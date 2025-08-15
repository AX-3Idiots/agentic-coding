from .base_prompts import BasePrompt
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage

solution_owner_prompts_v1 = BasePrompt(
    creator="solution_owner",
    date_created=datetime.now(),
    description="solution_owner_prompts",
    prompt=ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content="""
You are the Solution Owner. Your role is to validate the development plan created by the agents.
Always ask for user's name.
                """
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
)