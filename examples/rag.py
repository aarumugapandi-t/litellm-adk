"""Retrieval-Augmented Generation (RAG) Example.

Demonstrates indexing documents with InMemoryVectorStore, retrieving relevant context,
and injecting it into the Agent prompt.
"""

import asyncio
import os
from litellm_adk import Agent, InMemoryVectorStore, RetrievalConfig, Retriever


async def main():
    # 1. Create vector store and retriever with custom top_k
    vector_store = InMemoryVectorStore()
    retriever = Retriever(
        vector_store=vector_store,
        config=RetrievalConfig(top_k=2),
    )

    # 2. Index domain knowledge documents
    documents = [
        "Company Travel Policy: All international flights exceeding 6 hours are eligible for Business Class booking with VP approval.",
        "Meal Reimbursement: Daily allowance for employee meals during business trips is capped at $85 per day with itemized receipts.",
        "Remote Work Guideline: Employees can work remotely from another country for up to 30 days per calendar year.",
        "Equipment Policy: The company provides a $1,000 home office hardware stipend renewed every two years.",
    ]

    print("Indexing corporate policy documents into vector store...")
    await retriever.add_documents(documents)

    # 3. Create agent equipped with the retriever
    agent = Agent(
        name="policy_expert",
        model=os.getenv("LITELLM_MODEL", "openai/gpt-4o"),
        system_prompt="You are a corporate HR & travel policy assistant. Always ground your answers in the retrieved policy documents.",
        retriever=retriever,
    )

    query = "Can I book a business class seat for a 7-hour flight to London, and what is my meal budget?"
    print(f"\nUser Query: {query}\n")

    result = await agent.run(query)
    print(f"Agent Response:\n{result.text}\n")


if __name__ == "__main__":
    asyncio.run(main())
