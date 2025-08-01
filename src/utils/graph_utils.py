import json
import uuid

def transform_str_to_json(msg: str) -> dict:
    try:
        return json.loads(msg)
    except Exception as e:
        return msg

def transform_function_msg_to_tool_use(msg: dict) -> dict:
    """Transform a function message to a tool use format.
    
    Args:
        msg: The message to transform
        
    Returns:
        The transformed message in tool use format
    """
    # Check if we have 'parameters' instead of 'input'
    parameters = msg.get("parameters") or msg.get("input")
    
    # Handle parameters that might be a string or already a dict
    if isinstance(parameters, str):
        try:
            args = json.loads(parameters)
        except:
            args = parameters
    else:
        args = parameters
    
    # Use existing id if available, otherwise generate one
    tool_id = msg.get("id") or f"tooluse_{uuid.uuid4().hex}"
    
    return {
        "name": msg.get("name"),
        "args": args,
        "id": tool_id,
        "type": "tool_call"
    }

def convert_to_tool_use_format(last_message):
    """Convert various message formats to the standard tool use format.
    
    This function handles various input formats (string JSON, dict, etc.) and
    converts them to the proper tool use format expected by the Bedrock API.
    
    Args:
        last_message: The message to convert
        
    Returns:
        str: "function" if conversion was successful, None otherwise
    """
    try:
        # If content is a string that might be JSON
        if isinstance(last_message.content, str):
            content = last_message.content
            
            # Check for python_start and python_end tags
            if "<|python_start|>" in content and "<|python_end|>" in content:
                # Extract the JSON between the tags
                start_idx = content.find("<|python_start|>") + len("<|python_start|>")
                end_idx = content.find("<|python_end|>")
                json_str = content[start_idx:end_idx].strip()
                
                # Parse the JSON
                content_json = transform_str_to_json(json_str)
                if isinstance(content_json, dict) and content_json.get("type") == "function":
                    # Add "tool_calls" to the last_message
                    tool_call = transform_function_msg_to_tool_use(content_json)
                    last_message.tool_calls = [tool_call]
                    
                    # Transform to tool_use format
                    content_json["type"] = "tool_use"
                    
                    # Change parameters to input if it exists
                    if "parameters" in content_json:
                        content_json["input"] = content_json.pop("parameters")
                        
                    # Add id if missing
                    if "id" not in content_json:
                        content_json["id"] = tool_call["id"]
                        
                    # Ensure content is an array
                    last_message.content = [content_json]
                    return "tools"
            
            # Check if it looks like JSON
            elif content.strip().startswith('{'):
                content_json = transform_str_to_json(content)
                if isinstance(content_json, dict) and content_json.get("type") == "function":
                    # Add "tool_calls" to the last_message
                    tool_call = transform_function_msg_to_tool_use(content_json)
                    last_message.tool_calls = [tool_call]
                    
                    # Transform to tool_use format
                    content_json["type"] = "tool_use"
                    
                    # Change parameters to input if it exists
                    if "parameters" in content_json:
                        content_json["input"] = content_json.pop("parameters")
                        
                    # Add id if missing
                    if "id" not in content_json:
                        content_json["id"] = tool_call["id"]
                        
                    # Ensure content is an array
                    last_message.content = [content_json]
                    return "tools"
                    
        # Handle when content is already a dict
        elif isinstance(last_message.content, dict) and last_message.content.get("type") in ["function", "tool_use"]:
            content_json = last_message.content
            tool_call = transform_function_msg_to_tool_use(content_json)
            last_message.tool_calls = [tool_call]
            
            # Transform to tool_use format
            content_json["type"] = "tool_use"
            
            # Change parameters to input if it exists
            if "parameters" in content_json:
                content_json["input"] = content_json.pop("parameters")
                
            # Add id if missing
            if "id" not in content_json:
                content_json["id"] = tool_call["id"]
                
            # Ensure content is an array
            last_message.content = [content_json]
            return "function"
                    
        # If content is already an object with type attribute
        elif hasattr(last_message.content, "type") and last_message.content.type == "function":
            return "function"
            
    except Exception as e:
        print(f"Error converting content format: {e}")
        
    return None
