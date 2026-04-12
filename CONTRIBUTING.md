# Contributing to Notebook

Thank you for your interest in contributing! 🎉  
This is a personal, open-source project and all contributions — big or small — are genuinely appreciated.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Ways to Contribute](#ways-to-contribute)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Commit Style](#commit-style)

---

## Code of Conduct

Please be respectful and constructive. This project follows a simple rule: **treat others the way you'd want to be treated.** Harassment or toxic behavior of any kind will not be tolerated.

---

## Ways to Contribute

You don't have to write code to contribute! Here are different ways to help:

- 🐛 **Report bugs** — open a GitHub Issue
- 💡 **Suggest features** — open a GitHub Discussion or Issue
- 📖 **Improve documentation** — fix typos, clarify setup steps, add examples
- 🧪 **Write tests** — backend or frontend test coverage
- 🎨 **Improve UI/UX** — better components, animations, or responsive design
- 🔌 **Add integrations** — local LLM support (Ollama), export formats, etc.

---

## Getting Started

### 1. Fork and clone

```bash
git clone https://github.com/your-username/notebook.git
cd notebook
```

### 2. Set up your environment

```bash
cp .env.example .env
# Fill in your OPENAI_API_KEY
```

### 3. Start the dev environment

```bash
docker compose up --build
```

The app will be available at `http://localhost:3000` with hot-reload on both frontend and backend.

### 4. Backend only (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn main:app --reload --port 8000
```

### 5. Frontend only (without Docker)

```bash
cd frontend
npm install
npm run dev
```

---

## Development Workflow

1. **Create a branch** off `master` for your change:
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

2. **Make your changes** with clear, focused commits (see [Commit Style](#commit-style))

3. **Test your changes** locally before opening a PR

4. **Open a Pull Request** against `master` with a clear description of what and why

---

## Pull Request Guidelines

- Keep PRs **focused** — one feature or fix per PR
- Add a **clear description** of what changed and why
- Reference any related Issue numbers (e.g. `Closes #42`)
- Ensure the app still runs correctly end-to-end
- Don't include unrelated formatting or whitespace changes

---

## Reporting Bugs

When opening a bug report, please include:

- **What you expected to happen**
- **What actually happened** (error messages, screenshots)
- **Steps to reproduce** the issue
- **Your environment** (OS, Docker version, browser)

Use the GitHub Issue template if available.

---

## Suggesting Features

Open a GitHub Issue with:

- A clear description of the feature
- Why it would be useful
- Optional: mockups, examples, or references

---

## Commit Style

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <short description>
```

| Type | When to use |
|------|------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `style` | Formatting, missing semicolons, etc. |
| `refactor` | Code restructure without behavior change |
| `test` | Adding or fixing tests |
| `chore` | Build process, dependency updates |

**Examples:**
```
feat(insights): add mood trend chart with weekly averages
fix(auth): correct JWT expiry handling on refresh
docs(readme): update docker setup instructions
```

---

## Questions?

Open a GitHub Discussion or Issue — happy to help! 🙌
