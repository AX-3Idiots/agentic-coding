from .base_prompts import BasePrompt
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate

class AllocateRolePrompt(BasePrompt):
    pass

allocate_role_v1 = AllocateRolePrompt(
    creator="Dexter",
    date_created=datetime(year=2025, month=8, day=5),
    description="Allocate roles to code agents",
    prompt=ChatPromptTemplate(
        [
        ("system", """
        <identity>
        You are a software engineer.
        </identity>
        """)
    ])
)