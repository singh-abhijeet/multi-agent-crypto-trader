from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
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



# Ensure GOOGLE_API_KEY is set in environment for real usage
# os.environ["GOOGLE_API_KEY"] = "YOUR_API_KEY"

# Define the state for the LangGraph
class AgentState(TypedDict):
    asset: str
    market_data: dict
    sentiment_data: dict
    technical_data: dict
    strategy_decision: str
    proposed_trade: dict
    risk_assessment: str
    trade_executed: bool

# Agent 1: Market Data Gatherer (Mock)
async def gather_market_data(state: AgentState):
    asset = state.get("asset", "BTC")
    data = await call_mcp_tool("gather_market_data", {"asset": asset})
    return {"market_data": data["market_data"]}

# Agent 2: Sentiment Analyst (Mock)
async def analyze_sentiment(state: AgentState):
    data = await call_mcp_tool("analyze_sentiment", {})
    return {"sentiment_data": data["sentiment_data"]}

# Agent 3: Technical Analyst (Mock)
async def analyze_technicals(state: AgentState):
    data = await call_mcp_tool("analyze_technicals", {})
    return {"technical_data": data["technical_data"]}

# Agent 4: Strategy/Decision Agent (Gemini)
async def formulate_strategy(state: AgentState):
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro")
    
    prompt = f"""
    You are an expert Crypto Trading Strategist.
    Asset: {state.get('asset')}
    Market Data: {state.get('market_data')}
    Sentiment: {state.get('sentiment_data')}
    Technicals: {state.get('technical_data')}
    
    Based on this data, propose a trading action (BUY, SELL, HOLD), the amount (0 to 1), and a brief reasoning.
    Format your response as:
    ACTION: [BUY/SELL/HOLD]
    AMOUNT: [0.0-1.0]
    REASONING: [Your reasoning]
    """
    
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        
        # Simple parser
        lines = content.split('\n')
        action = "HOLD"
        amount = 0.0
        for line in lines:
            if line.startswith("ACTION:"):
                action = line.split(":")[1].strip()
            elif line.startswith("AMOUNT:"):
                try:
                    amount = float(line.split(":")[1].strip())
                except:
                    pass
        
        proposed_trade = {
            "action": action,
            "amount": amount,
            "asset": state.get("asset")
        }
        return {"strategy_decision": content, "proposed_trade": proposed_trade}
    except Exception as e:
        return {"strategy_decision": f"Error: {e}", "proposed_trade": {"action": "HOLD", "amount": 0, "asset": state.get("asset")}}

# Agent 5: Risk Manager (Gemini)
async def evaluate_risk(state: AgentState):
    proposed_trade = state.get("proposed_trade")
    if not proposed_trade or proposed_trade.get("action") == "HOLD":
        return {"risk_assessment": "No trade to evaluate.", "proposed_trade": proposed_trade}
        
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro")
    prompt = f"""
    You are a strict Risk Manager. Evaluate this proposed trade:
    Trade: {proposed_trade}
    Market Context: {state.get('market_data')}
    
    Approve or reject the trade based on standard risk management principles.
    Format your response as:
    DECISION: [APPROVE/REJECT]
    REASONING: [Your reasoning]
    """
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        if "DECISION: REJECT" in content.upper():
            proposed_trade["action"] = "HOLD"
            proposed_trade["amount"] = 0.0
        return {"risk_assessment": content, "proposed_trade": proposed_trade}
    except Exception as e:
        proposed_trade["action"] = "HOLD"
        return {"risk_assessment": f"Error: {e}", "proposed_trade": proposed_trade}

# Agent 6: Execution Agent
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
    workflow.add_node("gather_market_data", gather_market_data)
    workflow.add_node("analyze_sentiment", analyze_sentiment)
    workflow.add_node("analyze_technicals", analyze_technicals)
    workflow.add_node("formulate_strategy", formulate_strategy)
    workflow.add_node("evaluate_risk", evaluate_risk)
    workflow.add_node("execute_trade", execute_trade)
    
    # Define edges (parallel data gathering, then sequential)
    workflow.set_entry_point("gather_market_data")
    workflow.add_edge("gather_market_data", "analyze_sentiment")
    workflow.add_edge("analyze_sentiment", "analyze_technicals")
    workflow.add_edge("analyze_technicals", "formulate_strategy")
    workflow.add_edge("formulate_strategy", "evaluate_risk")
    workflow.add_edge("evaluate_risk", "execute_trade")
    workflow.add_edge("execute_trade", END)
    
    return workflow.compile()

trading_graph = build_trading_graph()

