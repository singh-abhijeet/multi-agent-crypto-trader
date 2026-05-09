# About the Project Website

This is a modern, responsive single-page application built to showcase the architecture, agentic workflow, and setup instructions of the **Automated Crypto Trading System**.

The site is built using:
*   **Vite** (Build Tool)
*   **React + TypeScript** (UI Framework)
*   **Tailwind CSS** (Styling)
*   **Mermaid.js** (Dynamic Diagram Rendering)
*   **Lucide React** (Icons)

## Setup and Run Instructions

### Prerequisites

Ensure you have Node.js (version 18 or higher recommended) and npm installed on your machine.

### Installation

1. Navigate to the `website` directory from the root of the repository:
   ```bash
   cd website
   ```
2. Install the required dependencies:
   ```bash
   npm install
   ```

### Running the Development Server

To start the local development server with hot-module replacement (HMR), run:

```bash
npm run dev
```

The website will typically be available at `http://localhost:5173/`. Open this URL in your browser to view the site.

### Building for Production

To create an optimized production build of the website, run:

```bash
npm run build
```

This command will compile the TypeScript code, optimize the assets, and generate the final static files in the `dist/` directory.

You can preview the production build locally by running:

```bash
npm run preview
```