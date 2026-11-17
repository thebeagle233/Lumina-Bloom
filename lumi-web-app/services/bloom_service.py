from __future__ import annotations

import os
from typing import Any, Dict, List

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _configuration() -> Dict[str, str]:
    return {
        "api_base_url": os.getenv("BLOOM_API_BASE_URL") or "http://127.0.0.1:8080/v1",
        "api_key": os.getenv("BLOOM_API_KEY") or "local",
        "model": os.getenv("BLOOM_MODEL") or "qwen-local",
    }

SYSTEM_PROMPT = """
You are Bloom, a tiny comforting plant companion inside a sunlight habit app.

Your job:
- speak gently, warmly, and briefly
- comfort the user without sounding clinical
- reflect the user's current state and sunlight pattern
- encourage tiny, low-pressure healthy actions
- never diagnose disease
- never claim medical certainty
- do not mention that you are an AI model

Style:
- 2 to 5 sentences
- soft, emotionally grounded, toy-like, reassuring
- if the user sounds tired or stressed, reduce pressure
- if sunlight is low today, suggest a tiny outside step only if it feels gentle
- if the user already did well today, praise them softly
""".strip()


HARDCODED_REPLY = "I'm here with you. We can keep this moment soft. Tell me how your body feels, and I'll stay with you for a bit."


def bloom_health() -> Dict[str, Any]:
    config = _configuration()
    return {
        "enabled": True,
        "api_base_url": config["api_base_url"],
        "model": config["model"],
        "api_key_configured": bool(os.getenv("BLOOM_API_KEY")),
    }


def _trim_history(history: List[Dict[str, str]] | None) -> List[Dict[str, str]]:
    history = history or []
    out: List[Dict[str, str]] = []
    for item in history[-8:]:
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content})
    return out


def _build_messages(
    user_message: str,
    app_context: Dict[str, Any],
    chat_history: List[Dict[str, str]] | None,
) -> List[Dict[str, str]]:
    compact_context = {
        "sunlight_today_min": app_context.get("sunlight_today_min"),
        "sunlight_7d_avg_min": app_context.get("sunlight_7d_avg_min"),
        "stress_label": app_context.get("stress_label"),
        "stress_pct": app_context.get("stress_pct"),
        "slacking_probability_pct": app_context.get("slacking_probability_pct"),
        "weather_summary": app_context.get("weather_summary"),
        "body_state": app_context.get("body_state"),
        "recent_skip_reasons": app_context.get("recent_skip_reasons"),
        "bloom_stage": app_context.get("bloom_stage"),
    }

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current app context: {compact_context}"},
    ]
    messages.extend(_trim_history(chat_history))
    messages.append({"role": "user", "content": user_message})
    return messages


def _chat_openai_compatible(
    user_message: str,
    app_context: Dict[str, Any],
    chat_history: List[Dict[str, str]] | None,
) -> Dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("openai package not installed")

    config = _configuration()
    client = OpenAI(api_key=config["api_key"], base_url=config["api_base_url"], timeout=20.0, max_retries=0)
    response = client.chat.completions.create(
        model=config["model"],
        messages=_build_messages(user_message, app_context, chat_history),
        temperature=0.7,
    )
    reply = (response.choices[0].message.content or "").strip()
    if not reply:
        reply = HARDCODED_REPLY
    return {
        "provider": f"openai-compatible:{config['model']}",
        "reply": reply,
        "fallback_used": False,
    }


def chat_with_bloom(
    user_message: str,
    app_context: Dict[str, Any],
    chat_history: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    try:
        return _chat_openai_compatible(user_message, app_context, chat_history)
    except Exception:
        return {
            "provider": "bloom-fallback",
            "reply": HARDCODED_REPLY,
            "fallback_used": True,
            "fallback_reason": "Bloom model unavailable; using a built-in companion reply.",
        }
