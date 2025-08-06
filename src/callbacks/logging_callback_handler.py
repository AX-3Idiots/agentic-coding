from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs.llm_result import LLMResult
import logging
from typing import Dict, Any

class LoggingCallbackHandler(BaseCallbackHandler):
    def __init__(self, logger: logging.Logger, session_id: str):
        self.logger = logger
        self.session_id = session_id
        # run_inline 속성 추가 - 콜백을 인라인으로 실행할지 결정
        self.run_inline = True

    def on_llm_end(self, response: LLMResult, **kwargs):
        self.logger.info(f"LLM response: {response.generations[0][0].text}")
        
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, *, run_id: str, **kwargs):
        self.logger.info(f"Tool start - serialized: {serialized}, input: {input_str}, kwargs: {kwargs}")
    
    def on_tool_end(self, output, **kwargs):
        self.logger.info(f"Tool end - output: {output}")

