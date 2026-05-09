import { Database, Layout, Server, Bot, Shield, Zap, Search, MessageSquare, TrendingUp, Cpu } from 'lucide-react';
import { Mermaid } from './components/Mermaid';

function App() {
  const overallSystemDiagram = `
graph TD
    User([User]) -->|Interacts with UI| Frontend[Angular Frontend]
    Frontend <-->|REST API| Backend[FastAPI Backend]

    subgraph Server Infrastructure
        Backend -->|Persists Data| MongoDB[(MongoDB Database)]
        Backend -->|Invokes Workflow| LangGraph[LangGraph Engine]
    end

    subgraph AI Orchestration
        LangGraph <-->|Prompts & Responses| LLM[Google Gemini LLM API]
    end
  `;

  const langGraphDiagram = `
stateDiagram-v2
    [*] --> gather_market_data

    gather_market_data --> analyze_sentiment: Market Data Gathered
    analyze_sentiment --> analyze_technicals: Sentiment Analyzed
    analyze_technicals --> formulate_strategy: Technicals Analyzed

    formulate_strategy --> evaluate_risk: Strategy Proposed (via Gemini)
    evaluate_risk --> execute_trade: Risk Evaluated (via Gemini)

    execute_trade --> [*]: Trade Executed (or Hold)

    note right of formulate_strategy
        Uses Gemini LLM to decide
        BUY, SELL, or HOLD based on
        aggregated data.
    end note

    note right of evaluate_risk
        Uses Gemini LLM to rigorously
        evaluate the proposed strategy
        against risk principles.
    end note
  `;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      {/* Header / Hero */}
      <header className="bg-white border-b border-slate-200 py-16 px-6 md:px-12 text-center">
        <div className="max-w-4xl mx-auto">
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-indigo-50 text-indigo-600 rounded-full">
              <Bot size={48} />
            </div>
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-slate-900 mb-6">
            Automated Crypto Trading System
          </h1>
          <p className="text-xl text-slate-600 leading-relaxed">
            A full-stack, automated cryptocurrency trading system. Features an Angular-based frontend and a Python FastAPI backend that leverages <span className="font-semibold text-indigo-600">LangGraph</span> and <span className="font-semibold text-indigo-600">Google Gemini</span> to orchestrate a team of AI agents.
          </p>
        </div>
      </header>

      <main className="max-w-6xl mx-auto py-16 px-6 md:px-12 space-y-24">

        {/* Architecture Section */}
        <section>
          <h2 className="text-3xl font-bold text-slate-900 mb-8 border-b pb-4">Architectural Insights</h2>
          <p className="text-lg text-slate-600 mb-10">The system is designed with a modern, decoupled architecture.</p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <Layout className="text-blue-500 mb-4" size={32} />
              <h3 className="text-xl font-bold mb-3">Frontend</h3>
              <p className="text-slate-600">Built with Angular 21, providing a UI to view portfolio status, recent trades, logs, and trigger new trading cycles manually.</p>
            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <Server className="text-green-500 mb-4" size={32} />
              <h3 className="text-xl font-bold mb-3">Backend</h3>
              <p className="text-slate-600">Developed using Python and FastAPI, handling REST APIs, database connections, and triggering AI workflows.</p>
            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <Database className="text-purple-500 mb-4" size={32} />
              <h3 className="text-xl font-bold mb-3">Database</h3>
              <p className="text-slate-600">MongoDB is used for persistent storage of portfolios, trade histories, and execution logs, with an in-memory fallback.</p>
            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <Bot className="text-indigo-500 mb-4" size={32} />
              <h3 className="text-xl font-bold mb-3">LangGraph</h3>
              <p className="text-slate-600">Models core intelligence as a state graph, allowing structured data flow from data gatherers to execution managers.</p>
            </div>

            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow lg:col-span-2">
              <Cpu className="text-orange-500 mb-4" size={32} />
              <h3 className="text-xl font-bold mb-3">Google Gemini LLM</h3>
              <p className="text-slate-600">Integrates Google's Gemini-1.5-pro model to process complex data and output structured trading decisions and rigorous risk reasoning.</p>
            </div>
          </div>
        </section>

        {/* Agentic Workflow Section */}
        <section>
          <h2 className="text-3xl font-bold text-slate-900 mb-8 border-b pb-4">Agentic Workflow</h2>
          <p className="text-lg text-slate-600 mb-10">
            The core trading intelligence is powered by a multi-agent system orchestrated by LangGraph. Each agent plays a specific role.
          </p>

          <div className="space-y-6">
            <div className="flex gap-6 items-start bg-white p-6 rounded-xl border border-slate-200">
              <div className="p-3 bg-slate-100 rounded-lg text-slate-700 shrink-0">
                <Search size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold mb-2">1. Market Data Gatherer</h3>
                <p className="text-slate-600 mb-2"><strong className="text-slate-800">Role:</strong> Collects real-time market data (price, volume, trend).</p>
                <p className="text-slate-600"><strong className="text-slate-800">Value:</strong> Provides foundational quantitative context.</p>
              </div>
            </div>

            <div className="flex gap-6 items-start bg-white p-6 rounded-xl border border-slate-200">
              <div className="p-3 bg-blue-50 rounded-lg text-blue-600 shrink-0">
                <MessageSquare size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold mb-2">2. Sentiment Analyst</h3>
                <p className="text-slate-600 mb-2"><strong className="text-slate-800">Role:</strong> Analyzes news and social media to provide a sentiment score.</p>
                <p className="text-slate-600"><strong className="text-slate-800">Value:</strong> Captures emotional and qualitative market drivers.</p>
              </div>
            </div>

            <div className="flex gap-6 items-start bg-white p-6 rounded-xl border border-slate-200">
              <div className="p-3 bg-teal-50 rounded-lg text-teal-600 shrink-0">
                <TrendingUp size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold mb-2">3. Technical Analyst</h3>
                <p className="text-slate-600 mb-2"><strong className="text-slate-800">Role:</strong> Computes technical indicators like RSI and MACD.</p>
                <p className="text-slate-600"><strong className="text-slate-800">Value:</strong> Identifies short-term momentum and price patterns.</p>
              </div>
            </div>

            <div className="flex gap-6 items-start bg-white p-6 rounded-xl border-l-4 border-l-indigo-500 shadow-sm">
              <div className="p-3 bg-indigo-50 rounded-lg text-indigo-600 shrink-0">
                <Cpu size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold mb-2">4. Strategy/Decision Agent (LLM)</h3>
                <p className="text-slate-600 mb-2"><strong className="text-slate-800">Role:</strong> Aggregates data and uses Gemini to formulate a strategy (ACTION, AMOUNT, REASONING).</p>
                <p className="text-slate-600"><strong className="text-slate-800">Value:</strong> Acts as the brain, synthesizing diverse streams to make context-aware decisions.</p>
              </div>
            </div>

            <div className="flex gap-6 items-start bg-white p-6 rounded-xl border-l-4 border-l-orange-500 shadow-sm">
              <div className="p-3 bg-orange-50 rounded-lg text-orange-600 shrink-0">
                <Shield size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold mb-2">5. Risk Manager (LLM)</h3>
                <p className="text-slate-600 mb-2"><strong className="text-slate-800">Role:</strong> Evaluates proposed trades against standard risk management principles to APPROVE or REJECT.</p>
                <p className="text-slate-600"><strong className="text-slate-800">Value:</strong> Protects portfolio from severe drawdowns, ensuring long-term capital preservation.</p>
              </div>
            </div>

            <div className="flex gap-6 items-start bg-white p-6 rounded-xl border border-slate-200">
              <div className="p-3 bg-green-50 rounded-lg text-green-600 shrink-0">
                <Zap size={24} />
              </div>
              <div>
                <h3 className="text-xl font-bold mb-2">6. Execution Agent</h3>
                <p className="text-slate-600 mb-2"><strong className="text-slate-800">Role:</strong> Executes the order if approved by Risk Management.</p>
                <p className="text-slate-600"><strong className="text-slate-800">Value:</strong> Automates physical trade execution.</p>
              </div>
            </div>
          </div>

          <div className="mt-10 p-6 bg-slate-100 rounded-xl">
            <h4 className="font-bold text-lg mb-3">Control & Communication Flow</h4>
            <p className="text-slate-700 leading-relaxed">
              Agents do not communicate directly. A shared <code>AgentState</code> object is managed by the LangGraph state machine. As the graph executes sequentially, each agent receives the state, performs its task, appends findings, and passes the enriched state down the pipeline.
            </p>
          </div>
        </section>

        {/* Diagrams Section */}
        <section>
          <h2 className="text-3xl font-bold text-slate-900 mb-8 border-b pb-4">System Diagrams</h2>

          <div className="mb-12">
            <h3 className="text-xl font-bold mb-6 text-center text-slate-700">Overall System Design</h3>
            <Mermaid chart={overallSystemDiagram} />
          </div>

          <div>
            <h3 className="text-xl font-bold mb-6 text-center text-slate-700">LangGraph State Flow</h3>
            <Mermaid chart={langGraphDiagram} />
          </div>
        </section>

        {/* Setup Instructions */}
        <section className="bg-slate-900 text-slate-300 p-8 md:p-12 rounded-2xl">
          <h2 className="text-3xl font-bold text-white mb-8 border-b border-slate-700 pb-4">Setup & Run</h2>

          <div className="grid md:grid-cols-2 gap-12">
            <div>
              <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
                <Server size={24} className="text-green-400" /> Backend Setup
              </h3>
              <ol className="space-y-4 list-decimal list-inside marker:text-slate-500">
                <li>Navigate to backend: <code className="bg-slate-800 px-2 py-1 rounded text-sm text-green-300">cd backend</code></li>
                <li>Install packages: <code className="bg-slate-800 px-2 py-1 rounded text-sm text-green-300">pip install -r requirements.txt</code></li>
                <li>Set API Key: <code className="bg-slate-800 px-2 py-1 rounded text-sm text-green-300 break-all">export GOOGLE_API_KEY="..."</code></li>
                <li>Start server: <code className="bg-slate-800 px-2 py-1 rounded text-sm text-green-300">uvicorn main:app --reload</code></li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
                <Layout size={24} className="text-blue-400" /> Frontend Setup
              </h3>
              <ol className="space-y-4 list-decimal list-inside marker:text-slate-500">
                <li>Navigate to frontend: <code className="bg-slate-800 px-2 py-1 rounded text-sm text-blue-300">cd frontend</code></li>
                <li>Install packages: <code className="bg-slate-800 px-2 py-1 rounded text-sm text-blue-300">npm install</code></li>
                <li>Start UI: <code className="bg-slate-800 px-2 py-1 rounded text-sm text-blue-300">npm start</code></li>
              </ol>
            </div>
          </div>
        </section>

      </main>

      <footer className="bg-slate-900 border-t border-slate-800 py-8 text-center text-slate-500">
        <p>Automated Crypto Trading System Documentation</p>
      </footer>
    </div>
  );
}

export default App;
