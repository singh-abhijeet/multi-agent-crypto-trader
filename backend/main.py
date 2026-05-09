from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# Import graph from agents
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agents import trading_graph, AgentState

app = FastAPI(title="Crypto Trading System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
# We use try-except to fallback to in-memory mock if MongoDB is not running locally.
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

@app.on_event("startup")
async def startup_db_client():
    global use_mock_db
    try:
        # Check if MongoDB is available
        await client.server_info()
        
        # Initialize mock portfolio if not exists
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

@app.post("/api/trigger_cycle")
async def trigger_cycle(req: TriggerCycleRequest):
    initial_state = {"asset": req.asset}
    
    # Run the LangGraph
    try:
        final_state = trading_graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Save the execution log
    log_entry = {
        "timestamp": datetime.now(),
        "asset": req.asset,
        "market_data": final_state.get("market_data"),
        "sentiment_data": final_state.get("sentiment_data"),
        "technical_data": final_state.get("technical_data"),
        "strategy_decision": final_state.get("strategy_decision"),
        "risk_assessment": final_state.get("risk_assessment"),
        "proposed_trade": final_state.get("proposed_trade"),
        "trade_executed": final_state.get("trade_executed")
    }
    
    if use_mock_db:
        mock_db["logs"].append(log_entry)
    else:
        await logs_collection.insert_one(log_entry)
    
    # If trade was executed, record it and update portfolio
    if final_state.get("trade_executed"):
        proposed = final_state["proposed_trade"]
        trade = {
            "asset": proposed["asset"],
            "action": proposed["action"],
            "amount": proposed["amount"],
            "price": final_state["market_data"]["price"],
            "timestamp": datetime.now(),
            "strategy_decision": final_state.get("strategy_decision"),
            "risk_assessment": final_state.get("risk_assessment")
        }
        
        if use_mock_db:
            mock_db["trades"].append(trade)
            # Update mock portfolio
            cost = trade["amount"] * trade["price"]
            if trade["action"] == "BUY":
                mock_db["portfolio"]["cash"] -= cost
                mock_db["portfolio"]["holdings"][trade["asset"]] = mock_db["portfolio"]["holdings"].get(trade["asset"], 0) + trade["amount"]
            elif trade["action"] == "SELL":
                mock_db["portfolio"]["cash"] += cost
                mock_db["portfolio"]["holdings"][trade["asset"]] = max(0, mock_db["portfolio"]["holdings"].get(trade["asset"], 0) - trade["amount"])
        else:
            await trade_collection.insert_one(trade)
            # Update DB portfolio
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

    # Return safe subset of state to frontend
    return {
        "status": "success",
        "trade_executed": final_state.get("trade_executed"),
        "proposed_trade": final_state.get("proposed_trade")
    }
