import asyncio

from app.agents.research_agent import ResearchAgent


async def main():

    agent = ResearchAgent()

    result = await agent.process(
        directive="Research the advantages of remote work.",
        context={}
    )

    print(result)


asyncio.run(main())