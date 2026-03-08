"""DeepSeek API client for PRO scenarios. Fallback to MVP logic on timeout/error."""
import logging
from typing import Optional

import httpx

from config import get_config

logger = logging.getLogger(__name__)
DEEPSEEK_CHAT_URL = "https://api.deepseek.com/v1/chat/completions"
TIMEOUT = 10.0


async def analyze_dialog_pro(
    messages_text: list[str],
    *,
    system_prompt: Optional[str] = None,
) -> Optional[dict]:
    """
    PRO: analyze dialog via DeepSeek API.
    Returns JSON-like dict with e.g. compatibility_percent, reason, recommendation.
    On timeout or error returns None (caller should use MVP logic).
    """
    config = get_config()
    if not config.deepseek_api_key:
        return None
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt or "Ты анализируешь переписку двух людей. Верни JSON: compatibility_percent (0-100), reason (строка), recommendation (строка)."}
        ]
        + [{"role": "user", "content": "\n---\n".join(messages_text)}],
        "max_tokens": 300,
        "temperature": 0.3,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                DEEPSEEK_CHAT_URL,
                json=payload,
                headers={"Authorization": f"Bearer {config.deepseek_api_key}"},
            )
            r.raise_for_status()
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            if not content:
                return None
            import json
            return json.loads(content.strip())
    except Exception as e:
        logger.warning("DeepSeek API error (fallback to MVP): %s", e)
        return None
