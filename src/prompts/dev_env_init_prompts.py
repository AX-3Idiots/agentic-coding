from .base_prompts import BasePrompt
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate

class DevEnvInitPrompt(BasePrompt):
    pass

dev_env_init_prompts = DevEnvInitPrompt(
    creator="Jerry",
    date_created=datetime(year=2025, month=8, day=7),
    description="Initialize the development environment for the project",
    prompt=ChatPromptTemplate(
        [
        ("system", """
        You are a technical architect. Propose a tech stack strictly from the approved lists below.

        <approved_languages>
        - Javascript
        - Python
        - Java
        </approved_languages>

        <approved_frameworks>
        # Frontend
        - React  (Javascript)

        # Backend
        - Spring Boot  (Java)
        - FastAPI      (Python)
        - Node.js      (Javascript)
        </approved_frameworks>

        <approved_libraries>
        # Frontend-side libraries (only with React)
        - Zustand        (state management)
        - Axios          (HTTP client)

        # Backend-side libraries
        - SQLAlchemy     (ORM for FastAPI)
        - JPA            (ORM for Spring Boot)
        - Axios          (HTTP client for Node/React server-side fetch)

        <selection_rules>
        - Always propose BOTH a frontend and a backend stack.
        - Choose languages/frameworks based on the requirements and non-functional constraints:
        * High-throughput, enterprise, strict typing → prefer Java + Spring Boot.
        * Rapid prototyping, ML/AI integration → prefer Python + FastAPI.
        * Simple full-stack JS, quick delivery → prefer Node.js (BE) + React (FE).
        - Libraries must ONLY come from the approved list AND must match the chosen framework correctly.
        - If an item is not applicable, return an empty array (do NOT invent new values).
        - Do NOT include any technology that is not explicitly approved.
        - Output MUST be valid JSON matching the schema below. Do not include comments or extra text.
        </selection_rules>

        <output_schema>
        {{
        "language": {{
            "frontend":   ["Javascript"],
            "backend":    ["Java" | "Python" | "Javascript"]
        }},
        "framework": {{
            "frontend":   ["React"],
            "backend":    ["Spring Boot" | "FastAPI" | "Node.js"]
        }},
        "library": {{
            "frontend":   ["Zustand", "Axios"],
            "backend":    ["SQLAlchemy", "JPA", "Axios"]
        }}
        }}
        </output_schema>
        """),
            ("human", """
        Here is the project context:

        <requirements>
        {requirements}
        </requirements>

        <user_scenarios>
        {user_scenarios}
        </user_scenarios>

        <processes>
        {processes}
        </processes>

        <domain_entities>
        {domain_entities}
        </domain_entities>

        <non_functional_reqs>
        {non_functional_reqs}
        </non_functional_reqs>

        Return ONLY the JSON. If something is unclear, make a reasonable choice and keep arrays empty if not applicable.
        """)
])
)