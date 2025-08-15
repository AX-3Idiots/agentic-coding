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
from typing import List, Dict, Optional, Any
from langchain_core.messages import HumanMessage
import json,re

class ArchitectState(ToolState):
    """Architect 에이전트 전용으로 확장된 상태"""
    # 입력 데이터 (from payload)
    spec: Dict[str, Any]
    dev_rules: str
    git_url: str
    owner: str
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
      def _extract_json_objects(raw: str) -> list[dict]:
          """Extract all top-level JSON objects from text, robust to extra prose/code fences."""
          objects: list[dict] = []
          depth = 0
          start_idx: int | None = None
          in_string = False
          escape = False
          for idx, ch in enumerate(raw):
              if ch == '"' and not escape:
                  in_string = not in_string
              if ch == '\\' and in_string:
                  escape = not escape
              else:
                  escape = False
              if in_string:
                  continue
              if ch == '{':
                  if depth == 0:
                      start_idx = idx
                  depth += 1
              elif ch == '}':
                  if depth > 0:
                      depth -= 1
                      if depth == 0 and start_idx is not None:
                          candidate = raw[start_idx:idx + 1]
                          try:
                              parsed = json.loads(candidate)
                              if isinstance(parsed, dict):
                                  objects.append(parsed)
                          except Exception:
                              pass
                          start_idx = None
          return objects

      try:
          def _find_final_answer_from_messages() -> Optional[dict]:
              # Scan messages from newest to oldest
              for msg in reversed(state.get('messages', [])):
                  content = getattr(msg, 'content', None)
                  if isinstance(content, str) and content:
                      candidates = _extract_json_objects(content)
                      # Prefer final_answer wrapper
                      for obj in candidates:
                          if obj.get("tool_name") == "final_answer" and isinstance(obj.get("tool_code"), dict):
                              return obj
                      if candidates:
                          return candidates[0]
              return None

          def _find_final_answer_from_steps() -> Optional[dict]:
              # Scan intermediate tool outputs (strings) from newest to oldest
              for step in reversed(state.get('intermediate_steps', [])):
                  try:
                      _, step_text = step
                  except Exception:
                      continue
                  if isinstance(step_text, str) and step_text:
                      candidates = _extract_json_objects(step_text)
                      for obj in candidates:
                          if obj.get("tool_name") == "final_answer" and isinstance(obj.get("tool_code"), dict):
                              return obj
                      if candidates:
                          return candidates[0]
              return None

          last_message = _find_final_answer_from_messages() or _find_final_answer_from_steps()
          if not isinstance(last_message, dict):
              raise json.JSONDecodeError("Content is not a JSON object.", str(last_message), 0)
          # Accept either full tool wrapper or direct tool_code body
          message = last_message.get("tool_code", last_message)
      except (json.JSONDecodeError, TypeError, IndexError):
          message = {
              "owner": "Error: Could not parse final output.",
              "branch_name": "Error: Could not parse final output.",
              "architect_result": {
                  "description": "Error: Could not parse final output.",
                  "created_directories": [],
                  "created_files": []
              }
          }

      final_result = ArchitectAgentResult(
          owner=message.get('owner', 'Missing owner'),
          main_branch=message.get('branch_name', 'Missing branch_name'),
          architect_result=message.get('architect_result', {})

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
    입력받은 spec, dev_rules 등을 사용하여 LLM에게 전달할
    첫 번째 HumanMessage를 생성합니다.
    """
    spec = state.get('spec', {})
    dev_rules = state.get('dev_rules', '')
    git_url = state.get('git_url', '')
    owner = state.get('owner', '')

    plan_text = f"""
    <spec>
    {json.dumps(spec, indent=2)}
    </spec>
    <dev_rules>
    {dev_rules}
    </dev_rules>
    <git_url>
    {git_url}
    </git_url>
    <owner>
    {owner}
    </owner>
    """
    return {"messages": [HumanMessage(content=plan_text)]}
