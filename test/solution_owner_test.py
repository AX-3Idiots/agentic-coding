from __future__ import annotations
import asyncio
from langgraph.graph import StateGraph, START, END, add_messages
from langchain_aws import ChatBedrockConverse
import boto3
from botocore.config import Config
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from typing import List, Any, TypedDict, Annotated
from botocore.exceptions import ClientError
from langfuse import get_client
import random
from src.prompts import (
    solution_owner_prompts_v1,
    solution_owner_prompts_v2
)
import os
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser, XMLOutputParser
from src.constants.aws_model import AWSModel
from pathlib import Path
from src.agents.graph import create_custom_react_agent
from langchain_core.tools import tool
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
import uuid
from pathlib import Path
import json
import re
# Load .env from repo root explicitly and override to ensure keys are visible
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env", override=True)
# Initialize callback; it reads LANGFUSE_* from environment
langfuse = get_client()  # uses env vars

lf_cb = LangfuseCallbackHandler()

class OverallState(TypedDict):
    """State for the overall graph."""
    messages: Annotated[List[AnyMessage], add_messages]
    base_url: str
    fe_spec: dict[str, Any] | None
    be_spec: dict[str, Any] | None
    response: str
    project_name: str

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
    prompt=solution_owner_prompts_v2.prompt,
    name="solution_owner_agent"
)

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
    return {"messages": result['messages']}

graph_builder = StateGraph(state_schema=OverallState)
graph_builder.add_node("solution_owner", solution_owner)

graph_builder.add_edge(START, "solution_owner")
graph_builder.add_edge("solution_owner", END)

graph = graph_builder.compile()
graph.name = "agentic-coding-graph"

parser = JsonOutputParser()

def parse_final_answer_with_langchain(text: str):
    m = re.search(r"<final_answer>([\s\S]*?)</final_answer>", text, re.IGNORECASE)
    if not m:
        try:
            return parser.parse(text)
        except Exception as e:
            raise ValueError("No <final_answer>...</final_answer> found")
    return parser.parse(m.group(1).strip())

async def main():    
    with langfuse.start_as_current_span(name="dexter-chat-session") as span:
        span.update_trace(user_id="Dexter")
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="Create a Shopping site app like Amazon only for frontend")],
            "base_url": "https://github.com/AX-3Idiots/agentic_coding_test.git"
            },
            config={
                "configurable": {"thread_id": str(uuid.uuid4())},
                "callbacks": [lf_cb]
            }
        )
        data = parse_final_answer_with_langchain(result['messages'][-1].content)
        print({
            "project_name": data.get('project_name', ''),
            "summary": data.get('summary', ''),
            "fe_spec": data.get('fe_spec', []),
            "be_spec": data.get('be_spec', [])
        })

if __name__ == "__main__":
    asyncio.run(main())