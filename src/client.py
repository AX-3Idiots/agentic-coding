import requests

response = requests.post(
    "http://localhost:8000/invoke-workflow",
    json={"input": "로그인 기능 하나 만들어줘", "git_url": "https://github.com/AX-3Idiots/agentic_coding_test.git"}
)

