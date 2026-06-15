from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import StateGraph, END, add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from deepagents import create_deep_agent
from pydantic import BaseModel, Field
import os
import json
import sys
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from contextlib import AsyncExitStack

async def call_mcp_tool(tool_name: str, arguments: dict):
    async with AsyncExitStack() as stack:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trader-mcp", "server.py")]
        )
        transport = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(transport[0], transport[1]))
        await session.initialize()
        result = await session.call_tool(tool_name, arguments=arguments)
        return json.loads(result.content[0].text)

# Define the state for the LangGraph
class AgentState(TypedDict):
    asset: str
    market_data: Optional[dict]
    sentiment_data: Optional[dict]
    technical_data: Optional[dict]
    strategy_decision: Optional[str]
    proposed_trade: Optional[dict]
    risk_assessment: Optional[str]
    trade_executed: Optional[bool]
    messages: Annotated[list, add_messages]

# Tools
@tool
async def gather_market_data(asset: str) -> dict:
    """Gathers market data for a specific asset (e.g. BTC)."""
    data = await call_mcp_tool("gather_market_data", {"asset": asset})
    return data["market_data"]

@tool
async def analyze_sentiment() -> dict:
    """Analyzes market sentiment data."""
    data = await call_mcp_tool("analyze_sentiment", {})
    return data["sentiment_data"]

@tool
async def analyze_technicals() -> dict:
    """Analyzes technical indicators for the market."""
    data = await call_mcp_tool("analyze_technicals", {})
    return data["technical_data"]

class StrategyOutput(BaseModel):
    action: str = Field(description="Trading action to take: BUY, SELL, or HOLD")
    amount: float = Field(description="Amount to trade (0.0 to 1.0)")
    reasoning: str = Field(description="Your reasoning for this action")

async def formulate_strategy(state: AgentState):
    asset = state.get('asset', 'BTC')
    system_prompt = f"""
    You are an expert Crypto Trading Strategist.
    Your task is to analyze the market for the asset: {asset}.
    You MUST use your tools to gather market data, sentiment, and technicals.
    
    Based on the data you gather, propose a trading action (BUY, SELL, HOLD), the amount (0 to 1), and a brief reasoning.
    Provide your output strictly matching the required schema.
    """
    
    agent = create_deep_agent(
        model="google_genai:gemini-1.5-pro",
        tools=[gather_market_data, analyze_sentiment, analyze_technicals],
        system_prompt=system_prompt,
    )

    # We ask the agent to formulate the strategy and return JSON
    try:
        # Ask for structured output using the model's native capability or parsing.
        # Apply the inner 4-iteration limit directly to the agent's invoke call
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content="Gather data and output your strategy decision as a JSON object matching the StrategyOutput schema: {\"action\": \"...\", \"amount\": ...., \"reasoning\": \"...\"}")]},
            {"recursion_limit": 4}
        )

        final_message = result["messages"][-1].content
        
        # Extract the gathered data from the message history to populate the outer state
        market_data = None
        sentiment_data = None
        technical_data = None
        
        for msg in result.get("messages", []):
            if isinstance(msg, ToolMessage):
                if msg.name == "gather_market_data":
                    try:
                        market_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    except:
                        pass
                elif msg.name == "analyze_sentiment":
                    try:
                        sentiment_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    except:
                        pass
                elif msg.name == "analyze_technicals":
                    try:
                        technical_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    except:
                        pass

        # Try to parse as JSON or look for the fields
        try:
            # strip markdown blocks if present
            if "```json" in final_message:
                json_str = final_message.split("```json")[1].split("```")[0].strip()
            elif "```" in final_message:
                json_str = final_message.split("```")[1].split("```")[0].strip()
            else:
                json_str = final_message
            parsed = json.loads(json_str)
            action = parsed.get("action", "HOLD")
            amount = float(parsed.get("amount", 0.0))
            reasoning = parsed.get("reasoning", "")
        except:
            # Fallback
            action = "HOLD"
            amount = 0.0
            reasoning = final_message

        proposed_trade = {
            "action": action,
            "amount": amount,
            "asset": asset
        }

        # Populate outer state
        return {
            "strategy_decision": reasoning,
            "proposed_trade": proposed_trade,
            "market_data": market_data,
            "sentiment_data": sentiment_data,
            "technical_data": technical_data
        }
    except Exception as e:
         return {"strategy_decision": f"Error: {e}", "proposed_trade": {"action": "HOLD", "amount": 0.0, "asset": asset}}


async def evaluate_risk(state: AgentState):
    proposed_trade = state.get("proposed_trade")
    if not proposed_trade or proposed_trade.get("action") == "HOLD":
        return {"risk_assessment": "No trade to evaluate.", "proposed_trade": proposed_trade}
        
    system_prompt = f"""
    You are a strict Risk Manager. Evaluate this proposed trade:
    Trade: {proposed_trade}
    Market Context: {state.get('market_data')}
    
    You can use tools to gather more market context if you need to.
    Approve or reject the trade based on standard risk management principles.
    """

    agent = create_deep_agent(
        model="google_genai:gemini-1.5-pro",
        tools=[gather_market_data, analyze_sentiment, analyze_technicals],
        system_prompt=system_prompt,
    )

    try:
        # Apply the inner 4-iteration limit directly to the agent's invoke call
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content="Evaluate the risk and output your decision as JSON: {\"decision\": \"APPROVE\" or \"REJECT\", \"reasoning\": \"...\"}")]},
            {"recursion_limit": 4}
        )
        final_message = result["messages"][-1].content

        try:
            if "```json" in final_message:
                json_str = final_message.split("```json")[1].split("```")[0].strip()
            elif "```" in final_message:
                json_str = final_message.split("```")[1].split("```")[0].strip()
            else:
                json_str = final_message
            parsed = json.loads(json_str)
            decision = parsed.get("decision", "REJECT").upper()
            reasoning = parsed.get("reasoning", final_message)
        except:
             decision = "REJECT" if "REJECT" in final_message.upper() else "APPROVE"
             reasoning = final_message

        if decision == "REJECT":
            proposed_trade["action"] = "HOLD"
            proposed_trade["amount"] = 0.0
        return {"risk_assessment": reasoning, "proposed_trade": proposed_trade}
    except Exception as e:
        proposed_trade["action"] = "HOLD"
        return {"risk_assessment": f"Error: {e}", "proposed_trade": proposed_trade}

checkpointer = MemorySaver()

@tool
async def perform_trade(proposed_trade: dict) -> dict:
    """Executes a trade via the MCP tool. Call this tool to perform the execution."""
    data = await call_mcp_tool("execute_trade", {"proposed_trade": proposed_trade})
    return data

execution_system_prompt = """
You are an Execution Agent. Your only job is to execute the trade that has been proposed.
You MUST call the `perform_trade` tool with the proposed trade details you receive in the user message.
After executing the trade, return the trade_executed status from the tool.
"""

execution_agent = create_deep_agent(
    model="google_genai:gemini-1.5-pro",
    tools=[perform_trade],
    system_prompt=execution_system_prompt,
    interrupt_on={"perform_trade": True},
    checkpointer=checkpointer
)

def format_trade_request(state: AgentState):
    proposed_trade = state.get("proposed_trade")
    if not proposed_trade or proposed_trade.get("action") == "HOLD":
        return {"trade_executed": False}

    return {
        "messages": [HumanMessage(content=f"Execute the proposed trade: {proposed_trade}")]
    }

def extract_trade_result(state: AgentState):
    trade_executed = False

    if not state.get("proposed_trade") or state.get("proposed_trade").get("action") == "HOLD":
         return {"trade_executed": False}

    for msg in state.get("messages", []):
        if isinstance(msg, ToolMessage) and msg.name == "perform_trade":
            try:
                data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                trade_executed = data.get("trade_executed", False)
            except:
                pass

    return {"trade_executed": trade_executed}

def should_execute_trade(state: AgentState) -> str:
    proposed_trade = state.get("proposed_trade")
    if not proposed_trade or proposed_trade.get("action") == "HOLD":
        return "extract_trade_result"
    return "execute_trade"

def build_trading_graph():
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("formulate_strategy", formulate_strategy)
    workflow.add_node("evaluate_risk", evaluate_risk)
    workflow.add_node("format_trade_request", format_trade_request)
    workflow.add_node("execute_trade", execution_agent)
    workflow.add_node("extract_trade_result", extract_trade_result)
    
    # Define edges
    workflow.set_entry_point("formulate_strategy")
    workflow.add_edge("formulate_strategy", "evaluate_risk")
    workflow.add_edge("evaluate_risk", "format_trade_request")

    workflow.add_conditional_edges(
        "format_trade_request",
        should_execute_trade,
        {
            "execute_trade": "execute_trade",
            "extract_trade_result": "extract_trade_result"
        }
    )

    workflow.add_edge("execute_trade", "extract_trade_result")
    workflow.add_edge("extract_trade_result", END)
    
    return workflow.compile(checkpointer=checkpointer)

trading_graph = build_trading_graph()
