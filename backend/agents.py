from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import StateGraph, END
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
        model="google:gemini-1.5-pro",
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
        
    market_data = state.get('market_data')
    sentiment_data = state.get('sentiment_data')
    technical_data = state.get('technical_data')
    strategy_decision = state.get('strategy_decision')
    
    context = f"""
    Proposed Trade: {proposed_trade}
    Strategy Reasoning: {strategy_decision}
    Market Context: {market_data}
    Sentiment Data: {sentiment_data}
    Technical Data: {technical_data}
    """

    bull_system_prompt = f"""
    You are a Bullish Researcher. Your goal is to advocate for the proposed trade.
    Focus on the positive indicators, growth potential, and favorable market conditions.
    Construct arguments supporting the initiation or continuation of the position.

    Data Context:
    {context}
    """

    bear_system_prompt = f"""
    You are a Bearish Researcher. Your goal is to focus strictly on potential downsides, liquidity traps, and market volatility.
    Provide cautionary insights, questioning the viability of the proposed trade and highlighting possible negative outcomes.

    Data Context:
    {context}
    """

    bull_agent = create_deep_agent(
        model="google:gemini-1.5-pro",
        tools=[],
        system_prompt=bull_system_prompt,
    )

    bear_agent = create_deep_agent(
        model="google:gemini-1.5-pro",
        tools=[],
        system_prompt=bear_system_prompt,
    )

    debate_history = []

    # Max 3 rounds of debate
    for round_num in range(3):
        # Bull Turn
        bull_prompt = "Make your case for why this trade is a good idea."
        if debate_history:
            bull_prompt = f"The Bear said: '{debate_history[-1]}'. Respond to this and make your case for why this trade is a good idea."

        try:
            bull_result = await bull_agent.ainvoke(
                {"messages": [HumanMessage(content=bull_prompt)]},
                {"recursion_limit": 4}
            )
            bull_message = bull_result["messages"][-1].content
            debate_history.append(f"Bull: {bull_message}")
        except Exception as e:
            debate_history.append(f"Bull failed to respond: {e}")
            break

        # Bear Turn
        bear_prompt = f"The Bull said: '{bull_message}'. Respond to this and make your case for why this trade is a bad idea or too risky."
        try:
            bear_result = await bear_agent.ainvoke(
                {"messages": [HumanMessage(content=bear_prompt)]},
                {"recursion_limit": 4}
            )
            bear_message = bear_result["messages"][-1].content
            debate_history.append(f"Bear: {bear_message}")
        except Exception as e:
            debate_history.append(f"Bear failed to respond: {e}")
            break

    debate_transcript = "\\n\\n".join(debate_history)

    risk_manager_system_prompt = f"""
    You are a strict Risk Manager. Your task is to make a final decision on the proposed trade by reviewing the debate between the Bull and Bear researchers.

    Data Context:
    {context}

    Debate Transcript:
    {debate_transcript}

    Approve or reject the trade based on standard risk management principles. You should output your decision as JSON.
    """

    risk_manager_agent = create_deep_agent(
        model="google:gemini-1.5-pro",
        tools=[],
        system_prompt=risk_manager_system_prompt,
    )

    try:
        # Apply the inner 4-iteration limit directly to the agent's invoke call
        rm_result = await risk_manager_agent.ainvoke(
            {"messages": [HumanMessage(content="Evaluate the risk based on the debate and output your decision as JSON: {\"decision\": \"APPROVE\" or \"REJECT\", \"reasoning\": \"...\"}")]},
            {"recursion_limit": 4}
        )
        final_message = rm_result["messages"][-1].content

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

# Agent 6: Execution Agent (Remains same, just a simple function)
async def execute_trade(state: AgentState):
    proposed_trade = state.get("proposed_trade")
    if not proposed_trade or proposed_trade.get("action") == "HOLD":
        return {"trade_executed": False}

    data = await call_mcp_tool("execute_trade", {"proposed_trade": proposed_trade})
    return {"trade_executed": data.get("trade_executed", False)}

# Build the Graph
def build_trading_graph():
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("formulate_strategy", formulate_strategy)
    workflow.add_node("evaluate_risk", evaluate_risk)
    workflow.add_node("execute_trade", execute_trade)
    
    # Define edges (sequential)
    workflow.set_entry_point("formulate_strategy")
    workflow.add_edge("formulate_strategy", "evaluate_risk")
    workflow.add_edge("evaluate_risk", "execute_trade")
    workflow.add_edge("execute_trade", END)
    
    return workflow.compile()

trading_graph = build_trading_graph()
