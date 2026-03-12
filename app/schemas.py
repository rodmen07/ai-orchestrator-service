from typing import List

from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=500)
    # Tasks already assigned to this goal — the AI will avoid suggesting duplicates.
    existing_tasks: List[str] = Field(default_factory=list)
    # Tasks from other goals — gives broader context about ongoing work.
    context_tasks: List[str] = Field(default_factory=list)
    # Optional refinement instructions from the user (e.g. "focus on testing", "make them smaller").
    feedback: str = Field(default="", max_length=500)
    # How many milestones to generate. Defaults to 16.
    target_count: int = Field(default=16, ge=12, le=20)


class PlanResponse(BaseModel):
    tasks: List[str]


class AgentRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    bearer_token: str = Field(min_length=1)


class AgentResponse(BaseModel):
    result: str


class HealthResponse(BaseModel):
    status: str
