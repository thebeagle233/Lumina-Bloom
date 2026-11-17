from __future__ import annotations

import json
import os
from typing import Any, Dict, List

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


SYSTEM_PROMPT = """
You are Lumi, a gentle sunlight habit coach inside a gamified wellness app.
You receive a JSON object with user context, weather, recent habit data, and candidate outdoor places.

Return ONLY valid JSON using this schema:
{
  "nudge_text": string,
  "suggested_duration_min": integer,
  "decision_type": string,
  "tone": string,
  "reason_tags": [string],
  "follow_up_options": [string],
  "place_recommendations": [
    {
      "name": string,
      "distance_m": integer,
      "map_url": string,
      "recommendation_score": integer,
      "recommendation_label": string,
      "why": string
    }
  ],
  "biometric_estimate": {
    "stress_label": "LOW" | "MODERATE" | "HIGH",
    "stress_pct": integer,
    "slacking_probability_pct": integer,
    "slack_subtext": string
  }
}

Rules:
- Select exactly 3 places if at least 3 candidate places are available.
- Choose only from the provided candidate_places list.
- Sort place_recommendations by recommendation_score descending.
- recommendation_score must be an integer from 0 to 100.
- recommendation_label must be one of: "Excellent", "Good", "Okay".
- The UI is in English, so all generated reasons must be in English.
- Be concise and warm.
- Favor recommendations that are easy to follow right now.
- If weather is poor or UV is unsafe, recommend a very short break or a delayed reminder.
- Never mention that you are an LLM.
""".strip()

HARDCODED_FALLBACK = {
    "provider": "hardcoded-fallback",
    "nudge_text": "A 5-minute outdoor break is enough for now.",
    "suggested_duration_min": 5,
    "decision_type": "go_out_now",
    "tone": "gentle",
    "reason_tags": ["fallback"],
    "follow_up_options": ["Try 5 minutes", "Try again later", "Log manually"],
    "place_recommendations": [],
    "biometric_estimate": {
        "stress_label": "MODERATE",
        "stress_pct": 45,
        "slacking_probability_pct": 35,
        "slack_subtext": "Fallback mode is active, so nudges are simplified.",
    },
}


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start : end + 1])


def _heuristic_biometrics(context: Dict[str, Any]) -> Dict[str, Any]:
    recent = _as_dict(context.get("recent_behavior"))
    feedbacks = _as_list(recent.get("skip_reasons"))
    mood_count = sum(1 for item in feedbacks if item == "mood")
    busy_count = sum(1 for item in feedbacks if item == "busy")
    lazy_count = sum(1 for item in feedbacks if item == "lazy")

    stress_pct = 45 + 20 * mood_count + 8 * busy_count - 12 * lazy_count
    stress_pct = max(15, min(90, stress_pct))
    if stress_pct >= 75:
        label = "HIGH"
        slack_prob = min(85, stress_pct)
        subtext = "Current stress pattern suggests a higher chance of skipping unless the goal stays tiny."
    elif stress_pct >= 45:
        label = "MODERATE"
        slack_prob = min(70, stress_pct - 5)
        subtext = "A small, low-friction outdoor break is more likely to stick today."
    else:
        label = "LOW"
        slack_prob = max(20, stress_pct - 10)
        subtext = "Stress looks manageable, so this is a good window for habit reinforcement."
    return {
        "stress_label": label,
        "stress_pct": int(stress_pct),
        "slacking_probability_pct": int(slack_prob),
        "slack_subtext": subtext,
    }


def _heuristic_recommendation(context: Dict[str, Any]) -> Dict[str, Any]:
    context = _as_dict(context)
    weather = _as_dict(context.get("weather"))
    places_payload = _as_dict(context.get("places"))
    candidate_places = _as_list(places_payload.get("candidate_places") or places_payload.get("places"))
    biometrics = _heuristic_biometrics(context)

    uv = float(weather.get("uv_index") or 0)
    temp = float(weather.get("temperature_c") or 22)
    precipitation = float(weather.get("precipitation") or 0)
    cloud_cover = float(weather.get("cloud_cover") or 0)
    recent_avg = float((_as_dict(context.get("recent_behavior")).get("last_7d_avg_minutes")) or 8)

    duration = 10
    decision_type = "go_out_now"
    tone = "gentle"
    reason_tags: List[str] = []

    if biometrics["stress_label"] == "HIGH":
        duration = 6
        tone = "calming"
        reason_tags.append("stress_relief")
    elif recent_avg >= 20:
        duration = 12
        reason_tags.append("habit_momentum")

    if uv < 1:
        duration = min(duration, 5)
        decision_type = "delay"
        reason_tags.extend(["low_uv", "delay_recommended"])
        nudge_text = "Sunlight is weak right now. Try a 5-minute outdoor reset later when the light improves."
    elif uv > 8:
        duration = min(duration, 6)
        decision_type = "seek_shade"
        reason_tags.extend(["uv_high", "short_break"])
        nudge_text = "UV is strong now, so keep it short. A quick 5–6 minute walk with partial shade is the safest move."
    elif precipitation > 0.2:
        duration = min(duration, 5)
        decision_type = "delay"
        reason_tags.extend(["rain_risk", "delay_recommended"])
        nudge_text = "A short break still helps, but rain is starting. I would wait for a drier window and keep today's goal tiny."
    else:
        if 2 <= uv <= 7:
            reason_tags.append("good_uv")
        if 18 <= temp <= 30:
            reason_tags.append("comfortable_temp")
        if cloud_cover < 60:
            reason_tags.append("good_light")
        nudge_text = f"Conditions look good for a low-effort reset. Try a {duration}-minute sunlight walk to keep your streak alive."

    selected_places = []
    for idx, place in enumerate(candidate_places[:3]):
        if not isinstance(place, dict):
            continue
        distance = int(place.get("distance_m", 0) or 0)
        walk_min = int(place.get("walk_min", max(1, round(distance / 80))) or max(1, round(distance / 80)))
        place_type = str(place.get("type", "outdoor_spot"))
        score = 88 - idx * 8
        if place_type == "park":
            score += 4
        if biometrics["stress_label"] == "HIGH" and walk_min <= 3:
            score += 4
        score = max(55, min(99, score))
        label = "Excellent" if score >= 85 else "Good" if score >= 70 else "Okay"
        why = f"{place_type.title()} about {walk_min} min away, easy for a short sunlight reset."
        if biometrics["stress_label"] == "HIGH":
            why = "Close and low-friction, which makes it easier to step outside even on a high-stress day."
        selected_places.append(
            {
                "name": str(place.get("name", "Nearby outdoor spot")),
                "distance_m": distance,
                "map_url": str(place.get("map_url", "")),
                "recommendation_score": int(score),
                "recommendation_label": label,
                "why": why,
            }
        )

    follow_up_options = [
        "Find a nearby sunny spot",
        "Keep it to just 5 minutes",
        "Remind me again later",
    ]
    if decision_type == "seek_shade":
        follow_up_options[0] = "Show a nearby shaded green spot"
    elif decision_type == "delay":
        follow_up_options[2] = "Check conditions again in 1 hour"

    return {
        "provider": "heuristic",
        "nudge_text": nudge_text,
        "suggested_duration_min": int(duration),
        "decision_type": decision_type,
        "tone": tone,
        "reason_tags": reason_tags,
        "follow_up_options": follow_up_options,
        "place_recommendations": selected_places,
        "biometric_estimate": biometrics,
    }


def _openai_recommendation(context: Dict[str, Any]) -> Dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("openai package not installed")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    client = OpenAI(api_key=api_key, timeout=20.0, max_retries=0)
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=json.dumps(context, ensure_ascii=False),
    )
    output_text = getattr(response, "output_text", "") or ""
    parsed = _extract_json(output_text)
    parsed["provider"] = f"openai:{model}"
    return parsed


def _deepseek_recommendation(context: Dict[str, Any]) -> Dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("openai package not installed")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not configured")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=20.0, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nReturn strictly valid JSON only. Do not include markdown fences."},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    output_text = response.choices[0].message.content or ""
    parsed = _extract_json(output_text)
    parsed["provider"] = f"deepseek:{model}"
    return parsed


def _configured_provider() -> str:
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider:
        return provider
    if os.getenv("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "heuristic"


def _model_recommendation(context: Dict[str, Any]) -> Dict[str, Any]:
    provider = _configured_provider()
    if provider == "openai":
        return _openai_recommendation(context)
    if provider == "deepseek":
        return _deepseek_recommendation(context)
    if provider == "heuristic":
        return _heuristic_recommendation(context)
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def generate_agent_recommendation(context: Dict[str, Any]) -> Dict[str, Any]:
    context = _as_dict(context)
    provider = _configured_provider()
    try:
        result = _model_recommendation(context)
        result["selected_provider"] = provider
        result["fallback_used"] = False
        return result
    except Exception:
        try:
            result = _heuristic_recommendation(context)
            result["selected_provider"] = provider
            result["fallback_used"] = True
            result["fallback_reason"] = "Configured provider unavailable; using local heuristics."
            return result
        except Exception:
            fallback = HARDCODED_FALLBACK.copy()
            fallback["selected_provider"] = provider
            fallback["fallback_used"] = True
            fallback["fallback_reason"] = "Recommendation unavailable; using a built-in suggestion."
            return fallback
