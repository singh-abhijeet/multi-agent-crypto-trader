import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import AIMessage
from backend.agents import (
    AgentState,
    formulate_strategy,
    bull_agent_node,
    bear_agent_node,
    debate_judge_node,
    risk_manager_node,
    should_start_debate,
    route_debate_decision,
    build_trading_graph
)
from backend.main import app, mock_db
from httpx import AsyncClient, ASGITransport

@pytest.fixture
def mock_agent_state() -> AgentState:
    return {
        "asset": "BTC",
        "market_data": {"price": 50000.0, "volume": 1200, "trend": "up"},
        "sentiment_data": {"score": 0.8, "summary": "Bullish news"},
        "technical_data": {"RSI": 65, "MACD": "Bullish crossover"},
        "strategy_decision": "High momentum suggests buying.",
        "proposed_trade": {"action": "BUY", "amount": 0.5, "asset": "BTC"},
        "debate_history": [],
        "debate_transcript": "",
        "debate_round": 0,
        "debate_status": "ongoing",
        "risk_assessment": None,
        "risk_decision": None,
        "trade_executed": None,
        "rejection_reason": None
    }

def test_should_start_debate_routing():
    # When trade is HOLD, skip debate to risk_manager
    state_hold: AgentState = {"proposed_trade": {"action": "HOLD", "amount": 0.0, "asset": "BTC"}}
    assert should_start_debate(state_hold) == "risk_manager"

    # When trade is BUY/SELL, route to bull_agent
    state_buy: AgentState = {"proposed_trade": {"action": "BUY", "amount": 0.5, "asset": "BTC"}}
    assert should_start_debate(state_buy) == "bull_agent"

def test_route_debate_decision():
    # If ongoing, continue debate loop to bull_agent
    assert route_debate_decision({"debate_status": "ongoing"}) == "bull_agent"
    # If concluded or skipped, proceed to risk_manager
    assert route_debate_decision({"debate_status": "concluded"}) == "risk_manager"
    assert route_debate_decision({"debate_status": "skipped"}) == "risk_manager"

@pytest.mark.asyncio
async def test_bull_agent_turn(mock_agent_state):
    with patch("backend.agents.create_deep_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="Bullish argument: Strong upward momentum and volume surge.")]
        })
        mock_create.return_value = mock_agent

        result = await bull_agent_node(mock_agent_state)
        assert result["debate_round"] == 1
        assert len(result["debate_history"]) == 1
        assert "Bullish argument" in result["debate_transcript"]
        # Verify tool gather_market_data was provided to bull agent
        assert mock_create.call_args[1]["tools"] is not None
        tool_names = [t.name for t in mock_create.call_args[1]["tools"]]
        assert "gather_market_data" in tool_names

@pytest.mark.asyncio
async def test_bear_agent_turn(mock_agent_state):
    mock_agent_state["debate_history"] = ["Round 1 [Bull]: Momentum is high."]
    mock_agent_state["debate_round"] = 1

    with patch("backend.agents.create_deep_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="Bearish counter: Overbought conditions and overhead resistance.")]
        })
        mock_create.return_value = mock_agent

        result = await bear_agent_node(mock_agent_state)
        assert len(result["debate_history"]) == 2
        assert "Bearish counter" in result["debate_transcript"]
        # Verify tool gather_market_data was provided to bear agent
        assert mock_create.call_args[1]["tools"] is not None
        tool_names = [t.name for t in mock_create.call_args[1]["tools"]]
        assert "gather_market_data" in tool_names

@pytest.mark.asyncio
async def test_debate_judge_adaptive_stop(mock_agent_state):
    mock_agent_state["debate_round"] = 1
    mock_agent_state["debate_transcript"] = "Round 1 [Bull] ... \n\nRound 1 [Bear] ..."

    # Test judge choosing STOP
    with patch("backend.agents.create_deep_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content='```json\n{"decision": "STOP", "reasoning": "Arguments are clear"}\n```')]
        })
        mock_create.return_value = mock_agent

        res = await debate_judge_node(mock_agent_state)
        assert res["debate_status"] == "concluded"

    # Test judge choosing CONTINUE
    with patch("backend.agents.create_deep_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content='```json\n{"decision": "CONTINUE", "reasoning": "Need more debate"}\n```')]
        })
        mock_create.return_value = mock_agent

        res = await debate_judge_node(mock_agent_state)
        assert res["debate_status"] == "ongoing"

    # Test max rounds triggers stop regardless of judge
    mock_agent_state["debate_round"] = 3
    res_max = await debate_judge_node(mock_agent_state)
    assert res_max["debate_status"] == "concluded"

@pytest.mark.asyncio
async def test_risk_manager_approval_and_rejection(mock_agent_state):
    # Approval case
    with patch("backend.agents.create_deep_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content='```json\n{"decision": "APPROVE", "reasoning": "Risk reward is 3:1"}\n```')]
        })
        mock_create.return_value = mock_agent

        res = await risk_manager_node(mock_agent_state)
        assert res["risk_decision"] == "APPROVE"
        assert res["proposed_trade"]["action"] == "BUY"

    # Rejection case
    with patch("backend.agents.create_deep_agent") as mock_create:
        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content='```json\n{"decision": "REJECT", "reasoning": "Excessive tail risk"}\n```')]
        })
        mock_create.return_value = mock_agent

        res = await risk_manager_node(mock_agent_state)
        assert res["risk_decision"] == "REJECT"
        assert res["proposed_trade"]["action"] == "HOLD"
        assert res["proposed_trade"]["amount"] == 0.0

@pytest.mark.asyncio
async def test_hitl_workflow_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Mock agents to approve trade and reach interrupt_before
        with patch("backend.agents.create_deep_agent") as mock_create:
            mock_agent = MagicMock()
            # Depending on caller:
            async def mock_ainvoke(input_data, config=None):
                prompt = input_data["messages"][0].content
                if "StrategyOutput" in prompt:
                    return {"messages": [AIMessage(content='{"action": "BUY", "amount": 0.5, "reasoning": "Strong trend"}')]}
                elif "Bull" in prompt or "opening argument" in prompt:
                    return {"messages": [AIMessage(content="Bullish argument")]}
                elif "Bear" in prompt:
                    return {"messages": [AIMessage(content="Bearish counter")]}
                elif "moderator" in prompt or "STOP" in prompt:
                    return {"messages": [AIMessage(content='{"decision": "STOP", "reasoning": "Resolved"}')]}
                else: # Risk manager
                    return {"messages": [AIMessage(content='{"decision": "APPROVE", "reasoning": "Acceptable risk"}')]}

            mock_agent.ainvoke = mock_ainvoke
            mock_create.return_value = mock_agent

            # 1. Trigger cycle
            res = await ac.post("/api/trigger_cycle", json={"asset": "BTC"})
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "awaiting_approval"
            assert "thread_id" in data
            thread_id = data["thread_id"]

            # Check pending approvals endpoint
            pending_res = await ac.get("/api/pending_approvals")
            assert pending_res.status_code == 200
            pending_list = pending_res.json()
            assert any(p["thread_id"] == thread_id for p in pending_list)

            # 2. Approve trade via HITL endpoint
            with patch("backend.agents.call_mcp_tool", new_callable=AsyncMock) as mock_mcp:
                mock_mcp.return_value = {"trade_executed": True}
                approve_res = await ac.post("/api/approve_trade", json={
                    "thread_id": thread_id,
                    "approved": True
                })
                assert approve_res.status_code == 200
                approve_data = approve_res.json()
                assert approve_data["status"] == "success"
                assert approve_data["trade_executed"] is True
                assert approve_data["human_decision"] == "APPROVED"

            # Check pending list is now empty of this thread
            pending_res2 = await ac.get("/api/pending_approvals")
            assert not any(p["thread_id"] == thread_id for p in pending_res2.json())

            # Check logs contain debate_transcript
            logs_res = await ac.get("/api/logs")
            assert logs_res.status_code == 200
            logs = logs_res.json()
            latest_log = logs[0]
            assert "debate_transcript" in latest_log
            assert latest_log["human_decision"] == "APPROVED"
