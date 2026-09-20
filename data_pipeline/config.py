"""Configuration for the Multi-Agent Synthetic Data Distillation Pipeline."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load workspace root .env if present
root_dir = Path(__file__).resolve().parent.parent
load_dotenv(root_dir / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env")

# Base paths
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_DATASET_PATH = OUTPUT_DIR / "training_dataset.jsonl"
TEST_DATASET_PATH = OUTPUT_DIR / "test_dataset.jsonl"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TELEMETRY_LOG_PATH = LOGS_DIR / "telemetry.jsonl"
REJECTIONS_LOG_PATH = LOGS_DIR / "rejections.log"

# API Provider & Endpoint Configuration
# Default is OpenRouter, but Together AI, Fireworks, or local vLLM can be used via env vars.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENROUTER_API_KEY", os.getenv("OPENAI_API_KEY", "")))

# Model Assignments (Cross-family alternation)
# Writer & Editor & QE: Qwen family
WRITER_MODEL = os.getenv("WRITER_MODEL", "qwen/qwen3-30b-a3b-instruct")
EDITOR_MODEL = os.getenv("EDITOR_MODEL", "qwen/qwen3-30b-a3b-instruct")
QE_MODEL = os.getenv("QE_MODEL", "qwen/qwen3-30b-a3b-instruct")

# Reviewer & Analyzer (Teacher) & Judge: Gemma family
REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", "google/gemma-2-9b-it")
ANALYZER_MODEL = os.getenv("ANALYZER_MODEL", "google/gemma-2-9b-it")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "google/gemma-2-9b-it")

# Pipeline Controls
MAX_EDITOR_ITERATIONS = 3
MAX_SCHEMA_RETRY = 2
DISCARD_RATE_THRESHOLD = 0.25  # Pause/warn if discard rate exceeds 25% over window
TEST_SPLIT_RATIO = 0.10        # 10% test holdout, 90% training

# Dynamic AIMD Concurrency Controller
class _ConcurrencyController:
    def __init__(self):
        self.current = 5
        self.max_allowed = 15
        self.min_allowed = 1
        self.success_streak = 0
        
    def setup(self, initial: int):
        self.current = initial
        self.max_allowed = max(initial, 15)
        self.success_streak = 0
        
    def decrease(self):
        """Multiplicative decrease on 429 Rate Limit."""
        new_limit = max(self.min_allowed, int(self.current * 0.5))
        self.current = new_limit
        self.success_streak = 0
        
    def increase(self):
        """Additive increase on sustained success."""
        self.success_streak += 1
        if self.success_streak >= 15:  # Require 15 consecutive clean API calls to bump concurrency
            if self.current < self.max_allowed:
                self.current += 1
            self.success_streak = 0

CONCURRENCY_CONTROLLER = _ConcurrencyController()
