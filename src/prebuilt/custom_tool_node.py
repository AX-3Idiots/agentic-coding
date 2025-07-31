from typing import TypedDict, Annotated, List, Tuple, Literal
from langchain_core.messages import AnyMessage, BaseMessage
from langchain_core.agents import AgentAction
import operator
from langgraph.graph import add_messages
from pydantic import BaseModel, Field
from ..utils.graph_utils import convert_to_tool_use_format

class ToolState(TypedDict):
    """State for the confluence agent."""
    messages: Annotated[List[AnyMessage], add_messages]
    intermediate_steps: Annotated[List[Tuple[AgentAction, str]], operator.add]
    chat_id: str

# Custom tools_condition function to check for function calls
def tools_condition(state: ToolState) -> Literal["tools", "__end__"]:
    """Check if the last message has a function call, route accordingly.
    
    Args:
        state: The agent state containing messages
        
    Returns:
        "tools" if the last message contains a function call
        "__end__" otherwise
    """
    messages = state["messages"]
    if not messages:
        return "__end__"
    last_message = messages[-1]
    
    # Check if it's an AI message with tool_calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # Check content if it's a JSON string containing type field
    if hasattr(last_message, "content"):
        # Use the utility function to handle all the conversion logic
        result = convert_to_tool_use_format(last_message)
        if result:
            return result
            
    # Check for function_call in additional_kwargs (OpenAI style)
    if hasattr(last_message, "additional_kwargs"):
        function_call = last_message.additional_kwargs.get("function_call")
        if function_call:
            return "tools"
    
    # For older model outputs that might have this field directly
    if hasattr(last_message, "function_call") and last_message.function_call:
        return "tools"
        
    return "__end__"