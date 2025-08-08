from __future__ import annotations

from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send
from langchain_aws import ChatBedrockConverse
import boto3
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from typing import List, Dict, Any, TypedDict, Annotated, Tuple, Union
from ..prompts import (
    architect_agent_prompts,
    # dev_env_init_prompts,
    # dev_planning_prompts,
    # req_def_prompts,
    # role_allocate_prompts,
    allocate_role_v1,
    # se_agent_prompts,
    resolver_prompts
)
import os
from dotenv import load_dotenv
import operator

from ..tools.cli_tools import ExecuteShellCommandTool
from ..tools.resolver_tools import CodeConflictResolverTool
from ..constants.aws_model import AWSModel
import functools
from ..agents import create_custom_react_agent
from ..agents.architect_agent_graph import create_architect_agent
from ..agents.resolver_agent_graph import create_resolver_agent
load_dotenv()

class InputState(TypedDict):
    """Input state for the AI CM graph."""
    messages: Annotated[List[AnyMessage], add_messages]
    git_url: str

class OutputState(TypedDict):
    """Output state for the AI CM graph."""
    response: str

class DefineReqState(TypedDict):
    """State for the define req node."""
    messages: Annotated[List[AnyMessage], add_messages]
    requirements: list[str]

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
    branch_name: str
    base_url: str
    branch_url: str
    project_dir: str

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
    branch_name: str
    project_dir: str
    base_url: str
    branch_url: str
    agent_state: Annotated[List[Tuple[str, Dict[str, Any], int]], operator.add]
    response: str


bedrock_client = boto3.client("bedrock-runtime", region_name=os.environ["AWS_DEFAULT_REGION"])

llm = ChatBedrockConverse(
    model=AWSModel.ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION,
    client=bedrock_client,
    temperature=0,
    max_tokens=None,
    region_name=os.environ["AWS_DEFAULT_REGION"],
)

# req_def_chain = req_def_prompts | llm
# dev_env_init_chain = dev_env_init_prompts | llm
# dev_planning_chain = dev_planning_prompts | llm
role_allocate_chain = allocate_role_v1.prompt | llm
# architect_agent_chain = architect_agent_prompts | llm
# resolver_chain = resolver_prompts | llm

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
    # result = await req_def_chain.ainvoke({'messages': state['messages']})
    result = llm.invoke(state['messages'])
    print(result)
    return {"messages": [result], "requirements": [result.content]}

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
    # result = await dev_env_init_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "language": [result.content], "framework": [result.content], "library": [result.content]}

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
    # result = await dev_planning_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "main_goals": [result.content], "sub_goals": [result.content]}

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
    main_goals = [
    "이메일과 비밀번호를 이용한 간단한 회원가입 및 로그인 기능을 제공하는 FastAPI 기반 API 서버를 구축한다."
    ]
    sub_goals = {
        "회원가입 기능 구현": [
            "`/register` 엔드포인트를 POST 방식으로 구현한다.",
            "사용자로부터 이메일과 비밀번호를 입력받는다.",
            "비밀번호는 bcrypt를 사용해 해시 처리한 뒤 저장한다.",
            "이메일 중복 여부를 확인하고 중복 시 에러를 반환한다."
        ],
        "로그인 기능 구현": [
            "`/login` 엔드포인트를 POST 방식으로 구현한다.",
            "입력된 이메일과 비밀번호를 검증한다.",
            "로그인 성공 시 JWT 토큰을 발급하여 응답한다.",
            "실패 시 적절한 에러 메시지를 반환한다."
        ],
        "JWT 기반 인증 처리": [
            "`/me`와 같은 보호된 엔드포인트를 생성한다.",
            "요청 헤더의 Authorization Bearer 토큰을 검증한다.",
            "토큰이 유효한 경우 사용자 정보를 반환한다."
        ],
        "간단한 데이터 저장 방식": [
            "사용자 정보는 메모리 또는 JSON 파일에 임시 저장한다.",
            "개발용이므로 DB는 사용하지 않는다.",
            "`User` 모델은 `email`, `hashed_password` 필드를 가진다."
        ],
        "환경 설정 및 실행": [
            "`requirements.txt`에 필요한 패키지 (fastapi, uvicorn, bcrypt, pyjwt)를 명시한다.",
            "`main.py` 하나의 파일에서 전체 API를 구현한다.",
            "Uvicorn을 사용해 로컬에서 서버를 실행할 수 있도록 설정한다."
        ]
    }

    result = await architect_agent.ainvoke(
        {
            'main_goals': main_goals,
            'sub_goals': sub_goals
        },
        config={"recursion_limit": 100}
    )
    print(result['architect_result'])
    return {
        "messages": result['messages'],
        "project_dir": result['architect_result'].project_dir,
        "branch_name": result['architect_result'].main_branch,
        "base_url": result['architect_result'].base_url,
        "branch_url": result['architect_result'].branch_url
    }


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

    result = await role_allocate_chain.ainvoke({'messages': state['messages']})
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

async def resolver(state: ArchitectState) -> OutputState:
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

    print(1)
    result = await resolver_agent.ainvoke(
        {
            'project_dir': state['project_dir'],
            'base_branch': state['branch_name']
        },
        config={"recursion_limit": 100}
    )
    print(result)
    # agent_results = {}
    # for agent_name, agent_result in state["agent_state"]:
    #     last_message = agent_result["messages"][-1]
    #     agent_results[agent_name] = last_message.content

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
