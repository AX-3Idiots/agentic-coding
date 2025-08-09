from fastapi import FastAPI
from pydantic import BaseModel
from .logging_config import setup_logging
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from .workflow.graph import graph
from langchain_core.messages import HumanMessage
from .callbacks.logging_callback_handler import LoggingCallbackHandler
from .core.config import git_config
import logging

setup_logging()
load_dotenv()

# LoggingCallbackHandler 인스턴스 생성
logger = logging.getLogger(__name__)
callback_handler = LoggingCallbackHandler(logger, "default_session")

app = FastAPI(
    title="agentic-coding",
    description="Agentic Coding",
    default_response_class=JSONResponse,
    lifespan=git_config
)

class Request(BaseModel):
    input: str

@app.post("/invoke-workflow")
async def read_root(request: Request):
    response = await graph.ainvoke(
            {"messages": [HumanMessage(content=request.input)]},
            config={                
                "callbacks": [callback_handler]
            },
    )
    return {"response": response}