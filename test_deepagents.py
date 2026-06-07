import asyncio
from backend.agents import trading_graph

async def main():
    print("Graph:", trading_graph.nodes)

if __name__ == "__main__":
    asyncio.run(main())
