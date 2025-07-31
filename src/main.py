from fastapi import FastAPI
import logging
from logging_config import setup_logging
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from .workflow.graph import graph
from langchain_core.messages import HumanMessage

setup_logging()
load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="agentic-coding",
    description="Agentic Coding",
    default_response_class=JSONResponse
)

class Request:
    input: str

@app.post("/invoke-workflow")
async def read_root(request: Request):
    response = await graph.ainvoke({
        "messages": [
            HumanMessage(content=request.input)
        ]
    })
    return response