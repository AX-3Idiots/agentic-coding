from fastapi import FastAPI
from pydantic import BaseModel
from .logging_config import setup_logging
from dotenv import load_dotenv
from fastapi.responses import JSONResponse, StreamingResponse
from .workflow.graph import graph
from langchain_core.messages import HumanMessage
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
from .callbacks.logging_callback_handler import LoggingCallbackHandler
from .core.config import git_config
import logging
import json
import uuid

setup_logging()
load_dotenv()

# LoggingCallbackHandler 인스턴스 생성
logger = logging.getLogger(__name__)
callback_handler = LoggingCallbackHandler(logger, "default_session")
langfuse_callback_handler = LangfuseCallbackHandler()

app = FastAPI(
    title="agentic-coding",
    description="Agentic Coding",
    default_response_class=JSONResponse,
    lifespan=git_config
)

class Request(BaseModel):
    input: str
    git_url: str

@app.post("/invoke-workflow")
async def read_root(request: Request):
    response = await graph.ainvoke(
            {"messages": [HumanMessage(content=request.input)],
            "base_url": request.git_url
            },
            config={
                "configurable": {"thread_id": str(uuid.uuid4())},
                "callbacks": [callback_handler, langfuse_callback_handler]
            },
    )
    return {"response": response}

@app.post("/stream-workflow")
async def stream_workflow(request: Request):
    async def ndjson_stream():
        # Send an initial line to flush headers and open the stream on clients
        yield (json.dumps({"status": "starting"}, ensure_ascii=False) + "\n").encode("utf-8")

        inputs = {
            "messages": [HumanMessage(content=request.input)],
            "base_url": request.git_url,
        }
        cfg = {"callbacks": [callback_handler]}

        # Choose the best available stream API, but iterate with one unified loop
        events_iter = (
            graph.astream_events(inputs, config=cfg, version="v1")
            if getattr(graph, "astream_events", None)
            else graph.astream_log(inputs, config=cfg)
        )

        async for event in events_iter:
            try:
                if isinstance(event, (bytes, bytearray)):
                    text = event.decode("utf-8", errors="ignore")
                    try:
                        obj = json.loads(text)
                    except Exception:
                        obj = {"message": text}
                elif isinstance(event, (dict, list)):
                    obj = event
                else:
                    text = str(event)
                    try:
                        obj = json.loads(text)
                    except Exception:
                        obj = {"message": text}
                yield (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
            except Exception:
                continue

    return StreamingResponse(
        ndjson_stream(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
        },
    )

@app.post("/stream-workflow-v2")
async def stream_workflow_v2(request: Request):
    async def ndjson_stream():
        # Send an initial line to flush headers and open the stream on clients
        yield (json.dumps({"status": "starting"}, ensure_ascii=False) + "\n").encode("utf-8")

        inputs = {
            "messages": [HumanMessage(content=request.input)],
            "base_url": request.git_url,
        }
        cfg = {"configurable": {"thread_id": str(uuid.uuid4())}, "callbacks": [callback_handler, langfuse_callback_handler]}

        # Choose the best available stream API, but iterate with one unified loop
        events_iter = (
            graph.astream_events(inputs, config=cfg, version="v1")
            if getattr(graph, "astream_events", None)
            else graph.astream_log(inputs, config=cfg)
        )

        async for event in events_iter:
            try:                
                obj = event
                if getattr(obj, "event", None) == "on_tool_start" and getattr(obj, "name", None) == "human_assistance":
                    print("gotcha")
                    obj = {
                        "event": "on_tool_start", 
                        "tool_name": "human_assistance", 
                        "langgrah_node": "tools", 
                        "data": obj.data
                    }
                if obj["event"] == "on_chat_model_stream":
                    print(obj)
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, "content"):
                        content = chunk.content
                        if content:
                            # Serialize the content directly to NDJSON
                            obj = {
                                "data": content,
                            }
                            # yield (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")                
                yield (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
            except Exception as e:
                print(e)
                continue

    return StreamingResponse(
        ndjson_stream(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
        },
    )