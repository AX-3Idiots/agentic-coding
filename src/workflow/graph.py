from __future__ import annotations
import json, time
import asyncio
from collections import defaultdict
from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.types import Send
from langchain_aws import ChatBedrockConverse
import boto3
from botocore.config import Config
from langchain_core.messages import AnyMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from typing import List, Dict, Any, TypedDict, Annotated, Tuple, Union
from botocore.exceptions import ClientError
from langfuse import get_client as get_langfuse_client
import random
from ..tools.final_answer_tools import FinalAnswerTool
from ..prompts import (
    frontend_architect_agent_prompts,
    backend_architect_agent_prompts,
    dev_env_init_prompts,
    dev_planning_prompts_v2,
    req_def_prompts,
    allocate_role_v1,
    resolver_prompts
)
import os
from dotenv import load_dotenv
import operator
from langchain_core.output_parsers import JsonOutputParser
from ..tools.cli_tools import ExecuteShellCommandTool
from ..tools.resolver_tools import CodeConflictResolverTool
from ..constants.aws_model import AWSModel
from ..tools.spawn_container import spawn_engineers as spawn_engineers_tool
from ..agents.resolver_agent_graph import create_resolver_agent
from ..agents.architect_agent_graph import create_architect_agent
import re
from pathlib import Path

load_dotenv()

APPROVED = {
    "language": {
        "frontend": {"Javascript"},
        "backend": {"Javascript", "Python", "Java"},
    },
    "framework": {
        "frontend": {"React"},
        "backend": {"Spring Boot", "FastAPI", "Node.js"},
    },
    "library": {
        "frontend": {"Zustand", "Axios"},
        "backend": {"SQLAlchemy", "JPA", "Axios"},
    },
}


def parse_section(text: str, section_name: str) -> List[str]:
    """
    Extracts a list of items under a given section name like:
    ## Functional Requirements
    - ...
    - ...
    """
    pattern = rf"## {section_name}\n(.+?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    section = match.group(1).strip()
    lines = [line.strip("-• ").strip() for line in section.splitlines() if line.strip()]
    return lines

def _ensure_list(x) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(v).strip() for v in x if str(v).strip()]
    return [str(x).strip()]

def _take_allowed(values: List[str], allowed: set) -> List[str]:
    return [v for v in values if v in allowed]

def _dedup(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for v in seq:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out

class OverallState(TypedDict):
    """State for the overall graph."""
    messages: Annotated[List[AnyMessage], add_messages]
    base_url: str
    response: str
    project_name: str
    requirements: List[str]
    directory_tree: List[str]
    user_scenarios: List[str]
    processes: List[str]
    domain_entities: List[str]
    non_functional_reqs: List[str]
    exclusions: List[str]
    language: list[str]
    framework: list[str]
    library: list[str]
    main_goals: list[str]
    sub_goals: dict[str, list[str]]
    fe_branch_name: str
    be_branch_name: str
    fe_spec: dict[str, Any] | None
    be_spec: dict[str, Any] | None
    fe_architect_result: dict[str, Any]
    be_architect_result: dict[str, Any]
    user_story_groups: list[dict[str, list[str] | str]]
    agent_results: list[dict]

config = Config(
    read_timeout=900,
    connect_timeout=120,
    retries={
        "max_attempts": 8,
        "mode": "adaptive"
    },
)

bedrock_client = boto3.client(
    "bedrock-runtime",
    region_name=os.environ["AWS_DEFAULT_REGION"],
    config=config,
)

llm = ChatBedrockConverse(
    model=AWSModel.ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION,
    client=bedrock_client,
    temperature=0,
    max_tokens=None,
    region_name=os.environ["AWS_DEFAULT_REGION"],
)

async def _retry_async(func, *args, max_retries: int = 6, base_delay: float = 0.5, **kwargs):
    """
    지수 백오프(+지터)로 비동기 함수를 재시도하는 헬퍼.
    주로 AWS/네트워크 스로틀링(Throttling/TooManyRequests) 계열 오류에 한 번 더
    기회를 주기 위해 사용한다. 지정 횟수만큼 시도하며, 마지막에 한 번 더 최종 실행한다.
    """
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            msg = str(e)
            if "Throttling" in code or "TooManyRequests" in code or "Rate exceeded" in msg:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.3)
                await asyncio.sleep(delay)
                continue
            raise
        except Exception as e:
            # Some SDKs surface throttling as generic errors with message only
            txt = str(e)
            if any(x in txt for x in ["Throttling", "TooManyRequests", "Rate exceeded"]):
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.3)
                await asyncio.sleep(delay)
                continue
            raise
    # Final try
    return await func(*args, **kwargs)

req_def_chain = req_def_prompts.prompt | llm | JsonOutputParser()
dev_env_init_chain = dev_env_init_prompts.prompt | llm
dev_planning_chain = dev_planning_prompts_v2.prompt | llm | JsonOutputParser()
role_allocate_chain = allocate_role_v1.prompt | llm | JsonOutputParser()

frontend_architect_agent = create_architect_agent(
    model=llm,
    tools=[ExecuteShellCommandTool(), FinalAnswerTool()],
    prompt=frontend_architect_agent_prompts.prompt,
    name="frontend_architect_agent"
)

backend_architect_agent = create_architect_agent(
    model=llm,
    tools=[ExecuteShellCommandTool(), FinalAnswerTool()],
    prompt=backend_architect_agent_prompts.prompt,
    name="backend_architect_agent"
)

resolver_agent = create_resolver_agent(
    model=llm,
    tools=[ExecuteShellCommandTool(),CodeConflictResolverTool(llm=llm)],
    prompt=resolver_prompts.prompt,
    name="resolver_agent"
)

async def define_req(state: OverallState):
    """Processes the initial user input to define project requirements.

    This node invokes a language model chain (`req_def_chain`) to analyze the
    initial messages and extract a list of functional or non-functional
    requirements for the project.

    Args:
        state (InputState): The initial state containing the 'messages' from the user.

    Returns:
        DefineReqState: An updated state dictionary containing the response from
            the LLM chain under 'messages' and the extracted 'requirements' as a
            list of strings.
    """
    result = await req_def_chain.ainvoke({'messages': state['messages']})

    # result is now a parsed JSON dict
    return {
        "messages": [AIMessage(content=json.dumps(result))],
        "project_name": result.get("project_name", "Untitled Project"),
        "requirements": result.get("functional_requirements", []),
        "user_scenarios": result.get("user_scenarios", []),
        "processes": result.get("process_flow", []),
        "domain_entities": result.get("domain_entities", []),
        "non_functional_reqs": result.get("non_functional_requirements", []),
        "exclusions": result.get("not_in_scope", [])
    }

async def dev_env_init(state: OverallState):
    """Determines the technical stack for the development environment.

    Based on the defined requirements, this node invokes a language model chain
    (`dev_env_init_chain`) to decide on the programming language, frameworks,
    and libraries needed for the project.

    Args:
        state (DefineReqState): The state containing the project 'requirements'.

    Returns:
        DevEnvInitState: An updated state dictionary with the LLM response under
            'messages', and the determined 'language', 'framework', and 'library'.
            Note: The return statement is currently commented out.
    """

    payload = {
        # 프롬프트는 문자열을 기대하므로 join
        "project_name": state.get("project_name", "Untitled Project"),
        "requirements": "\n".join(state.get("requirements", [])),
        "user_scenarios": "\n".join(state.get("user_scenarios", [])),
        "processes": "\n".join(state.get("processes", [])),
        "domain_entities": "\n".join(state.get("domain_entities", [])),
        "non_functional_reqs": "\n".join(state.get("non_functional_reqs", [])),
    }

    result = await dev_env_init_chain.ainvoke(payload)
    raw = getattr(result, "content", result)
    # print("dev_env_init raw:", raw)

    # 1) JSON 파싱
    try:
        parsed = json.loads(raw)
    except Exception:
        # 안전장치: 파싱 실패 시 빈값 반환
        parsed = {"language": {}, "framework": {}, "library": {}}


    # 2) 스키마 정규화
    lang_fe = _ensure_list(parsed.get("language", {}).get("frontend"))
    lang_be = _ensure_list(parsed.get("language", {}).get("backend"))
    fw_fe   = _ensure_list(parsed.get("framework", {}).get("frontend"))
    fw_be   = _ensure_list(parsed.get("framework", {}).get("backend"))
    lib_fe  = _ensure_list(parsed.get("library", {}).get("frontend"))
    lib_be  = _ensure_list(parsed.get("library", {}).get("backend"))

    # 3) 화이트리스트 필터링
    lang_fe = _take_allowed(lang_fe, APPROVED["language"]["frontend"])
    lang_be = _take_allowed(lang_be, APPROVED["language"]["backend"])
    fw_fe   = _take_allowed(fw_fe,   APPROVED["framework"]["frontend"])
    fw_be   = _take_allowed(fw_be,   APPROVED["framework"]["backend"])
    lib_fe  = _take_allowed(lib_fe,  APPROVED["library"]["frontend"])
    lib_be  = _take_allowed(lib_be,  APPROVED["library"]["backend"])

    # 4) 평탄화 & 중복 제거 (최종 state 스키마에 맞춤)
    language  = _dedup(lang_fe + lang_be)
    framework = _dedup(fw_fe + fw_be)
    library   = _dedup(lib_fe + lib_be)

    return {
        "messages": [result],
        "language": language,
        "framework": framework,
        "library": library,
    }

async def dev_planning(state: OverallState):
    """Creates a high-level development plan with main goals and sub-goals.

    This node uses the context of the technical stack to invoke the
    `dev_planning_chain`, which breaks down the project into a series of
    main goals and a dictionary of corresponding sub-goals.

    Args:
        state (DevEnvInitState): The state containing the chosen 'language',
            'framework', and 'library'.

    Returns:
        DevPlanningState: An updated state dictionary with the LLM response under
            'messages', along with the 'main_goals' and 'sub_goals' for the project.
            Note: The return statement is currently commented out.
    """
    payload = {
        "project_name": state.get("project_name", "Untitled Project"),
        "requirements": "\n".join(state.get("requirements", [])),            # ← OverallState로부터 접근하거나 이전 노드에서 넣어두기
        "user_scenarios": "\n".join(state.get("user_scenarios", [])),
        "processes": "\n".join(state.get("processes", [])),
        "domain_entities": "\n".join(state.get("domain_entities", [])),
        "non_functional_reqs": "\n".join(state.get("non_functional_reqs", [])),

        "language": ", ".join(state.get("language", [])),
        "framework": ", ".join(state.get("framework", [])),
        "library": ", ".join(state.get("library", [])),
    }

    result = await dev_planning_chain.ainvoke(payload)
    parsed = result

    return {
        "messages": [AIMessage(content=json.dumps(parsed))],
        "main_goals": parsed.get("main_goals", []),
        "sub_goals": parsed.get("sub_goals", {}),
        "directory_tree": parsed.get("directory_tree", [])
    }


async def architect(state: OverallState):
    """Acts as the software architect to implement the main goals.

    This node invokes the `architect_agent_chain` to review and potentially
    implement the main goals of the project based on architectural best practices.

    Args:
        state (DevPlanningState): The state containing the 'main_goals' and
            'sub_goals' from the planning phase.

    Returns:
        ArchitectState: An updated state dictionary with the architect's
            response message and potentially refined 'main_goals'.
            Note: The return statement is currently commented out.
    """
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

    start_time = time.perf_counter()
    print("작업을 시작합니다...")

    fe_spec = state.get("fe_spec")
    be_spec = state.get("be_spec")

    specs_to_process = []
    if fe_spec and isinstance(fe_spec, dict):
        specs_to_process.append(("FE", fe_spec))
    if be_spec and isinstance(be_spec, dict):
        specs_to_process.append(("BE", be_spec))

    tasks = []
    fe_branch_name = ""
    be_branch_name = ""
    fe_architect_result = {}
    be_architect_result = {}

    for owner, spec in specs_to_process:
        if not spec.get("sub_goals"):
            continue

        dev_rules_text = _build_dev_rules_text(owner)

        # 에이전트에 전달할 payload 구성
        payload = {
            "messages": state.get("messages", []),
            "spec": spec,
            "dev_rules": dev_rules_text,
            "git_url": state.get("base_url", ""),
            "owner": owner,
        }

        architect_agent_to_run = frontend_architect_agent if owner == "FE" else backend_architect_agent

        task = _retry_async(
            architect_agent_to_run.ainvoke,
            payload,
            config={
                "recursion_limit": 100,
                "callbacks": [get_langfuse_client().start_trace(name=f"architect_agent_{owner.lower()}")]
            },
            max_retries=7,
            base_delay=0.6,
        )
        tasks.append(task)

    results = []
    if tasks:
        results = await asyncio.gather(*tasks)

    merged_messages = []
    for result in results:
        msgs = result.get("messages", []) if isinstance(result, dict) else []
        if isinstance(msgs, list):
            merged_messages.extend(msgs)

        res = result['architect_result']
        if res.owner == "FE":
            fe_branch_name = res.main_branch
            fe_architect_result = res.architect_result
        else:
            be_branch_name = res.main_branch
            be_architect_result = res.architect_result

    end_time = time.perf_counter()
    print("작업이 끝났습니다!")

    # 경과 시간 계산 (종료 시간 - 시작 시간)
    elapsed_time = end_time - start_time

    print(f"\n작업에 총 {elapsed_time:.4f}초가 걸렸습니다.")

    return {
        "messages": merged_messages,
        "fe_branch_name": fe_branch_name,
        "be_branch_name": be_branch_name,
        "fe_architect_result": fe_architect_result,
        "be_architect_result": be_architect_result
    }


async def role_allocate(state: OverallState):
    """Allocates sub-goals to different developer roles or agents.

    This node uses the `role_allocate_chain` to process the sub-goals and
    decide which software engineer agent is responsible for each task.

    Args:
        state (ArchitectState): The state containing the refined 'main_goals'
            from the architect.

    Returns:
        RoleAllocateState: An updated state dictionary with the allocation
            decision message and the `sub_goals` mapped to specific roles.
            Note: The return statement is currently commented out.
    """
    sub_goals = state.get("sub_goals", None)

    if sub_goals is None:
        return

    result = await role_allocate_chain.ainvoke({
        'sub_goals': state['sub_goals'],
        'requirements': state['requirements'],
        'user_scenarios': state['user_scenarios'],
        'processes': state['processes'],
        'domain_entities': state['domain_entities'],
        'non_functional_reqs': state['non_functional_reqs'],
        'exclusions': state['exclusions']
    })
    return {"messages": [AIMessage(content=json.dumps(result))], "user_story_groups": result.get("user_story_groups", [])}

async def spawn_engineers(state: OverallState):
    """A placeholder node for the software engineer agents' work.

    In a complete implementation, this node would likely be replaced by a
    dynamic dispatcher or multiple individual engineer agent nodes. It is
    invoked after role allocation to carry out the development tasks.

    Args:
        state (RoleAllocateState): The state containing allocated sub-goals.

    Returns:
        agent_results: list[dict]: A list of dictionaries, each containing container_id, code, cost_usd, error, and log.
        For example:
            [
                {
                    "container_id": "1234567890",
                    "code": "...",
                    "cost_usd": "...",
                    "error": "...",
                    "log": "..."
                }
                ...
        ]
    """

    if not state['user_story_groups']:
        return {}
    user_story_groups = state['user_story_groups']
    if len(user_story_groups) == 0:
        return {}

    # Run container spawning in a background thread and wait for completion
    try:
        results = await asyncio.to_thread(
            spawn_engineers_tool,
            state['base_url'],
            {
                "fe_branch_name": state['fe_branch_name'],
                "be_branch_name": state['be_branch_name']
            },
            user_story_groups,
        )
    except Exception:
        # Swallow errors here to avoid crashing the graph; downstream resolver can proceed
        results = []

    return {"agent_results": results}

async def resolver(state: OverallState):
    """Aggregates results from all agents and synthesizes a final response.

    This node collects the outputs from all preceding agent nodes, which are
    stored in 'agent_state'. It then invokes the `resolver_chain` to process
    these intermediate results and generate a final, coherent response.

    Args:
        state (ResolverState): The state containing the 'agent_state' list, which
            holds the outputs from all executed agents.

    Returns:
        OutputState: The final output state of the graph, containing the
            synthesized 'response'.
            Note: The return statement is currently commented out.
    """

    result = await resolver_agent.ainvoke(
        {
            'project_dir': state['branch_name'],
            'base_branch': state['branch_name']
        },
        config={"recursion_limit": 100}
    )
    # agent_results = {}
    # for agent_name, agent_result in state["agent_state"]:
    #     last_message = agent_result["messages"][-1]
    #     agent_results[agent_name] = last_message.content

    # result = await resolver_chain.ainvoke({'messages': state['messages']})
    return {"messages": result['messages'], "response": result['resolver_result']}

graph_builder = StateGraph(state_schema=OverallState)
graph_builder.add_node("define_req", define_req)
graph_builder.add_node("dev_env_init", dev_env_init)
graph_builder.add_node("dev_planning", dev_planning)
graph_builder.add_node("architect", architect)
graph_builder.add_node("role_allocate", role_allocate)
graph_builder.add_node("spawn_engineers", spawn_engineers)
graph_builder.add_node("resolver", resolver)

graph_builder.add_edge(START, "define_req")
graph_builder.add_edge("define_req", END)
graph_builder.add_edge("define_req", "dev_env_init")
graph_builder.add_edge("dev_env_init", "dev_planning")
graph_builder.add_edge("dev_planning", "architect")
graph_builder.add_edge("architect", END)
# graph_builder.add_edge("dev_planning", "architect")
# graph_builder.add_edge("architect", "role_allocate")
# graph_builder.add_edge("role_allocate", "spawn_engineers")
# graph_builder.add_edge("resolver", END)

graph = graph_builder.compile()
graph.name = "agentic-coding-graph"
