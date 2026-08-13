# 🚀 AI-Agent-Environment-Simulator

A full-stack Multi-Agent AI platform focused on **HR Analytics and Recruitment Assistance**.

The project simulates how multiple AI agents collaborate to perform HR-related tasks such as job analysis, candidate screening, report generation, research, summarization, and workflow automation. The current implementation provides the foundation for a scalable multi-agent environment with a React frontend, FastAPI backend, and local LLM integration using Ollama.

---

# 📌 Project Status

**Current Version:** v0.2

**Development Stage:** Academic Project (Under Active Development)

**Current Focus:**
Building a working Multi-Agent HR Analytics platform with local AI inference before expanding to cloud LLM providers.

---

# 🎯 Project Objectives

- Build a modular Multi-Agent AI environment.
- Automate HR analytics and recruitment workflows.
- Enable collaboration between specialized AI agents.
- Support local LLM execution using Ollama.
- Design a scalable architecture for future cloud deployment.

---

# ✨ Current Features

## Frontend

- Dashboard
- Agent Monitoring
- Task Summary
- Messages
- Logs
- Replay
- Settings
- Live Simulation Interface

---

## Backend

- FastAPI Backend
- REST APIs
- WebSocket Support
- Multi-Agent Architecture
- Agent Orchestrator
- Local LLM Integration (Ollama)
- Modular Backend Structure

---

## AI Agents

Current agent modules include:

- Research Agent
- Analysis Agent
- Data Agent
- Report Agent
- Summarizer Agent
- Web Search Agent
- Agent Orchestrator

---

# 🏗 System Architecture

```
                User
                  │
                  ▼
        React + Vite Frontend
                  │
        REST API / WebSockets
                  │
                  ▼
            FastAPI Backend
                  │
        Agent Orchestrator
                  │
 ┌────────┬────────┬────────┬────────┬────────┐
 ▼        ▼        ▼        ▼        ▼
Research Analysis Data Report Summarizer
 Agent     Agent    Agent  Agent    Agent
                  │
                  ▼
             Ollama LLM
                  │
                  ▼
            Local Datasets
```

---

# 🛠 Tech Stack

### Frontend

- React
- Vite
- JavaScript
- CSS

### Backend

- FastAPI
- Python
- Uvicorn
- WebSockets

### AI

- Ollama
- Gemma (Development)
- Multi-Agent Architecture

### Database

- HR Datasets (JSON)
- Local Storage

---

# 📂 Project Structure

```
AI-Agent-Environment-Simulator
│
├── frontend/
│
├── backend/
│
├── database/
│
├── docs/
│
├── .github/
│
└── README.md
```

---

# ⚙ Getting Started

## Clone Repository

```bash
git clone https://github.com/shreetejshinde2003/AI-Agent-Environment-Simulator.git
```

---

## Backend

```bash
cd backend

python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload
```

Backend runs at:

```
http://127.0.0.1:8000
```

---

## Frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend runs at:

```
http://localhost:5173
```

---

# 🌳 Git Workflow

```
main
│
├── shreetej-backend
├── sumit-database
└── parag-frontend
```

Development is performed on feature branches and merged into **main** after testing.

---

# 📈 Development Roadmap

## ✅ Completed

- Repository setup
- GitHub collaboration
- Frontend foundation
- Backend foundation
- Multi-Agent architecture
- Dashboard implementation
- Agent pages
- Logs page
- Messages page
- Replay page
- Settings page
- Task Summary
- Initial Ollama integration
- Versioning (v0.1, v0.2)

---

## 🔄 In Progress

- HR Analytics specialization
- Recruitment Assistant workflow
- Backend integration with frontend
- Live AI agent execution
- Database integration
- Real-time monitoring

---

## 🔜 Planned

- Candidate matching
- Resume analysis
- Job description generation
- Hiring recommendation engine
- Analytics dashboard
- Authentication
- PostgreSQL
- Cloud LLM support
- Deployment

---

# 👥 Team

### Shreetej Shinde

- Project Lead
- Backend Development
- AI Agents
- System Integration
- Repository Management

### Sumit Jadhav

- Database Module
- Dataset Preparation
- Data Validation
- Documentation

### Parag Kulkarni

- Frontend Development
- UI/UX
- Dashboard
- Visualization

---

# 📊 Current Milestone

**Version:** v0.2

Current objective is to transform the existing multi-agent framework into a specialized **HR Analytics and Recruitment Assistance Platform** capable of demonstrating end-to-end AI-assisted recruitment workflows.

---

# 📄 License

This project is currently being developed as an academic project.

License selection will be finalized before the public release (v1.0).

---

⭐ Project under active development.
