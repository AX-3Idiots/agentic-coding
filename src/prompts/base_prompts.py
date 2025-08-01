from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

class BasePrompt(BaseModel):
    """Base prompt for all prompts."""
    date_created: datetime    
    description: str
    creator: str
    prompt: ChatPromptTemplate