import asyncio

async def get_llm_response(query: str) -> str:
    await asyncio.sleep(10)

    if query.lower() == "fail":
        raise ValueError(f"LLM query rejected for user input was: {query}")
    
    return f"This is a mock response to: {query}"