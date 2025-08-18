"""Prompt Module."""

from .role_allocate_prompts import *
from .architect_agent_prompts import *
from .se_agent_prompts import *
from .resolver_prompts import *
from .conflict_prompts import *
from .frontend_architect_agent_prompts import *
from .backend_architect_agent_prompts import *
from .solution_owner_prompts import *

__all__ = [
    "solution_owner_prompts_v1",
    "solution_owner_prompts_v2",
    "role_allocate_prompts",
    "role_allocate_prompts_v2",
    "architect_agent_prompts",
    "se_agent_prompts",
    "se_agent_prompts_specs_frontend",
    "resolver_prompts",
    "conflict_prompts",
    "frontend_architect_agent_prompts",
    "backend_architect_agent_prompts",
]

