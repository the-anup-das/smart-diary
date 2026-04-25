<div align="center">

# 📔 Notebook — AI-Powered Personal Diary

**A private, self-hosted journaling app with Multi-Agent Swarm reasoning and Long-Term Memory.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docker.com)

[Problem & Solution](#-what-problem-we-solve) · [Architecture](#%EF%B8%8F-system-architecture) · [Decision Swarm](#-decision-swarm-architecture) · [Getting Started](#-getting-started)

</div>

---

## 🎯 What Problem We Solve
*Journaling is powerful, but extracting long-term insights is tedious.* 
Notebook transforms your scattered diary entries into a structured, actionable knowledge base. By integrating **Long-Term Memory (Mem0)** and a **Multi-Agent Decision Swarm**, it acts as a cognitive behavioral assistant that actually *remembers* your life history to provide grounded, personal advice.

## 💡 How We Solve It & Why It Matters
Notebook goes beyond simple sentiment analysis. It uses a **StateGraph-based workflow** to break down complex life decisions into dynamic paths. 
- **Long-Term Context:** Uses **Qdrant** and **Mem0** to store and retrieve your values, fears, and history across months of entries.
- **Deep Reasoning:** Employs a **Map-Reduce Swarm** to evaluate multiple paths in parallel, ensuring no option is rushed or ignored.

## 🧠 Why Decision-Making is Hard (And How We Fix It)

Decision-making is one of the most cognitively demanding human tasks. Notebook is built to solve three specific psychological bottlenecks:

1. **Emotional Fog & Urgency Bias:** When we face a tough choice, the "scary" option creates immediate anxiety that clouds long-term judgment.
   - **Fix:** Our **Evaluator Swarm** forces a slow, analytical breakdown of every path, moving you from "fight-or-flight" to "system 2" thinking.
2. **Personal Information Amnesia:** We often forget our own values, past patterns, and hard-won lessons during a crisis.
   - **Fix:** **Mem0 Long-Term Memory** retrieves relevant facts from your past entries (e.g., "You've felt this burnout before in 2022") to ground the advice in your real history.
3. **Linear Thinking vs. Ripple Effects:** Humans are naturally bad at seeing "Third-Order Consequences" (the ripple effects of a ripple effect).
   - **Fix:** The **Synthesis Node** is specifically trained to look for **Blindspots**—the things you are romanticizing or ignoring—helping you see the full chess board.

---

## 🏗️ System Architecture

Our architecture is designed for privacy, memory-depth, and advanced reasoning.

```mermaid
flowchart TD
    subgraph Client [Client / User Device]
        UI[Next.js PWA]
        LocalSync[(Local Queue)]
    end

    subgraph Server [Backend / Home Server]
        API[FastAPI REST]
        Graph[LangGraph Swarm Engine]
        DB[(PostgreSQL)]
        Memory[(Mem0 + Qdrant Vector Store)]
        
        API --> |1. Save Entry| DB
        API --> |2. Ingest Fact| Memory
        API --> |3. Trigger Decision| Graph
        Graph --> |4. Context Retrieval| Memory
        Graph --> |5. Store Analysis| DB
    end

    subgraph AI [LLM Provider]
        LLM[OpenAI / Local LLM]
    end

    UI --> API
    Graph --> LLM
```

---

## 🐝 Decision Swarm Architecture (Multi-Agent)

We have moved away from rigid, single-shot frameworks. The **Decision Junction** now uses a high-performance Swarm architecture:

1.  **Orchestrator Node:** Analyzes the decision and retrieves relevant **Mem0** facts. It dynamically discovers the best **Paths** (e.g., "Quit", "Stay", "Bridge") and **Factors** (e.g., "Burnout Risk", "Financial Runway") for *this specific* situation.
2.  **Evaluator Swarm (Parallel):** Spins up independent agents for *each* discovered path. Each agent evaluates its path against the factors, strictly defining **Positives (+)** and **Negatives (-)**.
3.  **Synthesis Node:** Consolidates all parallel evaluations, detects blindspots (e.g., "You are romanticizing the workload"), and provides a grounded recommendation.

---

## ⚙️ Core System Features
- **Mem0 Integration:** Local, self-hosted long-term memory via Qdrant. The AI "remembers" your spouse's name, your career goals, and past fears.
- **Dynamic Reasoning:** No more hardcoded categories. The AI discovers what factors matter most for your specific life event.
- **PWA Excellence:** Offline-first editing with a custom React sync queue.
- **NAS Optimized:** Built for Synology/QNAP/Home Servers with x86 and ARM64 support.

---

## 📐 Design Decisions
- **LangGraph for Orchestration:** Allows for complex state-management and parallel "swarm" reasoning that simple prompt chains cannot achieve.
- **Vector-First Memory:** Every entry is processed for "facts" which are stored in a vector database, allowing the Decision Agent to ground its advice in your actual history.
- **Docker-First:** Packaged specifically for Home Servers to keep your data 100% private.

---

## 🚀 Getting Started

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- An OpenAI API key (or local Ollama instance)

### 1. Clone & Setup
```bash
git clone https://github.com/the-anup-das/smart-diary.git
cd smart-diary
cp .env.example .env
```

### 2. Configure Environment
```env
# Database
DATABASE_URL="postgresql://diary_user:diary_password@localhost:5432/diary_db"

# AI & Memory
OPENAI_API_KEY="sk-proj-..."
MEM0_DIR="/app/mem0_db"
QDRANT_URL="http://qdrant:6333"
```

### 3. Start everything
```bash
docker compose up --build
```
This starts **PostgreSQL**, **Qdrant (Vector DB)**, **FastAPI**, and **Next.js**.

---

## 📁 Project Structure
- `backend/skills/decision_agent.py`: The LangGraph Swarm engine.
- `backend/services/memory_service.py`: Mem0 and Qdrant integration.
- `frontend/src/app/(dashboard)/decisions/[id]/page.tsx`: Unified Dynamic Swarm UI.

---

## 🤝 Contributing
Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## 📄 License
MIT License. See [LICENSE](./LICENSE) for details.
