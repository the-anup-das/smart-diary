"""
Configuration for the synthetic-data distillation pipeline.

Values come from the environment. The app's root `.env` is loaded first (it holds the Google
keys the judge overflow uses), then `data_pipeline/.env`, which wins on conflicts. Nothing here
touches the filesystem at import time; entry points call `ensure_dirs()`.

Endpoint specs are `base_url|key|model[|extra_json]`, several separated by `;`. The key is
either `env:NAME` (read from the environment; the entry is skipped when NAME is unset) or a
literal such as `lm-studio`. `extra_json` holds request parameters sent only to that host,
for example `{"reasoning_effort": "low", "max_tokens": 800}`, plus an optional `rpm` cap.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from data_pipeline.endpoints import Endpoint, parse_endpoint, parse_endpoint_list

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=True)

# ---------------------------------------------------------------- paths
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
RAW_DATASET_PATH = OUTPUT_DIR / "dataset_raw.jsonl"          # every approved sample, with meta
TRAIN_DATASET_PATH = OUTPUT_DIR / "training_dataset.jsonl"   # written by scripts/build_splits.py
TEST_DATASET_PATH = OUTPUT_DIR / "test_dataset.jsonl"
SPLITS_MANIFEST_PATH = OUTPUT_DIR / "splits_manifest.json"
LESSONS_PATH = OUTPUT_DIR / "lessons.json"
JUDGE_DISAGREEMENTS_PATH = OUTPUT_DIR / "judge_disagreements.jsonl"
JUDGE_REPUTATION_PATH = OUTPUT_DIR / "judge_reputation.json"
TELEMETRY_LOG_PATH = LOGS_DIR / "telemetry.jsonl"
REJECTIONS_LOG_PATH = LOGS_DIR / "rejections.log"
CALLS_LOG_PATH = LOGS_DIR / "calls.jsonl"          # one line per model call: latency, tokens, tokens per second


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


# ---------------------------------------------------------------- default endpoint
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.eolarityinnovations.com/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")


def require_api_key() -> None:
    if not LLM_API_KEY:
        raise SystemExit(
            "LLM_API_KEY is not set. Put it in data_pipeline/.env (never in the repo); "
            "it is the key for LLM_BASE_URL, the endpoint that writes and labels entries."
        )


# ---------------------------------------------------------------- roles
# The writer list is rotated per batch so entry style is not one model's fingerprint. The owner
# currently runs a single writer; add more models separated by commas to rotate.
WRITER_MODELS = [m.strip() for m in os.getenv("WRITER_MODELS", os.getenv("WRITER_MODEL", DEFAULT_MODEL)).split(",") if m.strip()]
WRITER_BATCH_SIZE = _int("WRITER_BATCH_SIZE", 25)
EDITOR_MODEL = os.getenv("EDITOR_MODEL", DEFAULT_MODEL)
REVIEWER_MODEL = os.getenv("REVIEWER_MODEL", DEFAULT_MODEL)
# One fixed teacher for the whole dataset, so the labels keep a single calibration.
ANALYZER_MODEL = os.getenv("ANALYZER_MODEL", DEFAULT_MODEL)


def _extra_json(var: str) -> dict:
    """A JSON object of request parameters from an env var, for example REVIEWER_EXTRA='{"reasoning_effort": "low"}'."""
    raw = os.getenv(var, "").strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"{var} must be a JSON object, got {raw!r}: {e}") from e
    if not isinstance(value, dict):
        raise SystemExit(f"{var} must be a JSON object, got {raw!r}")
    return value


def role_endpoint(role: str, model: str | None = None) -> Endpoint:
    """A single-endpoint role. `<ROLE>_BASE_URL`, `<ROLE>_API_KEY`, `<ROLE>_MODEL` and `<ROLE>_EXTRA`
    (a JSON object of request parameters, such as reasoning effort) override the defaults."""
    prefix = role.upper()
    return Endpoint(
        base_url=os.getenv(f"{prefix}_BASE_URL", LLM_BASE_URL).rstrip("/"),
        api_key=os.getenv(f"{prefix}_API_KEY", LLM_API_KEY) or "empty",
        model=model or os.getenv(f"{prefix}_MODEL", DEFAULT_MODEL),
        name=role,
        extra=_extra_json(f"{prefix}_EXTRA"),
    )


# ---------------------------------------------------------------- judges
# Judges in order: Bonsai 27B on the owner's endpoint (a different family from the analyzer,
# fully private), then the owner's LM Studio model, then the Google AI Studio free tier as
# overflow, one entry per key. Entries whose key is unset are skipped.
BONSAI_MODEL = os.getenv("BONSAI_MODEL", "Ternary-Bonsai-2-27B")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "google/gemma-4-26b-a4b")
LMSTUDIO_EXTRA = os.getenv("LMSTUDIO_EXTRA", "").strip()   # JSON object of request parameters for the LM Studio judge
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GEMINI_JUDGE_MODEL = os.getenv("GEMINI_JUDGE_MODEL", "gemini-3.6-flash")
_GEMINI_EXTRA = '{"reasoning_effort": "low", "max_tokens": 800}'
DEFAULT_JUDGE_ENDPOINTS = ";".join([
    f"{LLM_BASE_URL}|env:LLM_API_KEY|{BONSAI_MODEL}",
    f"{LMSTUDIO_BASE_URL}|lm-studio|{LMSTUDIO_MODEL}" + (f"|{LMSTUDIO_EXTRA}" if LMSTUDIO_EXTRA else ""),
    f"{GEMINI_BASE_URL}|env:GOOGLE_API_KEY|{GEMINI_JUDGE_MODEL}|{_GEMINI_EXTRA}",
    f"{GEMINI_BASE_URL}|env:GOOGLE_API_KEY_podcast|{GEMINI_JUDGE_MODEL}|{_GEMINI_EXTRA}",
])
JUDGE_ENDPOINTS_SPEC = os.getenv("JUDGE_ENDPOINTS", DEFAULT_JUDGE_ENDPOINTS)

# Second judge. Unset, the second opinion comes from another host in the judge list; set it to a
# dedicated endpoint spec to use one model for every second opinion, for example
# https://api.cerebras.ai/v1|env:CEREBRAS_API_KEY|gpt-oss-120b|{"rpm": 5, "max_tokens": 800, "reasoning_effort": "medium"}
JUDGE2_ENDPOINT_SPEC = os.getenv("JUDGE2_ENDPOINT", "")
# Every sample gets a second judge from a different host by default: an overturned pass is the
# error that would poison training data. Lower the rates to save calls.
JUDGE2_SAMPLE_RATE = _float("JUDGE2_SAMPLE_RATE", 1.0)        # share of first-judge passes re-judged
JUDGE2_FAIL_SAMPLE_RATE = _float("JUDGE2_FAIL_SAMPLE_RATE", 1.0)  # share of final fails re-judged, for reputation and lessons

# Reputation per judge host: reward on agreement, larger penalties on overturned verdicts.
JUDGE_REP_AGREE = _int("JUDGE_REP_AGREE", 1)
JUDGE_REP_OVERTURNED_PASS = _int("JUDGE_REP_OVERTURNED_PASS", -3)
JUDGE_REP_OVERTURNED_FAIL = _int("JUDGE_REP_OVERTURNED_FAIL", -1)
JUDGE_REP_STRICT_BELOW = _int("JUDGE_REP_STRICT_BELOW", -5)   # below this score a judge must award more points to pass a sample

JUDGE_THRESHOLD = _int("JUDGE_THRESHOLD", 7)      # overall score needed to pass
JUDGE_SAFETY_MIN = _int("JUDGE_SAFETY_MIN", 8)    # safety score needed to pass


def judge_endpoints() -> list[Endpoint]:
    return parse_endpoint_list(JUDGE_ENDPOINTS_SPEC, name="judge")


def judge2_endpoint() -> Endpoint | None:
    return parse_endpoint(JUDGE2_ENDPOINT_SPEC, name="judge2") if JUDGE2_ENDPOINT_SPEC.strip() else None


# ---------------------------------------------------------------- generation knobs
SEED = _int("SEED", 3407)
PERSONA_PROMPT_RATE = _float("PERSONA_PROMPT_RATE", 0.15)   # production personas are mostly empty
EDGE_CASE_RATE = _float("EDGE_CASE_RATE", 0.30)
MAX_EDITOR_ITERATIONS = _int("MAX_EDITOR_ITERATIONS", 3)
MAX_SCHEMA_RETRY = _int("MAX_SCHEMA_RETRY", 2)
MAX_JUDGE_RETRY = _int("MAX_JUDGE_RETRY", 1)                # repair the analysis once with the judge's critique before discarding
MAX_ENTRY_REPAIR = _int("MAX_ENTRY_REPAIR", 1)              # send the entry back to the writer once when the judge faults the text
LESSONS_MAX = _int("LESSONS_MAX", 8)
TEST_SPLIT_RATIO = _float("TEST_SPLIT_RATIO", 0.10)

MAX_TOKENS_ENTRY = _int("MAX_TOKENS_ENTRY", 900)
MAX_TOKENS_REVIEW = _int("MAX_TOKENS_REVIEW", 400)
MAX_TOKENS_ANALYSIS = _int("MAX_TOKENS_ANALYSIS", 2048)
MAX_TOKENS_JUDGE = _int("MAX_TOKENS_JUDGE", 800)
REQUEST_TIMEOUT_S = _float("REQUEST_TIMEOUT_S", 180.0)   # a 30B model writing a full analysis can take a while under load

# How many requests one server may be generating at once. A 30B model that fills most of a card
# batches two generations well; more makes it shift context and every request slows down. Raise
# it only for a server with spare memory. HOST_LIMITS overrides it per host, and per model where
# a gateway fronts several of them on different hardware:
#   HOST_LIMITS=api.example.com=2;api.example.com/Small-Model=6;127.0.0.1:1234=1
MAX_CONCURRENT_PER_HOST = _int("MAX_CONCURRENT_PER_HOST", 2)
HOST_PACING_S = _float("HOST_PACING_S", 0.5)             # pause between starts, so the server can free the last request's cache
_HOST_LIMITS_SPEC = os.getenv("HOST_LIMITS", "")


def _parse_host_limits(spec: str) -> dict[str, int]:
    limits: dict[str, int] = {}
    for part in (p.strip() for p in spec.split(";") if p.strip()):
        key, _, value = part.rpartition("=")
        if not key.strip() or not value.strip().isdigit():
            raise SystemExit(f"HOST_LIMITS must look like host=2;host/model-id=4;other:1234=1, got {part!r}")
        limits[key.strip()] = max(1, int(value))
    return limits


HOST_LIMITS = _parse_host_limits(_HOST_LIMITS_SPEC)

# How a host's models share their hardware, which decides what the limit counts:
#   separate  each model has its own backend (a gateway in front of several instances), so the
#             limit applies per model and two models run side by side
#   shared    one GPU too small to hold two of them, so the limit applies to the host and a call
#             for another model waits for it to drain: the server swaps between batches, not
#             during them
#   mixed     the default: the limit applies to the host and models may run together
#   HOST_MODELS=api.example.com=separate;127.0.0.1:1234=shared
HOST_MODES = ("separate", "shared", "mixed")


def _parse_host_modes(spec: str) -> dict[str, str]:
    modes: dict[str, str] = {}
    for part in (p.strip() for p in spec.replace(";", ",").split(",") if p.strip()):
        host, _, mode = part.partition("=")
        if not host.strip() or mode.strip() not in HOST_MODES:
            raise SystemExit(f"HOST_MODELS must look like host=separate or host=shared (one of {HOST_MODES}), got {part!r}")
        modes[host.strip()] = mode.strip()
    return modes


HOST_MODEL_MODES = _parse_host_modes(os.getenv("HOST_MODELS", ""))


def host_limit(host: str, model: str | None = None) -> int:
    """The cap for this model on this host: `host/model` if it is set, else the host's, else the default."""
    if model and f"{host}/{model}" in HOST_LIMITS:
        return HOST_LIMITS[f"{host}/{model}"]
    return HOST_LIMITS.get(host, MAX_CONCURRENT_PER_HOST)


def host_model_mode(host: str) -> str:
    return HOST_MODEL_MODES.get(host, HOST_MODEL_MODES.get("*", "mixed"))
ENDPOINT_COOLDOWN_S = _float("ENDPOINT_COOLDOWN_S", 90.0)
MAX_CONSECUTIVE_CRASHES = _int("MAX_CONSECUTIVE_CRASHES", 8)   # stop the run instead of retrying a dead endpoint forever

# Cost per million tokens for the default endpoint; the owner's server is free, so 0 by default.
LLM_PRICE_IN = _float("LLM_PRICE_IN", 0.0)
LLM_PRICE_OUT = _float("LLM_PRICE_OUT", 0.0)


# ---------------------------------------------------------------- AIMD concurrency
class _ConcurrencyController:
    """Additive increase on clean calls, multiplicative decrease on rate limits."""

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
        self.current = max(self.min_allowed, int(self.current * 0.5))
        self.success_streak = 0

    def increase(self):
        self.success_streak += 1
        if self.success_streak >= 15:
            if self.current < self.max_allowed:
                self.current += 1
            self.success_streak = 0


CONCURRENCY_CONTROLLER = _ConcurrencyController()
