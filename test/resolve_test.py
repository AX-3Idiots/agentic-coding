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
from src.tools.final_answer_tools import FinalAnswerTool
from src.prompts import (
    solution_owner_prompts_v2,
    frontend_architect_agent_prompts,
    frontend_architect_agent_prompts_v2,
    backend_architect_agent_prompts,
    allocate_role_v2,
    resolver_prompts,
    se_agent_prompts
)
import re
import os
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from src.tools.cli_tools import ExecuteShellCommandTool
from src.tools.resolver_tools import CodeConflictResolverTool
from src.constants.aws_model import AWSModel
from src.tools.spawn_container import spawn_engineers as spawn_engineers_tool
from src.agents.resolver_agent_graph import create_resolver_agent
from src.agents.architect_agent_graph import create_architect_agent
from pathlib import Path
from src.agents.graph import create_custom_react_agent
from langchain_core.tools import tool
from langgraph.types import interrupt
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
import uuid
from src.core.config import git_config



# Load .env from repo root explicitly and override to ensure keys are visible
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)
# Initialize callback; it reads LANGFUSE_* from environment
langfuse = get_langfuse_client()  # uses env vars

lf_cb = LangfuseCallbackHandler()

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

config = Config(
    read_timeout=1800,
    connect_timeout=120,
    retries={
        "max_attempts": 8,
        "mode": "adaptive"
    },
)

us_bedrock_client = boto3.client(
    "bedrock-runtime",
    region_name='us-east-1',
    config=config,
)

kr_bedrock_client = boto3.client(
    "bedrock-runtime",
    region_name=os.environ["AWS_DEFAULT_REGION"],
    config=config,
)

sonnet_llm = ChatBedrockConverse(
    model=AWSModel.ANTHROPIC_CLAUDE_4_SONNET_SEOUL_CROSS_REGION,
    client=kr_bedrock_client,
    temperature=0,
    max_tokens=9000,
    region_name=os.environ["AWS_DEFAULT_REGION"],
)

opus_llm = ChatBedrockConverse(
    model=AWSModel.ANTHROPIC_CLAUDE_OPUS_4_1_CROSS_REGION,
    client=us_bedrock_client,
    temperature=0,
    max_tokens=9000,
    region_name=os.environ["AWS_DEFAULT_REGION"],
)

parser = JsonOutputParser()

@tool
def human_assistance(query: str) -> str:
    """
    Use this tool when you need human assistance.
    """
    # human_response = interrupt({"query": query})
    # return human_response["data"]
    return "Just assume the safe default for the archetype and requirements for software development."

async def spawn_engineers(base_url: str, branch_name: str, specs_list: list[list[dict]], **kwargs):
    """Spawn a container for each job and clean up the containers after the job is done.
    The container will implement the job using the claude-code.

    Args:
        base_url (str): The base URL of the repository.
        branch_name (str): The branch name to spawn engineers for.
        specs_list (list[dict]): The grouped specs to spawn engineers for.
            For example:
            specs_list = [
                [
                    {
                        "title": "...",
                        "description": "..."
                    },
                    ...
                ],
                [
                    {
                        "title": "...",
                        "description": "..."
                    },
                    ...
                ]
                ...
            ]

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
    # Run container spawning in a background thread and wait for completion
    try:
        results = await asyncio.to_thread(
            spawn_engineers_tool,
            git_url=base_url,
            branch_name=branch_name,
            jobs=specs_list,
            **kwargs
        )
    except Exception:
        # Swallow errors here to avoid crashing the graph; downstream resolver can proceed
        results = []

    return {"agent_results": results}

solution_owner_agent = create_custom_react_agent(
    model=sonnet_llm,
    tools=[human_assistance],
    prompt=solution_owner_prompts_v2.prompt,
    name="solution_owner_agent"
)

frontend_architect_agent = create_architect_agent(
    model=opus_llm,
    tools=[ExecuteShellCommandTool(), FinalAnswerTool()],
    prompt=frontend_architect_agent_prompts.prompt,
    name="frontend_architect_agent"
)

backend_architect_agent = create_architect_agent(
    model=opus_llm,
    tools=[ExecuteShellCommandTool(), FinalAnswerTool()],
    prompt=backend_architect_agent_prompts.prompt,
    name="backend_architect_agent"
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

def parse_final_answer_with_langchain(text: Union[str, List[Dict[str, Any]]]):
    if isinstance(text, list):
        full_text = []
        for part in text:
            if isinstance(part, str):
                full_text.append(part)
            elif isinstance(part, dict) and 'text' in part:
                full_text.append(part['text'])
        text = "".join(full_text)
    m = re.search(r"<final_answer>([\s\S]*?)</final_answer>", text, re.IGNORECASE)
    if not m:
        try:
            return parser.parse(text)
        except Exception as e:
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
        "project_name": data.get('project_name', ''),
        "summary": data.get('summary', ''),
        "fe_spec": data.get('fe_spec', []),
        "be_spec": data.get('be_spec', [])
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
    fe_spec = state.get("fe_spec")
    be_spec = state.get("be_spec")

    fe_branch_name = ""
    be_branch_name = ""

    specs_to_process = []
    if fe_spec:
        specs_to_process.append(("FE", fe_spec))
        fe_branch_name = f"{state.get('project_name','sample_project')}_FE"
    if be_spec:
        specs_to_process.append(("BE", be_spec))
        be_branch_name = f"{state.get('project_name','sample_project')}_BE"
    tasks = []
    for owner, spec in specs_to_process:
        if not spec:
            continue

        branch_name = fe_branch_name if owner == "FE" else be_branch_name
        # 에이전트에 전달할 payload 구성
        payload = {
            "messages": state.get("messages", []),
            "spec": spec,
            "git_url": state.get("base_url", ""),
            "owner": owner,
            "branch_name": branch_name,
        }

        architect_agent_to_run = frontend_architect_agent if owner == "FE" else backend_architect_agent

        task = _retry_async(
            architect_agent_to_run.ainvoke,
            payload,
            config={
                "recursion_limit": 200,
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
        "messages": latest_messages,
        "fe_branch_name": fe_branch_name,
        "be_branch_name": be_branch_name
    }


async def role_allocate(state: OverallState, config: RunnableConfig):
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
    fe_branch = state.get("fe_branch_name")
    be_branch = state.get("be_branch_name")

    @tool
    async def spawn_fe_engineers(base_url: str, specs_list: list[list[dict]]):
        """Spawns frontend engineers to work on the frontend branch. And clean up the containers after the job is done.
    The container will implement the job using the claude-code.
    Args:
        base_url (str): The base URL of the repository.
        specs_list (list[list[dict]]): The grouped specs to spawn engineers for.
    Returns:
        dict: A dictionary containing the agent results.
    """
        print(f"Spawning frontend engineers for {fe_branch} with {specs_list}")
        return await spawn_engineers(base_url, fe_branch, specs_list, is_frontend=True)

    @tool
    async def spawn_be_engineers(base_url: str, specs_list: list[list[dict]]):
        """Spawns backend engineers to work on the backend branch. And clean up the containers after the job is done.
    The container will implement the job using the claude-code.
    Args:
        base_url (str): The base URL of the repository.
        specs_list (list[list[dict]]): The grouped specs to spawn engineers for.
    Returns:
        dict: A dictionary containing the agent results.
    """
        print(f"Spawning backend engineers for {be_branch} with {specs_list}")
        return await spawn_engineers(base_url, be_branch, specs_list)

    role_allocate_agent = create_custom_react_agent(
        model=opus_llm,
        tools=[spawn_fe_engineers, spawn_be_engineers],
        prompt=allocate_role_v2.prompt,
        name="role_allocate_agent"
    )
    result = await role_allocate_agent.ainvoke({
        'messages': state['messages'],
        'intermediate_steps': [],
        'chat_id': config['configurable']['thread_id']
    },
    config={
        "recursion_limit": 200
    }
    )
    return {"messages": result['messages']}

graph_builder = StateGraph(state_schema=OverallState)
graph_builder.add_node("solution_owner", solution_owner)
graph_builder.add_node("architect", architect)
graph_builder.add_node("role_allocate", role_allocate)

graph_builder.add_edge(START, "solution_owner")
graph_builder.add_edge("solution_owner", "architect")
graph_builder.add_edge("architect", "role_allocate")
graph_builder.add_edge("role_allocate", END)

graph = graph_builder.compile()
graph.name = "agentic-coding-graph"


parser = JsonOutputParser()

async def main():
    async with git_config(app=None):
        with langfuse.start_as_current_span(name="anthony-chat-session") as span:
            span.update_trace(user_id="Anthony")
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="Create a GPT like chatbot app. The app should have a options for multiple models. I want the chatballon to have a animation when the chat is newly created by saying hello user.")],
                "base_url": "https://github.com/AX-3Idiots/dexter_test.git"
                },
                config={
                    "configurable": {"thread_id": str(uuid.uuid4())},
                    "callbacks": [lf_cb]
                }
            )


if __name__ == "__main__":
    asyncio.run(main())