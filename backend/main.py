from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

# Import graph from agents
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.agents import trading_graph, AgentState

app = FastAPI(title="Crypto Trading System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_DETAILS = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_DETAILS, serverSelectionTimeoutMS=2000)
database = client.crypto_trading

# Collections
portfolio_collection = database.get_collection("portfolio")
trade_collection = database.get_collection("trades")
logs_collection = database.get_collection("logs")

# In-memory mock database fallback
mock_db = {
    "portfolio": {
        "cash": 100000.0,
        "holdings": {"BTC": 0.5, "ETH": 10.0}
    },
    "trades": [],
    "logs": []
}

use_mock_db = False

# In-memory store for pending HITL cycles
pending_hitl_cycles: Dict[str, Dict[str, Any]] = {}

@app.on_event("startup")
async def startup_db_client():
    global use_mock_db
    try:
        await client.server_info()
        existing = await portfolio_collection.find_one({"_id": "mock_portfolio"})
        if not existing:
            await portfolio_collection.insert_one({
                "_id": "mock_portfolio",
                "cash": 100000.0,
                "holdings": {"BTC": 0.5, "ETH": 10.0}
            })
    except Exception:
        print("MongoDB connection failed, falling back to in-memory mock DB.")
        use_mock_db = True

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

class Trade(BaseModel):
    asset: str
    action: str
    amount: float
    price: float
    timestamp: datetime
    strategy_decision: str
    risk_assessment: str

class Portfolio(BaseModel):
    cash: float
    holdings: Dict[str, float]

class TriggerCycleRequest(BaseModel):
    asset: str

class ApproveTradeRequest(BaseModel):
    thread_id: str
    approved: bool

@app.get("/")
def read_root():
    return {"message": "Welcome to Crypto Trading System API"}

@app.get("/api/portfolio")
async def get_portfolio():
    if use_mock_db:
        return mock_db["portfolio"]
        
    portfolio = await portfolio_collection.find_one({"_id": "mock_portfolio"})
    if portfolio:
        portfolio.pop("_id", None)
        return portfolio
    raise HTTPException(status_code=404, detail="Portfolio not found")

@app.get("/api/trades")
async def get_trades():
    if use_mock_db:
        return list(reversed(mock_db["trades"]))[:50]
        
    trades = []
    cursor = trade_collection.find().sort("timestamp", -1).limit(50)
    async for document in cursor:
        document["_id"] = str(document["_id"])
        trades.append(document)
    return trades

@app.get("/api/logs")
async def get_logs():
    if use_mock_db:
        return list(reversed(mock_db["logs"]))[:10]
        
    logs = []
    cursor = logs_collection.find().sort("timestamp", -1).limit(10)
    async for document in cursor:
        document["_id"] = str(document["_id"])
        logs.append(document)
    return logs

@app.get("/api/pending_approvals")
async def get_pending_approvals():
    return list(pending_hitl_cycles.values())

async def _save_trade_and_update_portfolio(trade: dict):
    global use_mock_db
    if not use_mock_db:
        try:
            doc = dict(trade)
            await trade_collection.insert_one(doc)
            portfolio = await portfolio_collection.find_one({"_id": "mock_portfolio"})
            if portfolio:
                cost = trade["amount"] * trade["price"]
                if trade["action"] == "BUY":
                    portfolio["cash"] -= cost
                    portfolio["holdings"][trade["asset"]] = portfolio["holdings"].get(trade["asset"], 0) + trade["amount"]
                elif trade["action"] == "SELL":
                    portfolio["cash"] += cost
                    portfolio["holdings"][trade["asset"]] = max(0, portfolio["holdings"].get(trade["asset"], 0) - trade["amount"])

                await portfolio_collection.update_one(
                    {"_id": "mock_portfolio"},
                    {"$set": {"cash": portfolio["cash"], "holdings": portfolio["holdings"]}}
                )
            return
        except Exception:
            use_mock_db = True

    mock_db["trades"].append(dict(trade))
    cost = trade["amount"] * trade["price"]
    if trade["action"] == "BUY":
        mock_db["portfolio"]["cash"] -= cost
        mock_db["portfolio"]["holdings"][trade["asset"]] = mock_db["portfolio"]["holdings"].get(trade["asset"], 0) + trade["amount"]
    elif trade["action"] == "SELL":
        mock_db["portfolio"]["cash"] += cost
        mock_db["portfolio"]["holdings"][trade["asset"]] = max(0, mock_db["portfolio"]["holdings"].get(trade["asset"], 0) - trade["amount"])

async def _save_log(log_entry: dict):
    global use_mock_db
    if not use_mock_db:
        try:
            doc = dict(log_entry)
            await logs_collection.insert_one(doc)
            return
        except Exception:
            use_mock_db = True

    mock_db["logs"].append(dict(log_entry))

@app.post("/api/trigger_cycle")
async def trigger_cycle(req: TriggerCycleRequest):
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {"asset": req.asset}
    
    try:
        # Run graph up to interrupt_before=["execute_trade"]
        await trading_graph.ainvoke(initial_state, config=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    current_snapshot = trading_graph.get_state(config)
    interrupted_state = current_snapshot.values
    proposed = interrupted_state.get("proposed_trade") or {}
    risk_decision = interrupted_state.get("risk_decision")
    action = proposed.get("action", "HOLD")

    # If action is BUY or SELL and risk manager approved it, pause for Human-in-the-Loop review
    if action in ["BUY", "SELL"] and risk_decision == "APPROVE" and current_snapshot.next:
        pending_hitl_cycles[thread_id] = {
            "thread_id": thread_id,
            "asset": req.asset,
            "proposed_trade": proposed,
            "risk_assessment": interrupted_state.get("risk_assessment"),
            "debate_transcript": interrupted_state.get("debate_transcript"),
            "strategy_decision": interrupted_state.get("strategy_decision"),
            "created_at": datetime.now().isoformat()
        }
        return {
            "status": "awaiting_approval",
            "thread_id": thread_id,
            "proposed_trade": proposed,
            "risk_assessment": interrupted_state.get("risk_assessment"),
            "debate_transcript": interrupted_state.get("debate_transcript"),
            "message": "Risk Manager approved trade. Awaiting human confirmation before execution."
        }

    # Otherwise, execute immediately to finalize (trade was rejected by RM or action is HOLD)
    final_res = await trading_graph.ainvoke(None, config=config)
    final_state = final_res if final_res else interrupted_state

    log_entry = {
        "timestamp": datetime.now(),
        "asset": req.asset,
        "market_data": final_state.get("market_data"),
        "sentiment_data": final_state.get("sentiment_data"),
        "technical_data": final_state.get("technical_data"),
        "strategy_decision": final_state.get("strategy_decision"),
        "debate_transcript": final_state.get("debate_transcript"),
        "risk_assessment": final_state.get("risk_assessment"),
        "risk_decision": final_state.get("risk_decision"),
        "proposed_trade": final_state.get("proposed_trade"),
        "trade_executed": final_state.get("trade_executed", False)
    }
    await _save_log(log_entry)

    return {
        "status": "success",
        "trade_executed": final_state.get("trade_executed", False),
        "proposed_trade": final_state.get("proposed_trade")
    }

@app.post("/api/approve_trade")
async def approve_trade(req: ApproveTradeRequest):
    thread_id = req.thread_id
    config = {"configurable": {"thread_id": thread_id}}
    
    current_snapshot = trading_graph.get_state(config)
    if not current_snapshot or not current_snapshot.next:
        raise HTTPException(status_code=404, detail="No pending cycle found for this thread ID.")

    interrupted_state = current_snapshot.values
    proposed = interrupted_state.get("proposed_trade") or {}

    if not req.approved:
        # Human rejected trade
        proposed["action"] = "HOLD"
        proposed["amount"] = 0.0
        trading_graph.update_state(config, {
            "proposed_trade": proposed,
            "rejection_reason": "Rejected by human operator via HITL approval."
        })
    
    # Resume graph execution
    final_state = await trading_graph.ainvoke(None, config=config)
    pending_hitl_cycles.pop(thread_id, None)

    trade_executed = final_state.get("trade_executed", False)
    market_data = final_state.get("market_data") or {}
    price = market_data.get("price", 0.0)

    log_entry = {
        "timestamp": datetime.now(),
        "asset": final_state.get("asset", proposed.get("asset")),
        "market_data": final_state.get("market_data"),
        "sentiment_data": final_state.get("sentiment_data"),
        "technical_data": final_state.get("technical_data"),
        "strategy_decision": final_state.get("strategy_decision"),
        "debate_transcript": final_state.get("debate_transcript"),
        "risk_assessment": final_state.get("risk_assessment"),
        "risk_decision": final_state.get("risk_decision"),
        "proposed_trade": final_state.get("proposed_trade"),
        "trade_executed": trade_executed,
        "human_decision": "APPROVED" if req.approved else "REJECTED"
    }
    await _save_log(log_entry)

    if trade_executed:
        trade = {
            "asset": proposed.get("asset", "BTC"),
            "action": proposed.get("action", "HOLD"),
            "amount": proposed.get("amount", 0.0),
            "price": price,
            "timestamp": datetime.now(),
            "strategy_decision": final_state.get("strategy_decision"),
            "risk_assessment": final_state.get("risk_assessment")
        }
        await _save_trade_and_update_portfolio(trade)

    return {
        "status": "success",
        "trade_executed": trade_executed,
        "proposed_trade": final_state.get("proposed_trade"),
        "human_decision": "APPROVED" if req.approved else "REJECTED"
    }
