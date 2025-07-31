from __future__ import annotations

from langgraph.graph import StateGraph, START, END, add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send
from langchain_aws import ChatBedrockConverse
import boto3
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from typing import List, Dict, Any, TypedDict, Annotated, Tuple
from prompts import (
    architect_agent_prompts,
    dev_env_init_prompts, 
    dev_planning_prompts, 
    req_def_prompts, 
    role_allocate_prompts, 
    se_agent_prompts, 
    resolver_prompts
)
import os
from dotenv import load_dotenv
import operator
from constants import AWSModel
import functools
import logging
from agents import create_custom_react_agent

load_dotenv()

logger = logging.getLogger(__name__)

class InputState(TypedDict):
    """Input state for the AI CM graph."""
    messages: Annotated[List[AnyMessage], add_messages]

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
    

bedrock_client = boto3.client("bedrock-runtime", region_name=os.environ["AWS_DEFAULT_REGION"])

llm = ChatBedrockConverse(
    model=AWSModel.ANTHROPIC_CLAUDE_4_SONNET_CROSS_REGION,
    client=bedrock_client,
    temperature=0,
    max_tokens=None,
    region_name="us-east-1",
)

req_def_chain = req_def_prompts | llm
dev_env_init_chain = dev_env_init_prompts | llm
dev_planning_chain = dev_planning_prompts | llm
role_allocate_chain = role_allocate_prompts | llm
architect_agent_chain = architect_agent_prompts | llm
resolver_chain = resolver_prompts | llm

architect_agent = create_custom_react_agent(
    model=llm,
    tools=[],
    prompt=architect_agent_prompts,
    name="architect_agent"
)

async def define_req(state: InputState) -> DefineReqState:
    """Define requirements."""
    result = await req_def_chain.ainvoke({'messages': state['messages']})
    return {"messages": [result], "requirements": [result.content]}

async def dev_env_init(state: DefineReqState) -> DevEnvInitState:
    """Initialize development environment."""
    result = await dev_env_init_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "language": [result.content], "framework": [result.content], "library": [result.content]}

async def dev_planning(state: DevEnvInitState) -> DevPlanningState:
    """Plan development."""
    result = await dev_planning_chain.ainvoke({'messages': state['messages']})    
    # return {"messages": [result], "main_goals": [result.content], "sub_goals": [result.content]}

async def architect(state: DevPlanningState) -> ArchitectState:
    """Architect."""
    result = await architect_agent_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "main_goals": [result.content]}

async def role_allocate(state: ArchitectState) -> RoleAllocateState:
    """Role allocate."""
    result = await role_allocate_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "sub_goals": [result.content]}

def allocate_decision(state: RoleAllocateState, config: RunnableConfig):
    """Based on role allocate decision spawn engineer agents."""
    decisions = []
    # for agent_key, agent_info in state["decision"].items():
    #     if isinstance(agent_info, dict):
    #         if isinstance(agent_info.get("should_invoke"), str):
    #             agent_info["should_invoke"] = agent_info["should_invoke"].lower() == "true"
    #         if agent_info.get("should_invoke", False) and agent_info.get("query", "") != "":
    #             decisions.append({
    #                 "target": agent_key,
    #                 "messages": [agent_info.get("query")]
    #             })

    # if len(decisions) == 0:
    #     return Send("synthesizer", {"messages": [state["direct_response"]], "agent_state": []})

    # return [Send(s["target"], {"messages": s["messages"], "intermediate_steps":[]}) for s in decisions]

async def spawn_engineers(state: RoleAllocateState) -> EngineerState:
    """spawn engineers."""
    # result = await se_agent_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "jobs": [result.content]}

async def resolver(state: ResolverState) -> OutputState:
    agent_results = {}
    for agent_name, agent_result in state["agent_state"]:
        last_message = agent_result["messages"][-1]
        agent_results[agent_name] = last_message.content
    
    result = await resolver_chain.ainvoke({'messages': state['messages']})
    # return {"messages": [result], "response": [result.content]}

async def agent_node(state: Dict[str, Any], agent: CompiledStateGraph, name:str, config: RunnableConfig):
    logger.info(f"agent_node {name} invoked::: ")
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

architect_agent_node = functools.partial(agent_node, agent=architect_agent, name="architect")

graph_builder = StateGraph(input=InputState, output=OutputState)
graph_builder.add_node("define_req", define_req)
graph_builder.add_node("dev_env_init", dev_env_init)
graph_builder.add_node("dev_planning", dev_planning)
graph_builder.add_node("architect", architect)
graph_builder.add_node("role_allocate", role_allocate)
graph_builder.add_node("spawn_engineers", spawn_engineers)

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
