from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
import asyncio
from prebuilt import tools_condition, ToolState
from typing import Sequence
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts.base import BasePromptTemplate
from langchain_core.tools import BaseTool

def create_custom_react_agent(
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

    async def agent(state: ToolState) -> ToolState:
        """Confluence agent."""
        result = await asyncio.to_thread(agent_chain.invoke, state)
        return {"messages": [result], "intermediate_steps": [result.content]}
    
    graph_builder = StateGraph(ToolState)
    graph_builder.add_node("agent", agent)

    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)

    graph_builder.add_edge(START, "agent")
    graph_builder.add_conditional_edges(
        "agent",
        tools_condition,
    )
    graph_builder.add_edge("tools", "agent")
    graph_builder.add_edge("agent", END)
    graph = graph_builder.compile()
    graph.name = name

    return graph
