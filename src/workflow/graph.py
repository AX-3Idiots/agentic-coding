from __future__ import annotations
import json

from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send
from langchain_aws import ChatBedrockConverse
import boto3
from botocore.config import Config
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from typing import List, Dict, Any, TypedDict, Annotated, Tuple, Union
from ..prompts import (
    # architect_agent_prompts,
    dev_env_init_prompts, 
    dev_planning_prompts_v2, 
    req_def_prompts, 
    allocate_role_v1,
    # se_agent_prompts, 
    # resolver_prompts
)
import os
from dotenv import load_dotenv
import operator
from ..constants.aws_model import AWSModel
import functools
from ..agents import create_custom_react_agent
import re

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

load_dotenv()

class InputState(TypedDict):
    """Input state for the AI CM graph."""
    messages: Annotated[List[AnyMessage], add_messages]

class OutputState(TypedDict):
    """Output state for the AI CM graph."""
    response: str

class DefineReqState(TypedDict):
    """State for the define req node."""
    messages: Annotated[List[AnyMessage], add_messages]
    requirements: List[str]
    user_scenarios: List[str]
    processes: List[str]
    domain_entities: List[str]
    non_functional_reqs: List[str]
    exclusions: List[str]

class DevEnvInitState(TypedDict):
    """State for the dev env init node."""
    messages: Annotated[List[AnyMessage], add_messages]
    language: list[str]
    framework: list[str]
    library: list[str]

class DevPlanningState(TypedDict):
    """State for the dev planning node."""
    messages: Annotated[List[AnyMessage], add_messages]
    main_goals: list[str]
    sub_goals: dict[str, list[str]]

class ArchitectState(TypedDict):
    """State for the software architect node."""
    messages: Annotated[List[AnyMessage], add_messages]
    main_goals: list[str]    

class RoleAllocateState(TypedDict):
    """State for the role allocate node."""
    messages: Annotated[List[AnyMessage], add_messages]
    sub_goals: dict[str, list[str]]    

class EngineerState(TypedDict):
    """State for the software engineer node."""
    messages: Annotated[List[AnyMessage], add_messages]
    jobs: dict[str, list[str]]

class ResolverState(TypedDict):
    """State for the resolver node."""
    messages: Annotated[List[AnyMessage], add_messages]
    agent_state: Annotated[List[Tuple[str, Dict[str, Any], int]], operator.add]

class OverallState(TypedDict):
    """State for the overall graph."""
    messages: Annotated[List[AnyMessage], add_messages]
    requirements: list[str]
    language: list[str]
    framework: list[str]
    library: list[str]
    main_goals: list[str]
    sub_goals: dict[str, list[str]]
    agent_state: Annotated[List[Tuple[str, Dict[str, Any], int]], operator.add]
    response: str

bedrock_client = boto3.client(
    "bedrock-runtime", 
    region_name=os.environ["AWS_DEFAULT_REGION"],
    config=Config(read_timeout=300)
)

llm = ChatBedrockConverse(
    model=AWSModel.ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION,
    client=bedrock_client,
    temperature=0,
    max_tokens=None,
    region_name=os.environ["AWS_DEFAULT_REGION"],
)

req_def_chain = req_def_prompts.prompt | llm
dev_env_init_chain = dev_env_init_prompts.prompt | llm
dev_planning_chain = dev_planning_prompts_v2.prompt | llm
role_allocate_chain = allocate_role_v1.prompt | llm
# architect_agent_chain = architect_agent_prompts | llm
# resolver_chain = resolver_prompts | llm

# architect_agent = create_custom_react_agent(
#     model=llm,
#     tools=[],
#     prompt=architect_agent_prompts,
#     name="architect_agent"
# )

async def define_req(state: InputState) -> DefineReqState:
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

    return {
        "messages": [result],
        "requirements": parse_section(result.content, "Functional Requirements"),
        "user_scenarios": parse_section(result.content, "User Scenarios"),
        "processes": parse_section(result.content, "Process Flow"),
        "domain_entities": parse_section(result.content, "Domain Entities"),
        "non_functional_reqs": parse_section(result.content, "Non-functional Requirements"),
        "exclusions": parse_section(result.content, "Not in Scope")
    }

async def dev_env_init(state: DefineReqState) -> DevEnvInitState:
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

async def dev_planning(state: DevEnvInitState) -> DevPlanningState:
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
    raw = getattr(result, "content", result)

    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {"main_goals": [], "sub_goals": {}}

    return {
        "messages": [result],
        "main_goals": parsed.get("main_goals", []),
        "sub_goals": parsed.get("sub_goals", {})
    }

async def architect(state: DevPlanningState) -> ArchitectState:
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
    # result = await architect_agent_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "main_goals": [result.content]}

async def role_allocate(state: DevPlanningState) -> RoleAllocateState:
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

    # result = await role_allocate_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "sub_goals": [result.content]}

def allocate_decision(state: RoleAllocateState, config: RunnableConfig):
    """Dynamically routes tasks to engineer agents based on allocation.

    This function acts as a conditional edge. It inspects the 'decision' key in
    the state, which is expected to contain the output from the 'role_allocate'
    node. Based on this decision, it determines which engineer agent(s) to
    spawn by creating a list of `Send` objects for the next step.

    If no specific agents are required, it can route to a default node like a
    resolver or synthesizer.

    Args:
        state (RoleAllocateState): The current state from the 'role_allocate' node.
        config (RunnableConfig): The configuration for the runnable, containing
            session-specific details.

    Returns:
        Union[Send, List[Send]]: A list of `Send` objects, each targeting a
            specific agent node with its assigned tasks. Can also return a single
            `Send` object to route to a fallback node.
            Note: The implementation is currently commented out.
    """
    decisions = []
    return 

async def spawn_engineers(state: RoleAllocateState) -> EngineerState:
    """A placeholder node for the software engineer agents' work.

    In a complete implementation, this node would likely be replaced by a
    dynamic dispatcher or multiple individual engineer agent nodes. It is
    invoked after role allocation to carry out the development tasks.

    Args:
        state (RoleAllocateState): The state containing allocated sub-goals.

    Returns:
        EngineerState: An updated state dictionary containing the results of the
            engineering work under the 'jobs' key.
            Note: The implementation is currently commented out.
    """
    # result = await se_agent_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "jobs": [result.content]}

async def resolver(state: ResolverState) -> OutputState:
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
    agent_results = {}
    for agent_name, agent_result in state["agent_state"]:
        last_message = agent_result["messages"][-1]
        agent_results[agent_name] = last_message.content
    
    # result = await resolver_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "response": [result.content]}

async def agent_node(state: Dict[str, Any], agent: CompiledStateGraph, name:str, config: RunnableConfig):
    """Dynamically invokes a sub-agent graph and formats its output.

    This function serves as a generic node to execute a compiled LangGraph agent.
    It passes the current state to the agent, invokes it with a specific
    configuration, and then wraps the agent's output in a dictionary structured
    to be merged into the main graph's 'agent_state'.

    Args:
        state (Dict[str, Any]): The current state dictionary of the main graph,
            which is passed as input to the sub-agent.
        agent (CompiledStateGraph): The pre-compiled LangGraph sub-agent to execute.
        name (str): The name of the agent, used for logging and to identify its
            output in the 'agent_state'.
        config (RunnableConfig): The configuration object for the agent invocation,
            which may contain session-specific information.

    Returns:
        Dict[str, Any]: A dictionary with the key 'agent_state', containing a list
            with a single tuple: (agent_name, agent_result).
    """
    result = await agent.ainvoke(
        state, 
        config={
            "recursion_limit": 16, 
            "configurable": {
                "session_id": config["configurable"].get("session_id")
            }
        }
    )
    return {
        "agent_state": [(name, result)]
    }

# architect_agent_node = functools.partial(agent_node, agent=architect_agent, name="architect")

graph_builder = StateGraph(input=InputState, output=OutputState, state_schema=OverallState)
graph_builder.add_node("define_req", define_req)
graph_builder.add_node("dev_env_init", dev_env_init)
graph_builder.add_node("dev_planning", dev_planning)
graph_builder.add_node("architect", architect)
graph_builder.add_node("role_allocate", role_allocate)
graph_builder.add_node("spawn_engineers", spawn_engineers)
graph_builder.add_node("resolver", resolver)

graph_builder.add_edge(START, "define_req")
graph_builder.add_edge("define_req", END)
# graph_builder.add_conditional_edges(
#     "define_req",
#     orchestrator_decision,
# )

graph_builder.add_edge("define_req", "dev_env_init")
graph_builder.add_edge("dev_env_init", "dev_planning")
graph_builder.add_edge("dev_planning", "architect")
graph_builder.add_edge("architect", "role_allocate")
graph_builder.add_edge("role_allocate", "spawn_engineers")
graph_builder.add_edge("spawn_engineers", "resolver")
graph_builder.add_edge("resolver", END)

graph = graph_builder.compile()
graph.name = "agentic-coding-graph"
