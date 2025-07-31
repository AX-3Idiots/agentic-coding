# agentic-coding

This project is a FastAPI application managed with `uv`.

## How to Start Project

To install and sync the dependencies for this project, run the following command in your terminal:

```bash
uv sync
```

## How to Run the Server

To run the FastAPI development server, use the following command:

```bash
uv uvicorn src.main:app --reload
```

## Packages

This project uses the following packages:

- boto3>=1.39.17
- docker>=7.1.0
- fastapi>=0.116.1
- langchain>=0.3.27
- langchain-aws>=0.2.29
- langgraph>=0.6.2
- pydantic>=2.11.7
- uvicorn>=0.35.0

