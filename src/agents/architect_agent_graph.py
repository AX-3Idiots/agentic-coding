from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
import asyncio
from ..prebuilt import tools_condition, ToolState
from typing import Sequence
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts.base import BasePromptTemplate
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from typing import List, Dict, Any
from langchain_core.messages import HumanMessage
import json
from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from pathlib import Path
from ..models.schemas import ArchitectAgentResult

class ArchitectState(ToolState):
    """Architect 에이전트 전용으로 확장된 상태"""
    # 입력 데이터 (from payload)
    messages: Annotated[List[AnyMessage], add_messages]
    spec: List[Dict[str, Any]]
    git_url: str
    owner: str
    branch_name: str
    dev_rules: str


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

    def _tools_condition(state: ToolState) -> str:
        """
        기존 tools_condition을 호출하여 그 결과를 바탕으로, 'tools' 또는 'end'로 분기합니다.
        """
        decision = tools_condition(state)
        if decision == "tools":
            return "tools"
        return "end"

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
        {"tools": "tools", "end": END},
    )

    graph_builder.add_edge("tools", "answer_generator")
    graph_builder.add_edge("answer_generator", "agent")
    graph = graph_builder.compile()
    graph.name = name

    return graph


def answer_generator(state: ArchitectState) -> dict:
    """
    Parses the last tool call messages to find the 'final_answer' tool output
    and adds a confirmation message to the message list.
    """
    # The AI's decision to call a tool is in the second-to-last message.
    # We need to check if there are enough messages.
    if len(state["messages"]) < 2:
        return {}

    last_ai_message = state["messages"][-2]
    if isinstance(last_ai_message, AIMessage) and last_ai_message.tool_calls:
        for tool_call in last_ai_message.tool_calls:
            if tool_call["name"] == "final_answer":
                branch_name = tool_call["args"].get("branch_name")
                if branch_name:
                    confirmation_message = f"Architecture for branch '{branch_name}' has been successfully generated."
                    new_message = HumanMessage(content=confirmation_message)
                    return {"messages": [new_message]}
    return {}


def _create_initial_prompt(state: ArchitectState) -> dict:
    """
    입력받은 spec, dev_rules 등을 사용하여 LLM에게 전달할
    첫 번째 HumanMessage를 생성합니다.
    """
    spec = state.get('spec', [])
    git_url = state.get('git_url', '')
    owner = state.get('owner', '')
    dev_rules = _build_dev_rules_text(owner)
    branch_name = state.get('branch_name', 'sample-project')

    plan_text = f"""
    <branch_name>
    {branch_name}
    </branch_name>
    <spec>
    {spec}
    </spec>
    <dev_rules>
    {dev_rules}
    </dev_rules>
    <git_url>
    {git_url}
    </git_url>
    """
    return {
        "messages": [HumanMessage(content=plan_text)],
        "branch_name": branch_name,
        "dev_rules": dev_rules
    }


def _read_rules_file(file_name: str) -> str:
        """
        주어진 규칙 파일 이름을 바탕으로 `src/rules/` 디렉토리에서 내용을 읽어
        문자열로 반환한다. 파일이 없거나 읽기에 실패하면 빈 문자열을 반환하여
        상위 로직이 안전하게 진행되도록 한다.
        """
        try:
            rules_dir = Path(__file__).resolve().parent.parent / "rules"
            target = rules_dir / file_name
            if not target.exists():
                return ""
            return target.read_text(encoding="utf-8")
        except Exception:
            return ""

def _build_dev_rules_text(owner: str) -> str:
        """
        고정된 기술 스택(FE: React, BE: FastAPI)에 따라 owner에 맞는 개발 규칙을 반환합니다.
        """
        file_name = ""
        framework = ""
        if owner == "FE":
            file_name = "react_rules.md"
            framework = "React"
        elif owner == "BE":
            file_name = "fastapi_rules.md"
            framework = "FastAPI"
        else:
            return ""

        content = _read_rules_file(file_name)
        if content:
            header = f"\n# Rules for {owner} - {framework}\n\n"
            return header + content.strip() + "\n"
        return ""