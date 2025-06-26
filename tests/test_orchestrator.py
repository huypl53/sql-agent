import asyncio
import logging

from orchestrator import EnhancementGraphBuilder
from sql_qa.prompt.template import Role
from sql_qa.schema.graph import EnhancementState

def test_enhancement_graph():
    def get_weather(state: EnhancementState) -> str:
        return "Today is sunny with a high of 25°C and a low of 15°C."

    def get_news(state: EnhancementState) -> str:
        return "Today's top news: Local team wins championship!"

    async def get_time(state: EnhancementState) -> str:
        return "The current time is 14:30."

    workflow = EnhancementGraphBuilder(
        tools=[get_weather, get_news, get_time],
    )

    async def run_enhancement():
        result = await workflow.graph.ainvoke(
            {
                "messages": [
                    {
                        "role": Role.USER,
                        "content": "Should I go out now to play football or stay at home to watch TV?",
                    }
                ]
            }
        )
        print(f"Result: {result}")

    asyncio.run(run_enhancement())

