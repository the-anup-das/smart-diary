<div align="center">

# 📔 Notebook — AI-Powered Personal Diary

**A private, self-hosted AI journal: a diary app with mood tracking, AI reflections, overthinking and digital-wellbeing help, multi-agent decision support and long-term memory. Runs on Docker with OpenAI or fully local models (Ollama, LM Studio).**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue.svg)](https://docker.com)

[Who It Is For](#-who-this-is-for) · [Architecture](#%EF%B8%8F-system-architecture) · [Decision Swarm](#-decision-swarm-architecture) · [3-Minute Reset](#-3-minute-reset-overthinking-antidote) · [Tech Stack](#-tech-stack) · [Getting Started](#-getting-started)

</div>

---

## 🔍 Who This Is For

Notebook is for people searching for any of these, and finding that the usual apps upload their most private writing to someone else's cloud:

- a **self-hosted journaling app** or **private AI diary** you run at home, on a NAS or a Raspberry Pi, as an alternative to Day One, Journey or Reflectly
- a **mood tracker and mental health journal** with a mood calendar, sentiment and emotion tracking, and a wellbeing profile over time
- **CBT journaling**: cognitive reframes, thought records, a Stoic circle of control, open-loop tracking
- **help with overthinking and rumination**: detection in your own writing plus a guided three-minute practice
- a **dopamine detox** or **digital wellbeing** tool for doomscrolling, late-night screens, gaming and other compulsive habits, with a guided reset programme and urge surfing
- a **habit tracker with streaks** for writing, calm practice and abstinence windows
- **voice journaling** with a self-hosted Whisper speech-to-text server
- **chat with your journal** (RAG over your own entries) and a multi-agent **decision-making assistant**
- an **Obsidian-style writing experience** with markdown shortcuts, Tab word completion, typewriter scrolling and focus mode
- **privacy-first AI**: bring your own key, or point it at a local LLM so nothing ever leaves your network

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

**Write**
- **Daily journal** with rich text (Tiptap), autosave, and a distraction-free **Focus Mode**.
- **Writing experience:** Tab word completion from your own vocabulary, typewriter scrolling, readable line width, smart typography, task lists, and a goal-aware word count with your writing streak. Prompts step aside once you are writing.
- **Voice journaling:** continuous dictation via a self-hosted Whisper (faster-whisper) container — audio never leaves your server.
- **Guided templates:** Three Good Things, CBT Thought Record, Stoic Evening Review, Morning Pages, Five-Minute Journal, Worry Dump, Self-Compassion Break.
- **Backfill missed days:** click any empty past day in History to write that day's entry.
- **Offline write queue:** entries written offline are queued per day and synced when you reconnect.

**Reflect**
- **Save & Reflect:** AI analysis of mood, topics, grammar, open loops, cognitive reframes, and writing style.
- **Weekly AI Review:** a narrative retrospective of your week — wins, challenges, themes, and next-week focus.
- **On This Day + mood heatmap:** date-based memory resurfacing and a year-at-a-glance mood calendar.
- **Find Your Energy:** mental battery, Stoic Circle of Control reframing, rumination coaching, micro-actions.
- **3-Minute Reset:** detects overthinking in your entries and guides a three-minute breathing, stillness and visualisation practice, personalised to the loop you are stuck in and tracked like a habit.
- **Wellbeing Profile and patterns:** a six-axis radar of mood, energy, calm, agency, outward focus and clarity, each with a plain-language guide, plus a 28-day mood heatmap, weekly rhythm and overthinking trend on Insights.
- **Focus Reset (digital wellbeing):** appears only when your entries mention compulsive, high-stimulation habits. A guided programme after Lembke's DOPAMINE structure and Sepah's dopamine fasting: one behaviour, a 7, 14 or 30-day window, self-binding rules, replacements, daily check-ins, and a ninety-second urge-surfing practice.
- **Mind Fitness (brain rot antidote):** appears only when your entries describe brain fog, attention trouble or heavy passive consumption. Ten evidence-backed brain builders with weekly targets (sleep, long-form reading, deep work, exercise, rest, nature, learning, conversation, making, play), counted from your entries or ticked by hand, and a four-week "sharpen your mind" guide: subtract, rebuild, feed, keep.

**Ask**
- **Chat with your journal (RAG):** streaming answers grounded in your own entries with clickable date citations; conversations are saved and resumable.
- **Full-text search** across all entries with mood/sentiment/topic/date filters.

**Decide**
- **Decision Swarm:** multi-agent LangGraph analysis of hard choices, grounded in Mem0 long-term memory (Qdrant).
- **Decision review nudges:** predicted vs. actual outcome follow-ups that close the loop on past decisions.

**Trust & Operations**
- **Mem0 Integration:** local, self-hosted long-term memory via Qdrant — the AI "remembers" your goals, values, and past fears.
- **Helpfulness feedback:** 👍/👎 on every AI output, stored locally, so quality is measured rather than assumed.
- **Self-healing migrations:** Alembic-managed schema that automatically adopts and repairs older installs at startup.
- **Security:** JWT sessions, password reset (SMTP or log-link), auth rate limiting, single-purpose reset tokens.
- **AI Quality Benchmarking:** integrated **DeepEval** suite for AI faithfulness and relevancy.
- **Cost Transparency:** token tracking and estimated cost dashboard; **Test Connection** button for custom/local providers.
- **PWA Excellence:** offline-first editing, update prompts on new versions, installable on mobile with a bottom tab bar.
- **NAS Optimized:** built for Synology/QNAP/Home Servers with x86 and ARM64 support.

---

## ⚡ Find Your Energy Dashboard

Notebook goes beyond text logs by visualizing your mental energy state:

- **Human Battery:** A visual indicator of your daily energy level, calculated via a multi-dimensional formula (Mood, Chargers/Drainers, Agency, and Rumination).
- **Circle of Control:** An interactive component that helps you separate controllable vs. uncontrollable factors using Stoic reframing techniques.
- **Attention Heatmap:** Tracks where your mental energy went over the last 7 days (e.g., Health, Finances, Social).
- **Tomorrow's Recharge Strategy:** AI-generated forward-looking advice to build or protect energy for the following day.

---

## 🧘 3-Minute Reset (Overthinking Antidote)

Overthinking is detected in two layers and answered with a guided practice based on the 1-1-1 tool from Dr. Saloni Singh's *How to Stop Overthinking in 3 Minutes*:

- **While you write:** a quiet nudge appears when the entry itself starts to loop ("what if", "should have", "over and over").
- **After Save & Reflect:** the analysis rates rumination for the entry; at moderate or high, a card offers the reset.
- **The reset:** one minute of affectionate breathing, one of complete stillness, one of visualisation closed with affirmations. Only the third minute uses AI, which tailors it to the specific loop in today's entry. A soft chime marks each minute so you can keep your eyes closed.
- **Tracked like a habit:** rate how busy your mind is before and after, keep a streak on the Energy page, and drop a one-line reflection into the entry. A completed reset also tops up the energy battery.
- **Seen over time:** the Insights page shows an Overthinking Trend across the last four weeks next to the days you practised, a Weekly Rhythm of mood by weekday, a 28-day mood heatmap, and a Wellbeing Profile radar compared with the previous period.

<table>
  <tr>
    <td align="center" width="50%"><img src="docs/screenshots/reset-nudge.png" alt="Nudge shown while a looping entry is being written" width="100%"><br><sub>The nudge while a looping entry is being written</sub></td>
    <td align="center" width="50%"><img src="docs/screenshots/reset-feedback-card.png" alt="Feedback card offering the reset after analysis" width="100%"><br><sub>After analysis: the card appears when rumination is moderate or high</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/screenshots/reset-checkin.png" alt="Check-in screen naming the loop" width="100%"><br><sub>Check-in: the loop named from today's entry, and a before rating</sub></td>
    <td align="center"><img src="docs/screenshots/reset-visualise.png" alt="Visualisation minute with personalised lines" width="100%"><br><sub>Minute three: visualisation tailored to the entry</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/screenshots/reset-checkout.png" alt="Check-out screen with after rating and reflection" width="100%"><br><sub>Check-out: after rating, what to let go of, what matters</sub></td>
    <td align="center"><img src="docs/screenshots/reset-energy-card.png" alt="Energy page card with streak and 28-day strip" width="100%"><br><sub>Energy page: streak, 28-day strip and recent reflections</sub></td>
  </tr>
</table>

---

## 🧠 Mind Fitness (Brain Rot Antidote)

"Brain rot" was Oxford's word of the year for 2024: the wearing down of attention and memory by overconsumption of trivial online content. Notebook does not test your brain; it reads what you write about it, and only speaks up when there is something to work on.

- **Detection:** Save & Reflect records brain fog and attention complaints in your own words, minutes of passive scrolling when you state them, whether short-form video came up, and which brain-building activities actually happened. Nothing is inferred or diagnosed.
- **Nothing shown without a signal:** no card, no nav item and no feedback card until the last two weeks carry fog or short-form days, or you start the guide.
- **Ten builders, weekly targets:** slept enough, read long-form, deep work block, moved hard, real rest, time outdoors, learned something hard, real conversation, made something, played. Entries count on their own; tick the rest. A weekly score shows how much of the target set you hit.
- **Four-week guide:** one theme a week with four practices and a journal prompt each. Week one notices and subtracts (autoplay off, phone out of the bedroom, one boring wait a day), week two rebuilds attention (twenty minutes of a paper book, one deep-work block, green walks, seven hours in bed), week three feeds the brain (hard exercise, effortful learning, live conversation, making instead of consuming), week four makes it stick (compare week one's entries with now, a consumption budget, rules written down).
- **Together with the Focus Reset:** when the entries carry both compulsive habits and fog, the stimulation programme and the mind panel sit on the same page, and the Insights card carries both lines.

<table>
  <tr>
    <td align="center" width="50%"><img src="docs/screenshots/mind-fitness-panel.png" alt="Mind fitness panel with the 28-day fog strip, counts and the brain rot explainer" width="100%"><br><sub>What the entries show: fog and passive consumption by day, with the explainer open</sub></td>
    <td align="center" width="50%"><img src="docs/screenshots/mind-fitness-guide.png" alt="Today's builders with weekly targets and the four-week guide" width="100%"><br><sub>Today's builders, weekly targets and the four-week guide</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="docs/screenshots/mind-feedback-card.png" alt="Feedback card after a real analysis of a foggy entry" width="100%"><br><sub>After Save &amp; Reflect on a foggy entry: the note in your words, the minutes, and what you built</sub></td>
    <td align="center"><img src="docs/screenshots/mind-insights-card.png" alt="Insights card carrying both the stimulation and the mind lines" width="100%"><br><sub>Insights: the stimulation and mind lines together, shown only while there is a signal</sub></td>
  </tr>
</table>

---

## 📈 AI Quality & Cost Management

We take the reliability and cost of AI seriously:

- **DeepEval Integration:** We use industrial-grade evaluations to ensure the AI's advice is faithful to your diary and relevant to your needs.
- **Token Efficiency:** All prompts are compressed for token efficiency, and identical entries are cached to ensure zero-cost re-analysis.
- **Transparency Dashboard:** Track your exact token usage and estimated analysis costs directly in the Settings menu.

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router, standalone output), React 19, TypeScript, Tailwind CSS v4, TipTap 3 on ProseMirror for the editor, SWR for data fetching, next-pwa for the installable offline app, Framer Motion, Lucide icons, next-themes |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic migrations, Pydantic v2 structured outputs, PostgreSQL 15, uv for dependency management |
| AI | OpenAI SDK against any OpenAI-compatible endpoint (OpenAI, Ollama, LM Studio, LM Link), LangGraph and LangChain for the multi-agent decision swarm, mem0 with Qdrant for long-term vector memory, faster-whisper server for speech-to-text |
| Quality | pytest (offline, SQLite-backed API tests), DeepEval for AI faithfulness and relevancy, GitHub Actions publishing multi-arch images to GHCR |
| Deployment | Docker Compose, x86 and ARM64 images, OpenMediaVault, Synology and QNAP configs, JWT auth with rate limiting |

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

## 🦙 Using Local Open-Source Models (LM Studio / Ollama)

You don't have to rely on OpenAI! Notebook is fully compatible with local, open-source language models. By using tools like **LM Studio** or **Ollama**, you can run powerful models directly from your laptop or NAS for free and with 100% privacy.

To configure Notebook to use a local model via **LM Link** or LM Studio's Local Server:

1. Follow this comprehensive guide to get started: [Stop Paying for ChatGPT: Run Powerful Language Models From Your Laptop](https://medium.anuptechtips.com/stop-paying-for-chatgpt-run-powerful-language-models-from-your-laptop-9811219e0a63)
2. In your `.env` file, update the following variables:

```env
# Point this to your LM Link URL or Local Network IP
OPENAI_BASE_URL="http://your-local-ip:1234/v1" # or https://your-link.lmstudio.pro/v1
OPENAI_API_KEY="lm-studio" # Not strictly checked, but cannot be empty

# Update these to match the EXACT names of the models loaded in your local server
CHAT_MODEL="llama-3.2-3b-instruct"
EMBEDDING_MODEL="nomic-embed-text-v1.5"
```

---

## 💾 Data Persistence & Backup

### NAS Deployment (OpenMediaVault/Synology/QNAP)
To ensure your data survives container updates or system restarts, always use **Docker Volumes** or **Bind Mounts**. 

> [!NOTE]
> A pre-configured OMV setup is available in the `deployment/omv` directory.

**Recommended Bind Mount for NAS:**
In your `docker-compose.yml`, map the Postgres data to a physical folder on your drive:
```yaml
db:
  volumes:
    - /path/to/your/nas/storage/db_data:/var/lib/postgresql/data
```

### Import & Export
Notebook provides a built-in JSON archive system located in **Settings > Data & Security**:
- **Export:** Downloads a complete JSON file containing all your entries, AI feedback, and open loops.
- **Import:** Allows you to restore your library from a JSON archive. This is useful for moving to a new server or recovering from a data loss. *Note: Importing will merge data with your current entries.*

---

## 📁 Project Structure
- `backend/routers/analyze.py`: the Save & Reflect analysis, energy dashboard endpoints, and the stimulation and cognition signal extraction.
- `backend/routers/insights.py` and `backend/wellbeing.py`: Insights aggregation, the Wellbeing Profile axes, 28-day patterns.
- `backend/routers/calm.py` and `backend/skills/three_minute_reset/`: the 3-Minute Reset sessions and its planner prompt.
- `backend/routers/focus.py`: the Focus Reset overview, plans, urges and check-ins, plus the Mind Fitness summary, builders and guide.
- `backend/skills/decision_agent.py`: the LangGraph Swarm engine.
- `backend/memory_service.py`: Mem0 and Qdrant integration.
- `backend/alembic/versions/`: schema migrations, applied automatically at startup.
- `backend/tests/`: offline API tests (`cd backend && python -m pytest tests -q`).
- `frontend/src/components/diary/`: the editor, feedback view, templates, voice recorder and the Tab word-completion extension.
- `frontend/src/components/calm/`, `frontend/src/components/focus/`: the reset overlay, practice card, urge surfing, the Mind Fitness panel and Focus pages.
- `frontend/src/components/insights/`: charts, the Wellbeing radar, heatmap, weekly rhythm and trend cards.
- `frontend/src/app/(dashboard)/decisions/[id]/page.tsx`: unified Dynamic Swarm UI.

---

## 🤝 Contributing
Contributions are welcome! Please see [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## 🏷️ Keywords

self-hosted journal, AI diary, private journaling app, mood tracker, mental health journal, CBT journaling, cognitive reframing, overthinking, rumination, mindfulness, dopamine detox, digital wellbeing, screen time, brain rot, brain fog, attention span, focus, deep work, digital detox, doomscrolling, short-form video, cognitive fitness, habit tracker, streaks, voice journaling, Whisper, chat with your notes, RAG, LangGraph, mem0, Qdrant, Next.js, FastAPI, PostgreSQL, Docker, NAS, Raspberry Pi, Ollama, local LLM, privacy-first AI, Day One alternative, Obsidian alternative for journaling.

## 📄 License
MIT License. See [LICENSE](./LICENSE) for details.
