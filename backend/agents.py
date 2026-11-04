from typing import TypedDict, Annotated, List, Optional
from langgraph.graph import StateGraph, END
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
    debate_history: Optional[List[str]]
    debate_transcript: Optional[str]
    debate_round: Optional[int]
    debate_status: Optional[str]  # "ongoing", "concluded", "skipped"
    risk_assessment: Optional[str]
    risk_decision: Optional[str]  # "APPROVE" or "REJECT"
    trade_executed: Optional[bool]
    rejection_reason: Optional[str]

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

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content="Gather data and output your strategy decision as a JSON object matching the StrategyOutput schema: {\"action\": \"...\", \"amount\": ...., \"reasoning\": \"...\"}")]},
            {"recursion_limit": 4}
        )

        final_message = result["messages"][-1].content
        
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

        try:
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
            action = "HOLD"
            amount = 0.0
            reasoning = final_message

        proposed_trade = {
            "action": action,
            "amount": amount,
            "asset": asset
        }

        return {
            "strategy_decision": reasoning,
            "proposed_trade": proposed_trade,
            "market_data": market_data,
            "sentiment_data": sentiment_data,
            "technical_data": technical_data,
            "debate_history": [],
            "debate_transcript": "",
            "debate_round": 0,
            "debate_status": "ongoing" if action in ["BUY", "SELL"] else "skipped"
        }
    except Exception as e:
        return {
            "strategy_decision": f"Error: {e}",
            "proposed_trade": {"action": "HOLD", "amount": 0.0, "asset": asset},
            "debate_history": [],
            "debate_transcript": "",
            "debate_round": 0,
            "debate_status": "skipped"
        }

def should_start_debate(state: AgentState):
    proposed_trade = state.get("proposed_trade")
    if not proposed_trade or proposed_trade.get("action") == "HOLD":
        return "risk_manager"
    return "bull_agent"

async def bull_agent_node(state: AgentState):
    asset = state.get("asset", "BTC")
    proposed_trade = state.get("proposed_trade")
    market_data = state.get("market_data")
    sentiment_data = state.get("sentiment_data")
    technical_data = state.get("technical_data")
    strategy_decision = state.get("strategy_decision")
    debate_history = list(state.get("debate_history") or [])
    round_num = (state.get("debate_round") or 0) + 1

    context = f"""
    Asset: {asset}
    Proposed Trade: {proposed_trade}
    Strategy Reasoning: {strategy_decision}
    Market Context: {market_data}
    Sentiment Data: {sentiment_data}
    Technical Data: {technical_data}
    """

    system_prompt = f"""
    You are a Bullish Researcher. Your goal is to advocate for executing the proposed trade.
    Focus on positive market trends, upside potential, and favorable conditions.
    You have access to the tool 'gather_market_data' to inspect real-time market data to support your claims.

    Data Context:
    {context}
    """

    agent = create_deep_agent(
        model="google_genai:gemini-1.5-pro",
        tools=[gather_market_data],
        system_prompt=system_prompt,
    )

    if not debate_history:
        bull_prompt = (
            f"Round {round_num}: Present your opening argument for why this proposed trade is sound and advantageous. "
            f"Use the gather_market_data tool if you need live verification."
        )
    else:
        last_bear_msg = debate_history[-1]
        bull_prompt = (
            f"Round {round_num}: The Bear researcher argued:\n'{last_bear_msg}'\n\n"
            f"Rebut the Bear's concerns and reaffirm the case for the proposed trade. "
            f"You may verify with gather_market_data tool if needed."
        )

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=bull_prompt)]},
            {"recursion_limit": 4}
        )
        bull_message = result["messages"][-1].content
    except Exception as e:
        bull_message = f"Bull argument unavailable due to error: {e}"

    debate_history.append(f"Round {round_num} [Bull]: {bull_message}")

    return {
        "debate_history": debate_history,
        "debate_round": round_num,
        "debate_transcript": "\n\n".join(debate_history)
    }

async def bear_agent_node(state: AgentState):
    asset = state.get("asset", "BTC")
    proposed_trade = state.get("proposed_trade")
    market_data = state.get("market_data")
    sentiment_data = state.get("sentiment_data")
    technical_data = state.get("technical_data")
    strategy_decision = state.get("strategy_decision")
    debate_history = list(state.get("debate_history") or [])
    round_num = state.get("debate_round") or 1

    context = f"""
    Asset: {asset}
    Proposed Trade: {proposed_trade}
    Strategy Reasoning: {strategy_decision}
    Market Context: {market_data}
    Sentiment Data: {sentiment_data}
    Technical Data: {technical_data}
    """

    system_prompt = f"""
    You are a Bearish Researcher. Your goal is to critically examine the risks of the proposed trade.
    Focus on potential drawdowns, liquidity traps, volatility, and downside risk.
    You have access to the tool 'gather_market_data' to check real-time asset data to validate your concerns.

    Data Context:
    {context}
    """

    agent = create_deep_agent(
        model="google:gemini-1.5-pro",
        tools=[gather_market_data],
        system_prompt=system_prompt,
    )

    last_bull_msg = debate_history[-1] if debate_history else "No bull statement."
    bear_prompt = (
        f"Round {round_num}: The Bull researcher argued:\n'{last_bull_msg}'\n\n"
        f"Respond critically, highlight overlooked risks, and counter the Bull's stance. "
        f"You may check live market metrics using gather_market_data."
    )

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=bear_prompt)]},
            {"recursion_limit": 4}
        )
        bear_message = result["messages"][-1].content
    except Exception as e:
        bear_message = f"Bear argument unavailable due to error: {e}"

    debate_history.append(f"Round {round_num} [Bear]: {bear_message}")

    return {
        "debate_history": debate_history,
        "debate_transcript": "\n\n".join(debate_history)
    }

async def debate_judge_node(state: AgentState):
    round_num = state.get("debate_round") or 1
    max_rounds = 3

    # If reached max rounds, conclude debate
    if round_num >= max_rounds:
        return {"debate_status": "concluded"}

    debate_transcript = state.get("debate_transcript", "")
    proposed_trade = state.get("proposed_trade")

    judge_prompt = f"""
    You are an impartial Debate Moderator evaluating an adversarial debate between a Bull and Bear researcher on this trade: {proposed_trade}.

    Current Debate Transcript:
    {debate_transcript}

    Determine whether:
    1. A clear consensus or insurmountable objection has already been established such that further debate will not yield new insights (EARLY STOP).
    2. Further debate is warranted to clarify unresolved risks or claims (CONTINUE).

    Return your evaluation strictly as JSON:
    {{
        "decision": "CONTINUE" | "STOP",
        "reasoning": "brief reason"
    }}
    """

    judge_agent = create_deep_agent(
        model="google_genai:gemini-1.5-pro",
        tools=[],
        system_prompt="You are a strict, impartial debate moderator. Output JSON only.",
    )

    try:
        result = await judge_agent.ainvoke(
            {"messages": [HumanMessage(content=judge_prompt)]},
            {"recursion_limit": 4}
        )
        final_msg = result["messages"][-1].content
        if "```json" in final_msg:
            json_str = final_msg.split("```json")[1].split("```")[0].strip()
        elif "```" in final_msg:
            json_str = final_msg.split("```")[1].split("```")[0].strip()
        else:
            json_str = final_msg
        parsed = json.loads(json_str)
        decision = parsed.get("decision", "STOP").upper()
    except Exception:
        # Default to STOP after round 2 to keep latency balanced if parser fails
        decision = "CONTINUE" if round_num < 2 else "STOP"

    status = "ongoing" if decision == "CONTINUE" else "concluded"
    return {"debate_status": status}

def route_debate_decision(state: AgentState):
    if state.get("debate_status") == "ongoing":
        return "bull_agent"
    return "risk_manager"

async def risk_manager_node(state: AgentState):
    proposed_trade = state.get("proposed_trade")
    if not proposed_trade or proposed_trade.get("action") == "HOLD":
        return {
            "risk_assessment": "No trade to evaluate.",
            "risk_decision": "HOLD",
            "proposed_trade": proposed_trade
        }

    market_data = state.get('market_data')
    sentiment_data = state.get('sentiment_data')
    technical_data = state.get('technical_data')
    strategy_decision = state.get('strategy_decision')
    debate_transcript = state.get('debate_transcript', 'No debate occurred.')

    context = f"""
    Proposed Trade: {proposed_trade}
    Strategy Reasoning: {strategy_decision}
    Market Context: {market_data}
    Sentiment Data: {sentiment_data}
    Technical Data: {technical_data}

    Debate Transcript:
    {debate_transcript}
    """

    system_prompt = f"""
    You are a strict Risk Manager. Your task is to make a final decision on the proposed trade by reviewing the market context and the debate between the Bull and Bear researchers.

    Context:
    {context}

    Approve or reject the trade based on standard risk management principles (capital preservation, risk/reward asymmetry, volatility).
    You MUST output your decision strictly as JSON:
    {{
        "decision": "APPROVE" or "REJECT",
        "reasoning": "Detailed justification based on the debate and market factors"
    }}
    """

    risk_manager_agent = create_deep_agent(
        model="google_genai:gemini-1.5-pro",
        tools=[],
        system_prompt=system_prompt,
    )

    try:
        rm_result = await risk_manager_agent.ainvoke(
            {"messages": [HumanMessage(content="Evaluate the trade risk and output your decision as JSON.")]},
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
        except Exception:
            decision = "REJECT" if "REJECT" in final_message.upper() else "APPROVE"
            reasoning = final_message

        if decision == "REJECT":
            proposed_trade["action"] = "HOLD"
            proposed_trade["amount"] = 0.0

        return {
            "risk_assessment": reasoning,
            "risk_decision": decision,
            "proposed_trade": proposed_trade
        }
    except Exception as e:
        proposed_trade["action"] = "HOLD"
        proposed_trade["amount"] = 0.0
        return {
            "risk_assessment": f"Risk assessment error: {e}",
            "risk_decision": "REJECT",
            "proposed_trade": proposed_trade
        }

async def execute_trade_node(state: AgentState):
    proposed_trade = state.get("proposed_trade")
    if not proposed_trade or proposed_trade.get("action") == "HOLD":
        return {"trade_executed": False}

    data = await call_mcp_tool("execute_trade", {"proposed_trade": proposed_trade})
    return {"trade_executed": data.get("trade_executed", False)}

# Build the Graph with Checkpointer for HITL
def build_trading_graph(checkpointer=None):
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("formulate_strategy", formulate_strategy)
    workflow.add_node("bull_agent", bull_agent_node)
    workflow.add_node("bear_agent", bear_agent_node)
    workflow.add_node("debate_judge", debate_judge_node)
    workflow.add_node("risk_manager", risk_manager_node)
    workflow.add_node("execute_trade", execute_trade_node)
    
    # Entry point
    workflow.set_entry_point("formulate_strategy")

    # Conditional edge from formulate_strategy
    workflow.add_conditional_edges(
        "formulate_strategy",
        should_start_debate,
        {
            "bull_agent": "bull_agent",
            "risk_manager": "risk_manager"
        }
    )

    # Debate loop edges
    workflow.add_edge("bull_agent", "bear_agent")
    workflow.add_edge("bear_agent", "debate_judge")
    workflow.add_conditional_edges(
        "debate_judge",
        route_debate_decision,
        {
            "bull_agent": "bull_agent",
            "risk_manager": "risk_manager"
        }
    )

    # Risk manager to execute_trade
    workflow.add_edge("risk_manager", "execute_trade")
    workflow.add_edge("execute_trade", END)
    
    # Interrupt before execute_trade to enable Human-in-the-Loop review
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["execute_trade"]
    )

trading_checkpointer = MemorySaver()
trading_graph = build_trading_graph(checkpointer=trading_checkpointer)
