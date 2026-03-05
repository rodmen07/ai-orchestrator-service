from typing import List

from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=500)
    # Tasks already assigned to this goal — the AI will avoid suggesting duplicates.
    existing_tasks: List[str] = Field(default_factory=list)
    # Tasks from other goals — gives broader context about ongoing work.
    context_tasks: List[str] = Field(default_factory=list)


class PlanResponse(BaseModel):
    tasks: List[str]


class HealthResponse(BaseModel):
    status: str
