"""LLM Client utility for executing async chat completion calls across pipeline agents."""

import asyncio
from openai import AsyncOpenAI
from data_pipeline import config

_client = None
_client_lock = asyncio.Lock()

# Per-model pricing (per 1M tokens) — covers the models we use in this pipeline
# Source: OpenRouter / Together AI pricing pages
MODEL_PRICING = {
    # Qwen3 30B A3B (MoE, only 3B active) — very cheap
    "qwen/qwen3-30b-a3b-instruct": {"input": 0.20, "output": 0.50},
    "qwen/qwen3-30b-a3b": {"input": 0.20, "output": 0.50},
    # Gemma 2 9B
    "google/gemma-2-9b-it": {"input": 0.08, "output": 0.08},
}
DEFAULT_PRICING = {"input": 0.25, "output": 0.60}


async def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        async with _client_lock:
            # Double-check inside lock (another coroutine may have created it)
            if _client is None:
                _client = AsyncOpenAI(
                    api_key=config.LLM_API_KEY,
                    base_url=config.LLM_BASE_URL,
                )
    return _client


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost using per-model pricing."""
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


async def acall_llm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_retries: int = 3,
) -> tuple[str, dict]:
    """Invokes the LLM asynchronously with retry logic, returning the text and usage telemetry."""
    import random
    client = await get_client()
    last_error = None

    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            
            # API call succeeded
            config.CONCURRENCY_CONTROLLER.increase()

            content = response.choices[0].message.content
            if content is None:
                content = ""
            content = content.strip()

            usage = response.usage
            p_tok = usage.prompt_tokens if usage else 0
            c_tok = usage.completion_tokens if usage else 0

            usage_info = {
                "tokens": p_tok + c_tok,
                "cost": calculate_cost(model, p_tok, c_tok),
            }

            return content, usage_info

        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            
            # Detect Rate Limit (429)
            if "429" in err_str or "rate limit" in err_str:
                config.CONCURRENCY_CONTROLLER.decrease()
            
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                wait = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait)

    # All retries exhausted
    raise last_error
