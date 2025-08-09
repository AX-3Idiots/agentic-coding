from fastapi import FastAPI
from contextlib import asynccontextmanager
import os
from ..services.github_service import get_github_app_token

@asynccontextmanager
async def git_config(app: FastAPI):
    """
    Defines tasks to be performed when the application starts and ends.
    """
    print("Application starting! Loading GitHub configuration.")
    github_token = get_github_app_token()
    os.environ["GH_APP_TOKEN"] = github_token
    os.environ["TARGET_REPO_URL"] = os.environ.get("GIT_URL")

    yield

    print("Application shutting down!")