with open("README.md", "r") as f:
    content = f.read()

setup_instructions = """## Setup and Run Instructions

### Prerequisites
*   Node.js and npm (for the frontend)
*   Python 3.8+ (for the backend and MCP server)
*   [MongoDB](https://www.mongodb.com/) (Optional: The backend will fall back to an in-memory mock database if MongoDB is not running locally on port 27017)
*   A Google Gemini API Key

### MCP Server Setup
The trading tools are decoupled and hosted on an MCP (Model Context Protocol) server. The backend agents use an MCP client to communicate with this server.
1.  Navigate to the MCP server directory:
    ```bash
    cd trader-mcp
    ```
2.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```
*(Note: The FastAPI backend is configured to automatically invoke the `trader-mcp` server as a subprocess via the `stdio` transport. You do not need to run the MCP server manually as a separate background process for the main backend workflow to function.)*

### Backend Setup
1.  Navigate to the backend directory:
    ```bash
    cd backend
    ```
2.  Install Python dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Set your Google Gemini API key as an environment variable (required for the LLM agents to function):
    ```bash
    export GOOGLE_API_KEY="your_actual_api_key_here"
    ```
4.  Start the FastAPI server:
    ```bash
    uvicorn main:app --reload
    ```
    *The backend will be available at http://localhost:8000.*"""

import re
content = re.sub(r'## Setup and Run Instructions.*?(?=\n### Frontend Setup)', setup_instructions, content, flags=re.DOTALL)

with open("README.md", "w") as f:
    f.write(content)
