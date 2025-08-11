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
from ..prompts import (
    architect_agent_prompts,
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
    project_dir: str
    branch_url: str
    user_story_groups: list[dict[str, list[str] | str]]
    agent_results: list[dict]
    
config = Config(
    read_timeout=900,
    connect_timeout=120,
    retries={"max_attempts": 5},
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

req_def_chain = req_def_prompts.prompt | llm | JsonOutputParser()
dev_env_init_chain = dev_env_init_prompts.prompt | llm
dev_planning_chain = dev_planning_prompts_v2.prompt | llm | JsonOutputParser()
role_allocate_chain = allocate_role_v1.prompt | llm | JsonOutputParser()

architect_agent = create_architect_agent(
    model=llm,
    tools=[ExecuteShellCommandTool()],
    prompt=architect_agent_prompts.prompt,
    name="architect_agent"
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
        "sub_goals": parsed.get("sub_goals", {})
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
    start_time = time.perf_counter()
    print("작업을 시작합니다...")

    main_goals = state.get("main_goals", [])
    sub_goals_plan = state.get("sub_goals", {})
    # project_name = state.get("project_name", "sample-project")
    project_name = "sample-project"

    # Main Goals 맵 생성
    main_goals_map = {goal['id']: goal for goal in main_goals}

    # Owner별 작업 취합
    plan_builders = {
        "BE": {"main_goals_map": {}, "sub_goals": defaultdict(list)}, # <--- defaultdict 사용
        "FE": {"main_goals_map": {}, "sub_goals": defaultdict(list)}  # <--- defaultdict 사용
    }

    for goal_id, sub_goal_list in sub_goals_plan.items():
        parent_main_goal = main_goals_map.get(goal_id)
        if not parent_main_goal:
            continue

        for sub_goal in sub_goal_list:
            owner = sub_goal.get("owner")
            print(owner)
            if owner in plan_builders:
                builder = plan_builders[owner]
                # main_goal 객체를 딕셔너리에 저장하여 자동으로 중복 제거
                builder["main_goals_map"][goal_id] = parent_main_goal

                keys_to_keep = {
                    "id",
                    "title",
                    "description",
                    "dependencies",
                    "acceptance_criteria"
                }

                # 2. 새로운 딕셔너리를 만들어 원하는 키와 값만 복사
                filtered_sub_goal = {
                    key: sub_goal.get(key) for key in keys_to_keep
                }
                # sub_goal 추가
                builder["sub_goals"][goal_id].append(filtered_sub_goal)

    coroutines = []
    running_tasks = []
    fe_branch_name = ""
    be_branch_name = ""
    # 각 Owner(FE, BE)에 대해 실행할 작업을 생성
    for owner, builder in plan_builders.items():
        if not builder["sub_goals"]:
            continue # 해당 owner에 대한 작업이 없으면 건너뛰기
        print(builder["sub_goals"])

        if running_tasks:
            # 0.5초의 시간차를 둡니다.
            await asyncio.sleep(0.5)
        branch_name = f"{project_name}_{owner}"
        if owner == "FE":
            fe_branch_name = branch_name
        else:
            be_branch_name = branch_name

        plan = {
            "project_name": project_name,
            "branch_name": branch_name,
            "main_goals": list(builder["main_goals_map"].values()),
            "sub_goals": builder["sub_goals"]
        }

        task = asyncio.create_task(
            architect_agent.ainvoke(
                plan,
                config={"recursion_limit": 100}
            )
        )

        running_tasks.append(task)

    if running_tasks:
        results = await asyncio.gather(*running_tasks)

    for result in results:
        res = result['architect_result']
        if res.owner == "FE":
            fe_branch_name = res.main_branch
        else:
            be_branch_name = res.main_branch

    end_time = time.perf_counter()
    print("작업이 끝났습니다!")

    # 경과 시간 계산 (종료 시간 - 시작 시간)
    elapsed_time = end_time - start_time

    print(f"\n작업에 총 {elapsed_time:.4f}초가 걸렸습니다.")


    return {
        "messages": results[0]['messages'],
        "fe_branch_name": fe_branch_name,
        "be_branch_name": be_branch_name
        # "project_dir": result['architect_result'].project_dir,
        # "branch_name": result['architect_result'].main_branch,
        # "base_url": result['architect_result'].base_url,
        # "branch_url": result['architect_result'].branch_url
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
            state['branch_name'],
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
            'project_dir': state['project_dir'],
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
graph_builder.add_edge("dev_planning", "architect")
graph_builder.add_edge("architect", "role_allocate")
graph_builder.add_edge("role_allocate", "spawn_engineers")
graph_builder.add_edge("spawn_engineers", "resolver")
graph_builder.add_edge("resolver", END)

graph = graph_builder.compile()
graph.name = "agentic-coding-graph"
