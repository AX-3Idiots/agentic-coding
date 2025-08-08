# /tools/resolver_tools.py

import logging
import asyncio
from typing import Type

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.language_models.chat_models import BaseChatModel

# --- 프롬프트 임포트 ---
# 별도 파일로 분리된 프롬프트 템플릿을 가져옵니다.
from ..prompts.conflict_prompts import conflict_prompt_template

# --- 기본 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 도구의 입력 스키마 정의 ---
class ConflictResolverInput(BaseModel):
    """Input schema for the CodeConflictResolverTool."""
    file_path: str = Field(description="The full path to the file with the merge conflict.")
    conflict_content: str = Field(description="The full content of the file including the '<<<<<<<', '=======', '>>>>>>>' markers.")
    requirement: str = Field(description="The original user requirement or goal that led to these code changes. This provides context for a logical merge.")

# --- 코드 충돌 해결 전문 도구 클래스 ---
class CodeConflictResolverTool(BaseTool):
    """
    A specialized tool to resolve code merge conflicts using a powerful LLM.
    Use this ONLY when a file has been identified as having a merge conflict
    and its content has been read.
    """
    name: str = "resolve_code_conflict"
    description: str = (
        "Resolves a git merge conflict within a file. "
        "Use this tool ONLY AFTER you have read the content of a file and confirmed it contains '<<<<<<< HEAD' markers. "
        "It takes the conflicting code and the original requirement, and returns the final, clean, merged code."
    )
    args_schema: Type[BaseModel] = ConflictResolverInput
    llm: BaseChatModel # 외부에서 LLM 인스턴스를 주입받기 위한 필드

    def _run(self, file_path: str, conflict_content: str, requirement: str) -> str:
        """Synchronous wrapper for the async run method."""
        # 이벤트 루프가 이미 실행 중인 환경과의 호환성을 위해 get_event_loop 사용
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self._arun(file_path, conflict_content, requirement))

    async def _arun(self, file_path: str, conflict_content: str, requirement: str) -> str:
        """
        Uses an LLM to asynchronously analyze a code conflict and generate a resolved version.
        """
        logging.info(f"Asynchronously attempting to resolve conflict in file: {file_path}")

        # LLM의 출력을 안정적으로 파싱하기 위한 JSON 파서
        parser = JsonOutputParser()

        # 프롬프트, LLM, 파서를 하나의 체인(LCEL)으로 연결합니다.
        # 이제 전역 llm 대신, 클래스 인스턴스의 self.llm을 사용합니다.
        chain = conflict_prompt_template | self.llm | parser

        try:
            # 체인을 비동기적으로 실행하여 LLM으로부터 응답을 받습니다.
            response = await chain.ainvoke({
                "file_path": file_path,
                "conflict_content": conflict_content,
                "requirement": requirement
            })

            logging.info(f"Successfully generated resolved code for {file_path}")
            # 파싱된 JSON에서 'final_code' 키의 값만 반환합니다.
            return response['final_code']

        except Exception as e:
            logging.error(f"Failed to resolve conflict for {file_path} with LLM: {e}")
            return f"Error: The LLM failed to generate a valid resolution. Error: {str(e)}"

