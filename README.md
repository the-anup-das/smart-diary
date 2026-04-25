<div align="center">

# 📔 Notebook — AI-Powered Personal Diary

**A private, self-hosted journaling app with AI-driven insights, mood tracking, and personal growth analytics.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docker.com)

[Problem & Solution](#-what-problem-we-solve) · [Architecture](#%EF%B8%8F-system-architecture) · [Getting Started](#-getting-started) · [Ecosystem](#-my-ecosystem)

</div>

---

## 🎯 What Problem We Solve
*Journaling is powerful, but extracting long-term insights is tedious.* 
Most people write daily but rarely look back to identify patterns in their mood, vocabulary, or emotional state. 
This project brings the power of Generative AI and LLMs to your personal thoughts, turning scattered diary entries into structured, actionable insights—without compromising your privacy.

## 💡 How We Solve It & Why It Matters
By passing your encrypted local entries through state-of-the-art LLMs (like GPT-4o or local Ollama instances), Notebook automatically acts as a cognitive behavioral assistant. 
It analyzes sentiment, detects emotional trends, tracks open loops (unresolved tasks), and offers cognitive reframes. It matters because it transforms journaling from a passive dumping ground into an active partner for personal growth.

## 🚀 Why It's Hard & Better Than Existing Apps
- **Privacy vs. Intelligence:** Most smart diaries upload your intimate thoughts to third-party servers. We give you full control with self-hosting and local LLM support.
- **Complex Orchestration:** Extracting structured JSON (mood scores, sentiment, open loops) from unstructured, emotional text consistently is technically challenging. 
- **Offline-First Resilience:** Notebook handles network instability and queues LLM analysis gracefully using a custom PWA-ready architecture.
- **No Lock-in:** Your data is yours. PostgreSQL backed, easily exportable, totally private.

---

## 🏗️ System Architecture

Our architecture is designed for privacy, performance, and robust AI integration.

```mermaid
flowchart TD
    subgraph Client [Client / User Device]
        UI[Next.js PWA<br>Rich Text Editor]
        LocalSync[(Local Sync Queue<br>IndexedDB)]
        UI <--> |Offline Fallback| LocalSync
    end

    subgraph Server [Backend / Home Server]
        API[FastAPI<br>REST & JWT Auth]
        PromptEngine[Dynamic Prompting<br>Engine]
        DB[(PostgreSQL<br>Relational + JSONB)]
        
        API --> |1. Save Raw Entry| DB
        API --> |2. Trigger Analysis| PromptEngine
        PromptEngine --> |4. Store JSON Insights| DB
    end

    subgraph AI [LLM Provider]
        LLM[OpenAI API / Local Ollama<br>Structured Output Parser]
    end

    UI -->|HTTPS / JWT| API
    PromptEngine -->|3. Optimized Prompt| LLM
    LLM -->|Extracted JSON| PromptEngine
```


### Data Flow
1. **User Input:** User writes a diary entry in the rich text editor (PWA / Web).
2. **Preprocessing:** The frontend sanitizes the input and queues the request. If offline, the request is stored locally.
3. **API Layer:** FastAPI receives the entry, authenticates via JWT, and saves the raw text to PostgreSQL.
4. **LLM Analysis Pipeline:**
   - The backend constructs an optimized prompt wrapping the user's text.
   - It calls the LLM (OpenAI API or Local LLM) requesting structured JSON output.
   - The LLM extracts: Mood Score (1-10), Sentiment, Vocabulary Metrics, Cognitive Reframes, and Open Loops.
5. **Post-processing & Storage:** The extracted data is validated against strict Pydantic schemas and stored relationally alongside the entry.
6. **Pattern Recognition:** Aggregation endpoints crunch the historical AI data to generate the Insights Dashboard.

### Frontend (FE) & Backend (BE) Interaction
- **Next.js (BFF):** Acts as a secure proxy and handles server-side rendering, caching, and PWA capabilities.
- **FastAPI:** Exposes RESTful endpoints for CRUD and AI analysis. Heavy LLM processing is handled asynchronously to keep the UI snappy.
- **Database:** PostgreSQL stores both relational metadata (users, dates) and unstructured JSON (LLM analysis results).

---

## ⚙️ Core System Features (Under the Hood)
- **Local-First Sync Queue:** A custom React queue persists entries locally when offline and syncs them when connectivity is restored.
- **Resilient AI Extraction:** Fallback mechanisms and retries for LLM structured output parsing.
- **Dynamic Prompting Engine:** Context-aware prompts that adapt based on the user's entry length and historical data.
- **Progressive Web App (PWA):** Installable locally with offline caching for a native-like experience.

---

## 📐 Design Decisions
- **Next.js + FastAPI:** Next.js for excellent frontend UX and PWA support; FastAPI because Python remains the undisputed king of AI/LLM orchestration.
- **Docker-First:** Packaged specifically for Home Servers and NAS environments to make self-hosting frictionless.
- **Bring Your Own LLM (BYOK):** We enforce no vendor lock-in. Use OpenAI, or point the base URL to a local Ollama instance for 100% air-gapped privacy.

---

## 🚧 Limitations
- **LLM Latency:** Cloud API calls can take 2-5 seconds depending on entry length.
- **Local Hardware Requirements:** Running a local LLM requires significant RAM/VRAM, making it challenging on lower-end NAS devices.
- **Token Limits:** Extremely long entries might exceed context windows if not chunked properly.

---

## 🔮 Future Improvements
- **RAG (Retrieval-Augmented Generation):** "Chat with your past self" by vectorizing historical entries.
- **Semantic Search:** Find entries based on concepts rather than exact keywords.
- **Voice-to-Text Integration:** Whisper integration for audio journaling.
- **More Granular Offline Support:** Complete offline editing and conflict resolution.

---

## 🌐 My Ecosystem

Discover more of my projects:
- [Smart Diary](https://github.com/the-anup-das/smart-diary) - The main repository for this project.
- [GitHub Profile](https://github.com/the-anup-das) - Check out my other open-source tools and contributions.

---

## 🚀 Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/notebook.git
cd notebook
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
# Database — matches the docker-compose defaults
DATABASE_URL="postgresql://diary_user:diary_password@localhost:5432/diary_db?schema=public"

# Your OpenAI API key
OPENAI_API_KEY="sk-proj-..."

# Optional: Use a local LLM or proxy instead
OPENAI_BASE_URL="https://api.openai.com/v1"
```

### 3. Start everything with Docker

```bash
docker compose up --build
```

This starts three containers:
- **PostgreSQL** on port `5432`
- **FastAPI backend** on port `8000`
- **Next.js frontend** on port `3000`

### 4. Open the app

```
http://localhost:3000
```

Create an account, write your first entry, and the AI will analyze it automatically.

---

## 🏠 NAS / Home Server Deployment

Smart Diary is optimized for self-hosting on NAS (Synology, QNAP, TrueNAS) or any home server. We use **GitHub Container Registry (GHCR)** to ensure zero rate-limits for our users.

### 📦 Docker Images
| Component | Image |
|-----------|-------|
| **Backend** | `ghcr.io/the-anup-das/smart-diary-backend:latest` |
| **Frontend** | `ghcr.io/the-anup-das/smart-diary-frontend:latest` |

### 1. Simple Deployment (Docker Compose)
Download the optimized [docker-compose.nas.yml](./docker-compose.nas.yml) and run:

```bash
docker-compose -f docker-compose.nas.yml up -d
```

### 2. Portainer (One-Click)
Use our [Portainer Template](./portainer-template.json) to deploy directly from your dashboard. This is the recommended way for Synology/QNAP users.

### 3. Hardware Support
- **Architecture**: Supports **x86_64** (Intel/AMD) and **ARM64** (Raspberry Pi / New NAS models).
- **Environment**: Ensure `OPENAI_API_KEY` and `JWT_SECRET` are set in your environment.

---

## 📁 Project Structure

```
notebook/
├── backend/               # FastAPI Python backend
│   ├── routers/
│   │   ├── auth.py        # JWT authentication
│   │   ├── entries.py     # Journal CRUD
│   │   ├── analyze.py     # AI analysis pipeline
│   │   └── insights.py    # Aggregated analytics
│   ├── models.py          # SQLAlchemy ORM models
│   ├── database.py        # DB connection setup
│   ├── main.py            # App entrypoint
│   └── pyproject.toml     # Python dependencies (uv)
│
├── frontend/              # Next.js frontend
│   └── src/
│       ├── app/
│       │   ├── (dashboard)/   # Main journal & insights pages
│       │   ├── login/         # Auth page
│       │   └── api/           # Next.js API routes (BFF)
│       ├── components/        # Reusable UI components
│       └── lib/               # Auth helpers, API clients
│
├── docker-compose.yml     # Full-stack orchestration
├── .env.example           # Environment variable template
└── .gitignore
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `OPENAI_API_KEY` | ✅ | Your OpenAI API key |
| `OPENAI_BASE_URL` | ❌ | Override for local LLMs (e.g. Ollama) |

> **Never commit your `.env` file.** It is listed in `.gitignore`. Use `.env.example` as the reference template.

---

## 🤝 Contributing

Contributions are welcome and appreciated! Please read **[CONTRIBUTING.md](./CONTRIBUTING.md)** for guidelines on how to get involved.

---

## 📄 License

This project is open-source under the [MIT License](./LICENSE).
