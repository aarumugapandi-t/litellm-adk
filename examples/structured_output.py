"""Structured Output Example.

Demonstrates extracting strongly typed Pydantic models directly from agent runs
with automated schema enforcement and self-repair capabilities.
"""

import asyncio
import os
from typing import List
from pydantic import BaseModel, Field
from litellm_adk import Agent, LiteLLMAgent


# 1. Define the desired structured output schema
class TechStackAnalysis(BaseModel):
    project_name: str = Field(description="Name of the software project or library.")
    primary_language: str = Field(description="Primary programming language used.")
    core_dependencies: List[str] = Field(description="Key packages or dependencies.")
    key_features: List[str] = Field(description="Top architectural features.")
    production_readiness_score: int = Field(ge=1, le=10, description="Readiness score from 1 to 10.")


async def main():
    agent = Agent(
        model="openrouter/mistralai/ministral-3b-2512",
        api_key="sk-1234",
        base_url="http://localhost:9000/v1",
        system_prompt="You are a senior software architect specializing in codebase evaluation.",
    )

    prompt = (
        "Analyze the FastAPI web framework. Identify its language, major dependencies (like Starlette, Pydantic), "
        "key features (automatic OpenAPI, async endpoints, dependency injection), and score its production readiness."
    )

    print(f"Prompt:\n{prompt}\n")

    # 2. Run agent requesting structured output model
    result = await agent.ainvoke(prompt, response_model=TechStackAnalysis)

    # 3. Access validated Pydantic model
    analysis: TechStackAnalysis = result.structured

    print("--- Structured Pydantic Output ---")
    print(f"Project Name: {analysis.project_name}")
    print(f"Language:     {analysis.primary_language}")
    print(f"Dependencies: {', '.join(analysis.core_dependencies)}")
    print(f"Key Features: {', '.join(analysis.key_features)}")
    print(f"Readiness:    {analysis.production_readiness_score}/10")


if __name__ == "__main__":
    asyncio.run(main())
