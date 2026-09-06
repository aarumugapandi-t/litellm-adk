"""Multi-Agent Coordination Example.

Demonstrates wrapping specialized worker agents into tools and coordinating them
via a Supervisor agent.
"""

import asyncio
import os
from litellm_adk import Agent, Supervisor, tool


# Specialized tools for worker agents
@tool
def search_python_docs(query: str) -> str:
    """Mock search for Python language documentation."""
    return f"Python Docs for '{query}': asyncio.gather runs awaitable objects concurrently."


@tool
def check_code_syntax(code: str) -> str:
    """Checks Python code for basic syntax validity."""
    try:
        compile(code, "<string>", "exec")
        return "Syntax valid: No compilation errors detected."
    except SyntaxError as e:
        return f"SyntaxError: {e}"


async def main():
    model_name = os.getenv("LITELLM_MODEL", "openai/gpt-4o")

    # 1. Specialized Researcher Agent
    researcher = Agent(
        name="Researcher",
        model=model_name,
        description="Researches technical documentation and language APIs.",
        system_prompt="You are a research specialist. Find technical details and explain them clearly.",
        tools=[search_python_docs],
    )

    # 2. Specialized Code Reviewer Agent
    reviewer = Agent(
        name="Reviewer",
        model=model_name,
        description="Analyzes code for bugs, syntax errors, and style issues.",
        system_prompt="You are a senior code reviewer. Verify Python code correctness.",
        tools=[check_code_syntax],
    )

    # 3. Supervisor Agent coordinating the team
    supervisor = Supervisor(
        name="Supervisor",
        agents=[researcher, reviewer],
        model=model_name,
        system_prompt=(
            "You are a project supervisor. Coordinate tasks across your team. "
            "Use the Researcher to look up documentation and the Reviewer to inspect code."
        ),
    )

    task = "Look up how to run concurrent tasks in Python using asyncio, write a short snippet, and have it reviewed."
    print(f"Task: {task}\n")

    result = await supervisor.ainvoke(task)
    print(f"Supervisor Final Report:\n{result.text}\n")


if __name__ == "__main__":
    asyncio.run(main())
