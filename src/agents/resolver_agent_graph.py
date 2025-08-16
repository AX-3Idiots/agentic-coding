# /agents/cr_agent.py

import asyncio
from typing import Sequence, List, Dict, Optional
import re
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.prompts.base import BasePromptTemplate
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
import json
from ..models.schemas import ResolverAgentResult # Pydantic 모델 (별도 파일에 정의 가정)
from ..prebuilt import ToolState # LangGraph의 기본 상태 (별도 파일에 정의 가정)


class ResolverState(ToolState):
    """Conflict Resolver 에이전트 전용으로 확장된 상태"""
    # --- 입력 데이터 ---
    # SA 에이전트로부터 전달받는 기준 브랜치
    branch_name: str
    git_url: str

    # --- 최종 결과 ---
    # 에이전트 작업 완료 후 생성될 구조화된 결과
    resolver_result: Optional[ResolverAgentResult]


def create_resolver_agent(
        model: BaseChatModel,
        tools: Sequence[BaseTool],
        prompt: BasePromptTemplate,
        name: str = "resolver_agent"
    ) -> StateGraph:
    """
    Langchain의 ReAct 에이전트를 기반으로, 코드 충돌 해결 및 통합(CR)
    유스케이스에 맞춰 커스텀된 StateGraph를 생성합니다.
    """
    # 모델에 도구를 바인딩하여, LLM이 도구 사용을 결정할 수 있도록 합니다.
    model_with_tools = model.bind_tools(tools)
    # 프롬프트와 모델을 연결하여 에이전트의 핵심 체인을 구성합니다.
    agent_chain = prompt | model_with_tools

    async def agent(state: ResolverState) -> ResolverState:
        """Confluence agent."""
        result = await asyncio.to_thread(agent_chain.invoke, state)
        return {"messages": [result], "intermediate_steps": [result.content]}

    async def answer_generator(state: ResolverState) -> ResolverState:
      """
      모든 중간 과정이 끝난 후, 최종적으로 구조화된 요약 답변을 생성합니다.
      """
      # 이 노드는 현재 ReAct 프롬프트에서 'finish' 액션으로 대체되므로,
      # 필요 시 별도의 요약 프롬프트를 구성하여 사용할 수 있습니다.
      # 현재는 마지막 메시지를 결과로 간주하는 간단한 로직을 구현합니다.
      content = state['messages'][-1].content
      json_pattern = r'\{[^{}]*"final_url"[^{}]*\}'
      json_match = re.search(json_pattern, content, re.DOTALL)

      if json_match:
          json_str = json_match.group(0)
          last_message = json.loads(json_str)
          final_url = last_message.get('final_url')
      else:
          final_url = None
      final_result = ResolverAgentResult(
          final_url=final_url
      )
      return {"resolver_result": final_result}

    def _tools_condition(state: ToolState) -> str:
        """
        LLM의 마지막 응답을 보고 도구를 호출할지, 아니면 종료할지 결정합니다.
        LangGraph의 내장 `tools_condition`을 사용하여 분기합니다.
        """
        decision = tools_condition(state)
        if decision == "tools":
              return "tools"

        return "answer_generator"


    # 상태 그래프 빌더를 초기화합니다.
    graph_builder = StateGraph(ResolverState)

    # 그래프의 각 노드를 정의합니다.
    graph_builder.add_node("initial_prompt", _create_initial_prompt)
    graph_builder.add_node(name, agent)
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)
    graph_builder.add_node("answer_generator", answer_generator) # 필요 시 활성화

    # 그래프의 흐름(엣지)을 정의합니다.
    graph_builder.add_edge(START, "initial_prompt")
    graph_builder.add_edge("initial_prompt", name)

    # 'agent' 노드 이후에는 조건에 따라 분기합니다.
    graph_builder.add_conditional_edges(
        name,
        _tools_condition,
        # {"tools": "tools", END: END} 와 동일
    )

    # 'tools' 노드 실행 후에는 다시 'agent' 노드로 돌아가 다음 행동을 결정합니다.
    graph_builder.add_edge("tools", name)
    graph_builder.add_edge("answer_generator", END) # 필요 시 활성화

    # 그래프를 컴파일하여 실행 가능한 객체로 만듭니다.
    graph = graph_builder.compile()
    graph.name = name

    return graph


def _create_initial_prompt(state: ResolverState) -> dict:
    """
    에이전트 실행 시 입력받은 `base_branch`와 `requirement`를 사용하여
    LLM에게 전달할 첫 번째 임무 지시 메시지를 생성합니다.
    """
    branch_name = state['branch_name']
    git_url = state['git_url']

    # f-string을 사용해 명확한 초기 임무를 전달합니다.
    task_description = f"""
    Your task is to resolve conflicts and integrate branches.

    <task_info>
    <base_branch_to_merge_into>
    {branch_name}
    </base_branch_to_merge_into>
    <repository_path>
    {git_url}
    </repository_path>
    </task_info>


    Start by identifying the branches that need to be merged into the base branch.
    """

    # 구성된 텍스트를 HumanMessage로 만들어 messages 상태를 초기화합니다.
    return {"messages": [HumanMessage(content=task_description)]}

