from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
import asyncio
from ..prebuilt import tools_condition, ToolState
from typing import Sequence
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts.base import BasePromptTemplate
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from ..models.schemas import ArchitectAgentResult
from typing import List, Dict, Optional
from langchain_core.messages import HumanMessage
import json
class ArchitectState(ToolState):
    """Architect 에이전트 전용으로 확장된 상태"""
    # 입력 데이터
    main_goals: List[str]
    sub_goals: Dict[str, List[str]]
    # 최종 결과
    architect_result: Optional[ArchitectAgentResult]

def create_architect_agent(
        model: BaseChatModel,
        tools: Sequence[BaseTool],
        prompt: BasePromptTemplate,
        name: str = "agent"
    ) -> StateGraph:
    """
        Based on create_react_agent from langchain.
        This function uses custom tool_condition and logic for ai-cm usecases.
    """
    model_with_tools = model.bind_tools(tools)
    agent_chain = prompt | model_with_tools

    async def agent(state: ArchitectState) -> ArchitectState:
        """Confluence agent."""
        result = await asyncio.to_thread(agent_chain.invoke, state)
        return {"messages": [result], "intermediate_steps": [result.content]}

    async def answer_generator(state: ArchitectState) -> ArchitectState:
      """
      Parses the final message from the agent to create a structured result.
      If the message is not valid JSON, it returns a default result object
      to prevent the graph from crashing.
      """
      try:
          # Attempt to parse the JSON from the last message's content
          last_message = json.loads(state['messages'][-1].content)
          # Ensure last_message is a dictionary to prevent errors on .get()
          if not isinstance(last_message, dict):
              raise json.JSONDecodeError("Content is not a JSON object.", state['messages'][-1].content, 0)
      except (json.JSONDecodeError, TypeError):
          # If parsing fails, create a default object with error messages
          # This makes the agent more robust to unexpected LLM outputs.
          last_message = {
              "project_dir": "Error: Could not parse final output.",
              "branch_name": "Error: Could not parse final output.",
              "base_url": "Error: Could not parse final output.",
              "branch_url": "Error: Could not parse final output.",
          }

      final_result = ArchitectAgentResult(
          project_dir=last_message.get('project_dir', 'Missing project_dir'),
          main_branch=last_message.get('branch_name', 'Missing branch_name'),
          base_url=last_message.get('base_url', 'Missing base_url'),
          branch_url=last_message.get('branch_url', 'Missing branch_url')
      )
      return {"architect_result": final_result}


    def _tools_condition(state: ToolState) -> str:
        """
        기존 tools_condition을 호출하여 그 결과를 바탕으로,새로운 그래프의 분기점인 'tools' 또는 'final_answer_generator'를 반환합니다.
        """

        decision = tools_condition(state)

        if decision == "tools":
              return "tools"

        return "answer_generator"


    graph_builder = StateGraph(ArchitectState)
    graph_builder.add_node("initial_prompt", _create_initial_prompt)
    graph_builder.add_node("agent", agent)

    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("answer_generator", answer_generator)

    graph_builder.add_edge(START, "initial_prompt")
    graph_builder.add_edge("initial_prompt", "agent")

    graph_builder.add_conditional_edges(
        "agent",
        _tools_condition,
    )

    graph_builder.add_edge("tools", "agent")
    graph_builder.add_edge("answer_generator", END)
    graph = graph_builder.compile()
    graph.name = name

    return graph


def _create_initial_prompt(state: ArchitectState) -> dict:
    """
    입력받은 main_goals와 sub_goals를 사용하여
    LLM에게 전달할 첫 번째 HumanMessage를 생성합니다.
    """
    main_goals = state['main_goals']
    sub_goals = state['sub_goals']

    # f-string을 사용해 상세한 계획 메시지를 구성
    plan_text = f"""
    Here is the project plan. Please initialize the project based on it.

    <plan>
    <main_goals>
    {main_goals}
    </main_goals>
    <sub_goals>
    {sub_goals}
    </sub_goals>
    </plan>
    """

    # 구성된 텍스트를 HumanMessage로 만들어 messages 상태를 업데이트
    return {"messages": [HumanMessage(content=plan_text)]}