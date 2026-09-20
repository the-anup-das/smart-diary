import os
import openai

def get_llm_client() -> openai.OpenAI:
    """
    Returns an OpenAI client configured for either the external OpenAI API
    or the local SGLang Docker container, based on the USE_LOCAL_LLM flag.
    """
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    
    if use_local:
        return openai.OpenAI(
            api_key="empty",
            base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://sglang:30000/v1")
        )
    else:
        return openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", None)
        )

def get_model_name() -> str:
    """
    Returns the correct model string identifier based on the routing strategy.
    """
    use_local = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    return "default" if use_local else os.getenv("CHAT_MODEL", "gpt-4o-mini")
