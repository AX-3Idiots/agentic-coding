from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

class BasePrompt(BaseModel):
    model_name: str
    date_created: datetime
    prompt_test: str
    description: str
    creator: str
    prompt: ChatPromptTemplate