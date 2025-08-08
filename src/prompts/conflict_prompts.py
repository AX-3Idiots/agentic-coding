# /prompts/resolver_prompts.py

from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from .base_prompts import BasePrompt

conflict_prompt_template = ChatPromptTemplate([
    ("system",
     """You are a 20-year experienced Principal Software Architect. Your mission is to resolve a Git merge conflict.

Analyze the following conflict in the file `{file_path}`.

Here is the full content of the conflicted file:
```
{conflict_content}
```

Your Task:
1. Analyze the changes from both sides of the conflict.
2. Produce a single, final, and correct version of the code that intelligently merges the logic.
3. The final code MUST NOT include any `<<<<<<<`, `=======`, `>>>>>>>` conflict markers.

Output your response in the following JSON format ONLY:
{{"final_code": "The fully resolved and merged code block goes here."}}
"""
    ),
    ("human", "Please resolve the merge conflict in the file `{file_path}`.")
])

# 프롬프트에 메타데이터를 추가하여 관리합니다.
conflict_prompts = BasePrompt(
    date_created=datetime.now(),
    description="conflict_prompt",
    creator="Anthony", # 또는 실제 작성자 이름
    prompt=conflict_prompt_template
)
