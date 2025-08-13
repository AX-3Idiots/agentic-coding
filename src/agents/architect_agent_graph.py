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
import json,re
class ArchitectState(ToolState):
    """Architect 에이전트 전용으로 확장된 상태"""
    # 입력 데이터
    main_goals: List[str]
    sub_goals: Dict[str, List[str]]
    project_name: str
    branch_name: str
    directory_tree: List[str]
    git_url: str
    owner: str
    dev_rules: str
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
          """Extract all top-level JSON objects from text, robust to extra prose/code fences.
          Tracks braces outside of quoted strings to find balanced objects, then parses to dicts.
          """
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
    입력받은 main_goals와 sub_goals를 사용하여
    LLM에게 전달할 첫 번째 HumanMessage를 생성합니다.
    """

    # 소유자(FE/BE)에 맞게 디렉토리 트리를 정규화/필터링한다.
    # - FE: 모든 경로에서 'frontend/' 접두를 제거하고, FE 관련 경로만 유지하여 루트가 'src/' 등으로 시작되도록 보장한다
    # - BE: 'frontend/'는 제외하고, 'backend/' 접두는 제거하여 BE 경로의 루트를 평탄화한다
    # - 공통: 불릿/공백 및 'repo/' 접두 제거로 일관된 상대 경로를 보장한다
    directory_tree = get_filtered_directory_tree(state['directory_tree'], state['owner'])

    def _slugify_branch_base(name: str) -> str:
        """프로젝트명에서 브랜치명에 부적합한 문자를 '-'로 치환하고
        연속 구분자를 하나로 축약해 안정적인 브랜치 베이스를 만든다.
        예) "User Authentication System" -> "user-authentication-system"
        """
        lower = name.strip().lower()
        result_chars = []
        prev_hyphen = False
        for ch in lower:
            if ch.isalnum():
                result_chars.append(ch)
                prev_hyphen = False
            else:
                if not prev_hyphen:
                    result_chars.append('-')
                    prev_hyphen = True
        s = ''.join(result_chars).strip('-')
        while '--' in s:
            s = s.replace('--', '-')
        return s

    project_name = state['project_name']
    owner = state['owner']
    # 일관된 브랜치 네이밍 규칙을 적용한다: <slugified-project-name>_<OWNER>
    # 공백/대소문자/특수문자에 의한 혼선을 방지하고, 오너 표기를 명확히 구분한다
    try:
        slug_base = _slugify_branch_base(project_name) if project_name else ""
        branch_name = f"{slug_base}_{owner}" if slug_base and owner else state['branch_name']
    except Exception:
        branch_name = state['branch_name']
    # f-string을 사용해 상세한 계획 메시지를 구성

    # 디버그: 프롬프트에 전달되는 최종 브랜치명을 로깅하여 추적성을 높인다
    plan_text = f"""
    Here is the project plan. Please initialize the project based on it.

    <plan>
    <main_goals>
    {state['main_goals']}
    </main_goals>
    <sub_goals>
    {state['sub_goals']}
    </sub_goals>
    </plan>

    <directory_tree>
    {directory_tree}
    </directory_tree>

    <git_url>
    {state['git_url']}
    </git_url>

    <project_name>
    {state['project_name']}
    </project_name>

    <branch_name>
    {branch_name}
    </branch_name>

    <dev_rules>
    {state['dev_rules']}
    </dev_rules>

    """
    # 구성된 텍스트를 HumanMessage로 만들어 messages 상태를 업데이트
    return {"messages": [HumanMessage(content=plan_text)]}

def get_filtered_directory_tree(directory_tree: list[str], owner: str) -> list[str]:
    """
    owner 별로 디렉토리 트리를 필터링/정규화한다.
    - FE: 'frontend/' 하위만 유지하고, 반환 시 'frontend/' 접두는 제거한다.
    - BE: 'frontend/'는 제외하고, 'backend/' 접두는 제거하여 반환한다. 'infra/' 등 기타 경로는 그대로 포함한다.
    - 입력은 'repo/...' 또는 상위 경로가 포함된 형식도 허용하며 'repo/' 이전은 제거한다.
    """

    def normalize(path: str) -> str:
        p = path.strip().lstrip("-* \t")
        # Collapse any prefix up to 'repo/' if present anywhere
        if "repo/" in p:
            p = p.split("repo/", 1)[1]
        # Normalize embedded segments so path starts from that segment
        if "/frontend/" in p and not p.startswith("frontend/"):
            p = "frontend/" + p.split("/frontend/", 1)[1]
        if "/backend/" in p and not p.startswith("backend/") and not p.startswith("frontend/"):
            p = "backend/" + p.split("/backend/", 1)[1]
        return p

    normalized = [normalize(p) for p in directory_tree]

    if owner == "FE":
        # Keep only frontend items and strip the 'frontend/' prefix entirely so output starts at src/, public/, etc.
        fe_items = []
        for p in normalized:
            if p.startswith("frontend/") or "/frontend/" in p:
                s = p.split("frontend/", 1)[1]
                if s:
                    fe_items.append(s)
        return [x for x in fe_items if x]
    elif owner == "BE":
        # Exclude any frontend paths; strip 'backend/' prefix from backend items
        be_candidates = [p for p in normalized if not (p.startswith("frontend/") or "/frontend/" in p)]
        cleaned = [p[len("backend/"):] if p.startswith("backend/") else p for p in be_candidates]
        return [x for x in cleaned if x]
    else:
        raise ValueError(f"잘못된 owner 값입니다: {owner}. 'FE' 또는 'BE'여야 합니다.")