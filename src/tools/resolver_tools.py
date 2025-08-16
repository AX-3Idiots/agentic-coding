# /tools/resolver_tools.py

import logging
import asyncio
from typing import Type

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.language_models.chat_models import BaseChatModel

# --- 프롬프트 임포트 ---
# 업데이트된 범용 프롬프트를 가져옵니다.
from ..prompts.conflict_prompts import code_fixer_prompt_template

# --- 기본 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 도구의 입력 스키마 정의 ---
class CodeFixerInput(BaseModel):
    """Input schema for the CodeConflictResolverTool."""
    file_path: str = Field(description="The full path to the file that needs fixing.")
    file_content: str = Field(description="The full content of the file to be fixed.")
    error_context: str = Field(description="The context of the issue, which can be a merge conflict description or a runtime error message.")
    requirement: str = Field(description="The original user requirement or goal. This provides context for a logical fix.")

# --- 코드 문제 해결 전문 도구 클래스 ---
class CodeConflictResolverTool(BaseTool):
    """
    A specialized tool to fix code issues, including merge conflicts and runtime errors, using a powerful LLM.
    Use this when a file has a merge conflict or when a command execution fails with an error.
    """
    name: str = "CodeConflictResolverTool"
    description: str = (
        "Fixes code in a file based on an error or a merge conflict. "
        "Input should include the file path, its content, the error message (or conflict description), and the original requirement. "
        "It returns the complete, corrected code for the file."
    )
    args_schema: Type[BaseModel] = CodeFixerInput
    llm: BaseChatModel # 외부에서 LLM 인스턴스를 주입받기 위한 필드

    def _run(self, file_path: str, file_content: str, error_context: str, requirement: str) -> str:
        """Synchronous wrapper for the async run method."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._arun(file_path, file_content, error_context, requirement))

    async def _arun(self, file_path: str, file_content: str, error_context: str, requirement: str) -> str:
        """
        Uses an LLM to asynchronously analyze a code issue and generate a fixed version.
        """
        logging.info(f"Asynchronously attempting to fix code in file: {file_path}")

        parser = JsonOutputParser()
        chain = code_fixer_prompt_template | self.llm | parser

        try:
            response = await chain.ainvoke({
                "file_path": file_path,
                "file_content": file_content,
                "error_context": error_context,
                "requirement": requirement
            })

            logging.info(f"Successfully generated fixed code for {file_path}")
            return response['final_code']

        except Exception as e:
            logging.error(f"Failed to fix code for {file_path} with LLM: {e}")
            return f"Error: The LLM failed to generate a valid fix. Error: {str(e)}"

