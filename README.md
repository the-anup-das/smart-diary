<div align="center">

# 📔 Notebook — AI-Powered Personal Diary

**A private, self-hosted journaling app with AI-driven insights, mood tracking, and personal growth analytics.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docker.com)

[Features](#-features) · [Tech Stack](#-tech-stack) · [Getting Started](#-getting-started) · [Contributing](./CONTRIBUTING.md)

</div>

---

## ✨ Features

- 📝 **Rich Journal Editor** — Write daily entries with a clean, distraction-free editor (powered by Tiptap)
- 🤖 **AI Analysis** — Each entry is analyzed by OpenAI to produce mood scores, sentiment, grammar feedback, and cognitive reframes
- 📊 **Insights Dashboard** — Visualize mood trends, vocabulary growth, writing streaks, and emotional patterns over time
- 🔁 **Open Loops Tracker** — AI automatically detects unresolved tasks and commitments from your entries
- 🔐 **Private & Self-hosted** — All data stays on your own machine; no third-party storage
- 🌗 **Dark / Light Mode** — Sleek UI with full theme support

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS v4 |
| **Backend** | FastAPI, Python 3.12, SQLAlchemy, Uvicorn |
| **Database** | PostgreSQL 15 |
| **AI** | OpenAI API (GPT-4o / compatible) |
| **Auth** | JWT (python-jose + jose) |
| **Infrastructure** | Docker Compose |

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
