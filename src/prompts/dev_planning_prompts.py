from .base_prompts import BasePrompt
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate

class DevPlanningPrompt(BasePrompt):
    pass

dev_planning_prompts_v1 = DevPlanningPrompt(
    creator="Jerry",
    date_created=datetime(year=2025, month=8, day=8),
    description="Plan the development of the project",
    prompt=ChatPromptTemplate(
        [
        ("system", """
You are a software architect. Create a development plan based on the given requirements and the chosen tech stack.

<planning_rules>
- Output MUST be valid JSON. No extra text.
- Provide two levels: "main_goals" (epics) and "sub_goals" (stories/tasks per epic).
- Each sub-goal MUST include: owner ("FE" or "BE"), rationale, estimated_points (int), dependencies (ids), and acceptance_criteria (1~3 bullets).
- Respect non-functional requirements when prioritizing.
        - Use only the provided stack in {{language}}/{{framework}}/{{library}}.
        </planning_rules>

        <output_schema>
        {{
          "main_goals": [
            {{"id": "G1", "title": "Auth & User Management", "priority": "P1"}},
            {{"id": "G2", "title": "Core Domain APIs", "priority": "P1"}}
          ],
          "sub_goals": {{
            "G1": [
              {{
                "id": "G1-S1",
                "title": "Login/Logout (JWT)",
                "owner": "BE",
                "rationale": "Security & session handling",
                "estimated_points": 5,
                "dependencies": [],
                "acceptance_criteria": [
                  "Login returns JWT on valid creds",
                  "401 on invalid creds"
                ]
              }},
              {{
                "id": "G1-S2",
                "title": "React login page",
                "owner": "FE",
                "estimated_points": 3,
                "dependencies": ["G1-S1"],
                "acceptance_criteria": [
                  "Form validation",
                  "Stores token via Zustand"
                ]
              }}
            ]
          }}
        }}
        </output_schema>
"""),
    ("human", """
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

<stack>
language: {language}
framework: {framework}
library: {library}
</stack>

Return ONLY the JSON.
""")
])
)






dev_planning_prompts_v2 = DevPlanningPrompt(
    creator="Jerry",
    date_created=datetime(year=2025, month=8, day=8),
    description="Plan the development of the project",
    prompt=ChatPromptTemplate(
        [
        ("system", """
You are a senior software architect and delivery planner. 
Produce a FULL execution-ready plan that downstream nodes can implement without guessing.

<inputs>
- Functional requirements, user scenarios, process flow, domain entities, non-functional requirements
- Chosen stack (language/framework/library). You MUST use ONLY these.
</inputs>

<granularity_contract>
- main_goals (EPICs): 3–6 items, each with clear rationale and priority (P1|P2|P3).
- sub_goals (TASKs): For every EPIC, 6–12 tasks. Each task must be specific, implementable in <= 2 days.
- Every BE task must specify API/model/storage impact. Every FE task must specify page/component/state changes.
- No vague items like "set up basic stuff". Be explicit.
</granularity_contract>

<comprehensiveness_rules>
- Return ONLY valid JSON (no extra text), matching <output_schema>.
- Respect the chosen stack strictly; if something is not listed, leave it empty.
- Derive priorities using non-functional requirements (security/latency/availability).
- Enforce correct dependency ordering: BE endpoints/models before FE consumption; schema before migrations; migrations before runtime.
- Include enough detail for CI/CD and tests to run green without extra context.
</comprehensiveness_rules>

<output_schema>
{{
  "main_goals": [
    {{
      "id": "G1",
      "title": "Authentication & User Management",
      "rationale": "Access control aligned to security NFRs",
      "priority": "P1",
      "story_points_total": 0
    }}
  ],
  "sub_goals": {{
    "G1": [
      {{
        "id": "G1-S1",
        "title": "Login/Logout API (JWT)",
        "owner": "BE",
        "stack": {{"language": [], "framework": [], "library": []}},
        "description": "Implement stateless auth with JWT including token refresh.",
        "estimated_points": 5,
        "dependencies": [],
        "acceptance_criteria": [
          "POST /auth/login returns JWT (200) on valid creds; 401 otherwise",
          "POST /auth/refresh returns new token with valid refresh token",
          "Blacklist/rotation rules documented"
        ],
        "interfaces": [
          {{"type":"REST","method":"POST","path":"/auth/login","status":[200,401]}},
          {{"type":"REST","method":"POST","path":"/auth/refresh","status":[200,401,403]}}
        ],
        "deliverables": ["API spec (OpenAPI snippet)", "Unit tests", "Integration tests"],
        "sequence": 1
      }}
    ]
  }},

  "directory_tree": [
    "repo/",
    "repo/frontend/",
    "repo/frontend/src/components/",
    "repo/frontend/src/pages/",
    "repo/frontend/src/store/  (state with Zustand if React)",
    "repo/backend/",
    "repo/backend/app/routers/",
    "repo/backend/app/models/",
    "repo/backend/app/schemas/",
    "repo/backend/tests/",
    "repo/infra/ci/",
    "repo/infra/scripts/"
  ],

  "bootstrap_instructions": {{
    "frontend": [
      "Shell commands to scaffold the FE project with the chosen framework",
      "Install and wire state mgmt (e.g., Zustand) and HTTP client (Axios) if applicable"
    ],
    "backend": [
      "Shell commands to scaffold the BE project with the chosen framework",
      "Add ORM and create initial app module (e.g., FastAPI router or Spring Boot controller)"
    ]
  }},

  "api_spec": [
    {{
      "path": "/auth/login",
      "method": "POST",
      "summary": "Authenticate user",
      "request": {{"body": {{"username":"string","password":"string"}}}},
      "responses": {{
        "200": {{"json": {{"access_token":"string","refresh_token":"string"}}}},
        "401": {{"json": {{"error":"invalid_credentials"}}}}
      }}
    }}
  ],

  "data_model": [
    {{
      "entity": "User",
      "table": "users",
      "fields": [
        {{"name":"id","type":"UUID","pk":true}},
        {{"name":"email","type":"VARCHAR(255)","unique":true}},
        {{"name":"password_hash","type":"VARCHAR(255)"}},
        {{"name":"created_at","type":"TIMESTAMP"}}
      ],
      "indexes": [["email"]],
      "relations": []
    }}
  ],

  "migrations": [
    {{
      "id": "001_init_users",
      "changes": [
        "create table users(...columns as per data_model...)",
        "unique index on email"
      ]
    }}
  ],

  "seed_data": [
    {{
      "entity":"User",
      "rows":[
        {{"email":"admin@example.com","password_hash":"<hashed>"}}
      ]
    }}
  ],

  "env_vars": [
    {{"name":"APP_ENV","required":true,"example":"dev"}},
    {{"name":"DB_URL","required":true,"example":"mysql://user:pass@host/db"}},
    {{"name":"JWT_SECRET","required":true,"example":"<32+ chars>"}}
  ],

  "test_plan": {{
    "unit": [
      "Auth service: token issuance/verification",
      "Validators and data mappers"
    ],
    "integration": [
      "Login flow end-to-end",
      "DB migrations apply cleanly and rollback works"
    ],
    "e2e": [
      "User can sign in on FE, token stored safely, protected routes accessible"
    ],
    "coverage_targets": {{
      "lines": 0.8,
      "branches": 0.7
    }}
  }},

  "ci_cd": {{
    "pipeline": [
      "Install deps",
      "Static checks (lint, type-check if any)",
      "Run unit + integration tests",
      "Build artifacts",
      "Package & push image",
      "Run DB migrations",
      "Deploy to environment"
    ],
    "checks": [
      "Fail if coverage below targets",
      "Block merge if tests fail"
    ]
  }},

  "milestones": [
    {{"name":"M1 - Auth baseline","target_week":"W2"}},
    {{"name":"M2 - Core domain APIs","target_week":"W3"}}
  ],

  "risks": [
    {{"id":"R1","risk":"Schema drift with evolving requirements","mitigation":"Migration discipline + ADRs"}},
    {{"id":"R2","risk":"JWT revocation complexity","mitigation":"Short TTL + refresh + server-side blacklisting if needed"}}
  ],

  "assumptions": [
    "Single database for MVP",
    "Email is unique user identifier"
  ],

  "open_questions": [
    "Do we require SSO or social login?",
    "What is the target RPS and p95 latency requirement?"
  ],

  "delivery_plan": [
    {{
      "sprint": 1,
      "goals": ["G1 partial completion"],
      "owners": [
        {{"name":"FE-1","focus":["G1 FE tasks"]}},
        {{"name":"BE-1","focus":["G1 BE tasks"]}}
      ]
    }},
    {{
      "sprint": 2,
      "goals": ["G2 majority completion"],
      "owners": [
        {{"name":"FE-1","focus":["G2 FE tasks"]}},
        {{"name":"BE-1","focus":["G2 BE tasks"]}}
      ]
    }}
  ],

  "definitions_of_done": [
    "All acceptance criteria satisfied",
    "Code reviewed and merged",
    "Tests green, coverage targets met",
    "CI/CD pipeline passes, deployment verified",
    "Runbook updated"
  ],

  "runbooks": [
    {{
      "name":"User onboarding incident",
      "steps":[
        "Check API health /auth/login, /auth/refresh",
        "Inspect logs for auth errors",
        "Invalidate compromised tokens if any",
        "Create incident ticket with timeline"
      ]
    }}
  ],

  "coding_standards": [
    "Consistent error model for APIs",
    "Avoid shared mutable state; use store slices (FE) and services (BE)",
    "SQL/ORM migrations must be idempotent and reversible"
  ]
}}
</output_schema>
"""),
    ("human", """
<context>
Requirements:
{requirements}

User Scenarios:
{user_scenarios}

Process Flow:
{processes}

Domain Entities:
{domain_entities}

Non-functional Requirements:
{non_functional_reqs}

Chosen Stack:
language={language}
framework={framework}
library={library}
</context>

Constraints:
- Use ONLY the stacks in "Chosen Stack".
- Fill EVERY section of <output_schema> with project-specific, actionable details.
- For each EPIC, include 6–12 concrete tasks with BE-first dependencies when applicable.
- Return ONLY the JSON object per <output_schema>.
""")
])
)

dev_planning_prompts_v3 = DevPlanningPrompt(
    creator="Jerry",
    date_created=datetime(year=2025, month=8, day=8),
    description="A lightweight development plan for testing purposes.",
    prompt=ChatPromptTemplate(
        [
        ("system", """
You are a software architect. Create a concise development plan based on the given requirements and tech stack.

<planning_rules>
- Output MUST be a valid JSON object.
- Provide two main keys: "main_goals" and "sub_goals".
- "main_goals" should be a list of 2-3 high-level objectives (epics).
- For each main goal, create 2-4 specific "sub_goals" (tasks).
- Each sub-goal must have an "id", "title", and "owner" ("FE" or "BE").
- Keep all descriptions brief and to the point.
</planning_rules>

<output_schema>
{{
  "main_goals": [
    {{"id": "G1", "title": "Setup User Authentication"}},
    {{"id": "G2", "title": "Develop Core API"}}
  ],
  "sub_goals": {{
    "G1": [
      {{"id": "G1-S1", "title": "Implement JWT-based login API", "owner": "BE"}},
      {{"id": "G1-S2", "title": "Create a simple login page", "owner": "FE"}}
    ],
    "G2": [
      {{"id": "G2-S1", "title": "Define main data models", "owner": "BE"}},
      {{"id": "G2-S2", "title": "Create basic CRUD endpoints", "owner": "BE"}}
    ]
  }}
}}
</output_schema>
"""),
    ("human", """
<context>
Requirements:
{requirements}

User Scenarios:
{user_scenarios}

Process Flow:
{processes}

Domain Entities:
{domain_entities}

Non-functional Requirements:
{non_functional_reqs}

Chosen Stack:
language={language}
framework={framework}
library={library}
</context>

Constraints:
- Return ONLY the JSON object matching the <output_schema>.
- Focus on creating a minimal, valid plan for workflow testing.
""")
])
)
