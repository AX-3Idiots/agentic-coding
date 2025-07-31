from fastapi import FastAPI
from logging_config import setup_logging
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
from .workflow.graph import graph
from langchain_core.messages import HumanMessage
from callbacks import logging_callback_handler

setup_logging()
load_dotenv()

app = FastAPI(
    title="agentic-coding",
    description="Agentic Coding",
    default_response_class=JSONResponse
)

class Request:
    input: str

@app.post("/invoke-workflow")
async def read_root(request: Request):
    response = await graph.ainvoke(
            {"messages": [HumanMessage(content=request.input)]},
            config={                
                "callbacks": [logging_callback_handler]
            },
    )
    return response