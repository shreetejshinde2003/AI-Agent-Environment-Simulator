import asyncio

from app.agents.llm_client import call_llm


async def main():
    response = await call_llm(
        prompt="Introduce yourself in one sentence."
    )

    print("\nModel:", response.model)
    print("Input Tokens:", response.input_tokens)
    print("Output Tokens:", response.output_tokens)
    print("Time:", response.response_time_seconds)
    print("\nResponse:")
    print(response.text)


asyncio.run(main())