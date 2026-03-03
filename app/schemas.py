from typing import List

from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=1000)


class PlanResponse(BaseModel):
    tasks: List[str]


class HealthResponse(BaseModel):
    status: str
