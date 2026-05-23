import asyncio
import json

from typing import Dict, Any

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

server = Server("trader-mcp")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="gather_market_data",
            description="Gather current market data for a given asset including price, volume, and trend.",
            inputSchema={
                "type": "object",
                "properties": {
                    "asset": {
                        "type": "string",
                        "description": "The crypto asset symbol (e.g., BTC, ETH)",
                        "default": "BTC"
                    }
                },
                "required": ["asset"],
            },
        ),
        types.Tool(
            name="analyze_sentiment",
            description="Analyze the current market sentiment for crypto assets, returning a score and summary.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="analyze_technicals",
            description="Analyze technical indicators like RSI and MACD.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="execute_trade",
            description="Execute a trade based on a proposed trade strategy decision.",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposed_trade": {
                        "type": "object",
                        "description": "The details of the trade to execute, must include 'action' (BUY/SELL/HOLD), 'amount', and 'asset'.",
                        "properties": {
                            "action": {"type": "string"},
                            "amount": {"type": "number"},
                            "asset": {"type": "string"}
                        },
                        "required": ["action", "amount", "asset"]
                    }
                },
                "required": ["proposed_trade"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if name == "gather_market_data":
        asset = arguments.get("asset", "BTC") if arguments else "BTC"
        market_data = {
            "price": 50000.0,
            "volume": 1200,
            "trend": "up"
        }
        return [types.TextContent(type="text", text=json.dumps({"market_data": market_data}))]

    elif name == "analyze_sentiment":
        sentiment_data = {
            "score": 0.8,
            "summary": "Bullish news on ETF approval."
        }
        return [types.TextContent(type="text", text=json.dumps({"sentiment_data": sentiment_data}))]

    elif name == "analyze_technicals":
        technical_data = {
            "RSI": 65,
            "MACD": "Bullish crossover"
        }
        return [types.TextContent(type="text", text=json.dumps({"technical_data": technical_data}))]

    elif name == "execute_trade":
        if not arguments or "proposed_trade" not in arguments:
            raise ValueError("Missing 'proposed_trade' argument")
        proposed_trade = arguments["proposed_trade"]
        trade_executed = proposed_trade and proposed_trade.get("action") in ["BUY", "SELL"]
        return [types.TextContent(type="text", text=json.dumps({"trade_executed": trade_executed}))]

    raise ValueError(f"Unknown tool: {name}")


async def run_stdio():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(run_stdio())
