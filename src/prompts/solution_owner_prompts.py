import base_prompts
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage

solution_owner_prompts = base_prompts.BasePrompt(
    creator="solution_owner",
    date_created=datetime.now(),
    description="solution_owner_prompts",
    prompt=ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content="""
                """
            )
        ]
    )
)