from __future__ import annotations
import json, time
import asyncio
from collections import defaultdict
from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.types import Send
from langchain_aws import ChatBedrockConverse
import boto3
from botocore.config import Config
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from typing import List, Dict, Any, TypedDict, Annotated, Tuple, Union
from botocore.exceptions import ClientError
from langfuse import get_client as get_langfuse_client
import random
from ..tools.final_answer_tools import FinalAnswerTool
from ..prompts import (
    solution_owner_prompts_v1,
    frontend_architect_agent_prompts,
    backend_architect_agent_prompts,
    allocate_role_v1,
    resolver_prompts
)
import os
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from ..tools.cli_tools import ExecuteShellCommandTool
from ..tools.resolver_tools import CodeConflictResolverTool
from ..constants.aws_model import AWSModel
from ..tools.spawn_container import spawn_engineers as spawn_engineers_tool
from ..agents.resolver_agent_graph import create_resolver_agent
from ..agents.architect_agent_graph import create_architect_agent
from pathlib import Path
from ..agents.graph import create_custom_react_agent
from langchain_core.tools import tool
from langgraph.types import interrupt
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
import re

load_dotenv()

class OverallState(TypedDict):
    """State for the overall graph."""
    messages: Annotated[List[AnyMessage], add_messages]
    base_url: str
    fe_spec: dict[str, Any] | None
    be_spec: dict[str, Any] | None
    response: str
    project_name: str
    fe_branch_name: str
    be_branch_name: str
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

parser = JsonOutputParser()

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

role_allocate_chain = allocate_role_v1.prompt | llm | JsonOutputParser()

@tool
def human_assistance(query: str) -> str:
    """
    Use this tool when you need human assistance.
    """
    # human_response = interrupt({"query": query})
    # return human_response["data"]
    return "Just assume the safe default for the archetype and requirements for software development."

solution_owner_agent = create_custom_react_agent(
    model=llm,
    tools=[human_assistance],
    prompt=solution_owner_prompts_v1.prompt,
    name="solution_owner_agent"
)

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

def parse_final_answer_with_langchain(text: str):
    m = re.search(r"<final_answer>([\s\S]*?)</final_answer>", text, re.IGNORECASE)
    if not m:
        raise ValueError("No <final_answer>...</final_answer> found")
    return parser.parse(m.group(1).strip())

async def solution_owner(state: OverallState, config: RunnableConfig):
    """Acts as the solution owner to validate the development plan.

    Args:
        state (OverallState): The state containing the 'messages' and 'base_url'.

    Returns:
        OverallState: An updated state dictionary with the solution owner's
            response message.
            Note: The return statement is currently commented out.

        Example:
            state = {
                "messages": [HumanMessage(content="What is the main goal of the project?")],
                "base_url": "https://github.com/AX-3Idiots/agentic_coding_test.git",
                "fe_spec": [
                    {
                    "title": "로그인 화면", "description": "아이디와 비밀번호를 입력하는 로그인 화면입니다. '아이디' 입력 필드(필수)와 '비밀번호' 입력 필드(필수, 입력 내용 숨김 처리)가 각각 존재합니다. 사용자가 정보를 입력하고 '로그인' 버튼을 클릭하면 서버로 로그인 요청을 보냅니다."
                    },
                    {
                    "title": "사용자 대시보드 화면", "description": "로그인 성공 후 진입하는 메인 대시보드 화면입니다. API로부터 받은 사용자 정보를 활용하여 'OOO님, 환영합니다!' 형태의 환영 메시지와 사용자의 이메일 주소를 보여줍니다. 추가로, 사용자가 로그아웃할 수 있는 '로그아웃' 버튼이 있으며 이 버튼을 누르면 로그인 화면으로 이동합니다."
                    }
                ],
                "be_spec": [
                    {
                    "endpoint": "POST /auth/login", "description": "사용자 인증을 처리합니다. 요청 body에는 `username`(string)과 `password`(string) 필드를 필수로 포함해야 합니다. 인증 성공 시, 상태 코드 200과 함께 `{ \"accessToken\": \"JWT_TOKEN_STRING\" }` 형식의 토큰을 반환합니다. 아이디나 비밀번호가 틀릴 경우, 상태 코드 401과 `{ \"error\": \"Invalid credentials\" }` 메시지를 반환합니다."
                    },
                    {
                    "endpoint": "GET /users/me","description": "현재 로그인된 사용자의 정보를 조회합니다. 반드시 요청 헤더에 `Authorization: Bearer {accessToken}` 형식의 유효한 토큰을 포함해야 합니다. 성공 시, 상태 코드 200과 `{ \"username\": \"유저이름\", \"email\": \"유저이메일\" }` 형식의 사용자 정보를 반환합니다. 토큰이 유효하지 않은 경우, 상태 코드 403과 `{ \"error\": \"Forbidden\" }` 메시지를 반환합니다."
                    }
                ]
            }
    """
    result = await solution_owner_agent.ainvoke({
        'messages': state['messages'],
        'intermediate_steps': [],
        'chat_id': config['configurable']['thread_id']
        })
    data = parse_final_answer_with_langchain(result['messages'][-1].content)
    return {
        "messages": result['messages'],
        "project_name": data['project_name'],
        "summary": data['summary'],
        "fe_spec": data['fe_spec'],
        "be_spec": data['be_spec']
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
    fe_spec = state.get("fe_spec", None)
    be_spec = state.get("be_spec", None)

    if fe_spec is None or be_spec is None:
        return {
            "messages": [AIMessage(content="Something went wrong. Please try again.")]
        }

    specs_to_process = [("FE", fe_spec), ("BE", be_spec)]
    tasks = []
    for owner, spec in specs_to_process:
        # 에이전트에 전달할 payload 구성
        payload = {
            "messages": state.get("messages", []),
            "spec": spec,
            "git_url": state.get("base_url", ""),
            "owner": owner,
        }

        architect_agent_to_run = frontend_architect_agent if owner == "FE" else backend_architect_agent

        task = _retry_async(
            architect_agent_to_run.ainvoke,
            payload,
            config={
                "recursion_limit": 100,
                "callbacks": [LangfuseCallbackHandler()]
            },
            max_retries=7,
            base_delay=0.6,
        )
        tasks.append(task)

    results = []
    if tasks:
        results = await asyncio.gather(*tasks)

    latest_messages = []
    for result in results:
        msgs = result.get("messages", []) if isinstance(result, dict) else []
        if isinstance(msgs, list):
            latest_messages.extend(msgs)

    return {
        "messages": latest_messages
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
graph_builder.add_node("solution_owner", solution_owner)
graph_builder.add_node("architect", architect)
graph_builder.add_node("role_allocate", role_allocate)
graph_builder.add_node("spawn_engineers", spawn_engineers)
graph_builder.add_node("resolver", resolver)

graph_builder.add_edge(START, "architect")
graph_builder.add_edge("architect", END)
# graph_builder.add_edge("architect", END)
# graph_builder.add_edge("dev_planning", "architect")
# graph_builder.add_edge("architect", "role_allocate")
# graph_builder.add_edge("role_allocate", "spawn_engineers")
# graph_builder.add_edge("resolver", END)

graph = graph_builder.compile()
graph.name = "agentic-coding-graph"
