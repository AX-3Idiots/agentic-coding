from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import json


class FinalAnswerInput(BaseModel):
    """Input schema for the final_answer tool matching the prompt contract."""

    branch_name: Optional[str] = Field(default=None, description="Name of the branch created for this work.")


class FinalAnswerTool(BaseTool):
    """
    A no-op aggregation tool that captures the architect agent's final structured
    answer and returns it verbatim for downstream parsing.
    """

    name: str = "final_answer"
    description: str = (
        "Collect the final structured result for the architect agent. "
        "Pass through the provided fields so the workflow can persist and use them."
    )
    args_schema: Type[BaseModel] = FinalAnswerInput

    def _run(
        self,
        branch_name: Optional[str] = None
    ) -> str:
        payload = {
            "tool_name": self.name,
            "tool_code": {
                # Always include provided fields; omit Nones for cleanliness
                **({"branch_name": branch_name} if branch_name is not None else {})
            },
        }
        # Return as JSON string so downstream regex/json parsing can consume it
        return json.dumps(payload)

    async def _arun(self, *args, **kwargs) -> str:  # pragma: no cover - sync path is primary
        return self._run(*args, **kwargs)

