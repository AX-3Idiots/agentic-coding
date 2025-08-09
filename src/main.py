from fastapi import FastAPI
from pydantic import BaseModel
from .logging_config import setup_logging
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from .workflow.graph import graph
from langchain_core.messages import HumanMessage
from .callbacks.logging_callback_handler import LoggingCallbackHandler
from .core.config import git_config
import os

setup_logging()
load_dotenv()

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
                "callbacks": [LoggingCallbackHandler]
            },
    )
    return {"response": response}