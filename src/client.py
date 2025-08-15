import requests

response = requests.post(
    "http://localhost:8000/invoke-workflow",
    json={"input": "Create a timer app  only for frontend", "git_url": "https://github.com/AX-3Idiots/agentic_coding_test.git"}
)

