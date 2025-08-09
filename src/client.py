import requests

response = requests.post(
    "http://localhost:8000/invoke-workflow",
    json={"input": "hi"}
)

