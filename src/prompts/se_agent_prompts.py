from .base_prompts import BasePrompt
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate

class SEAgentPrompts(BasePrompt):
    def __init__(
        self,
        creator: str,
        date_created: datetime,
        description: str,
        prompt: ChatPromptTemplate,
        ):
        super().__init__()
        self.creator = creator
        self.date_created = date_created
        self.description = description
        self.prompt = prompt

se_agent_prompts_v1 = SEAgentPrompts(
    creator="Dexter",
    date_created=datetime(year=2025, month=8, day=2),
    description="SE Agent Prompts for claude-code",
    prompt=ChatPromptTemplate(
        [
        ("system", """
        <identity>
        You are a software engineer.
        </identity>
        """)
    ])
)