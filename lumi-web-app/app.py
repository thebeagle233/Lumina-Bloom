from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv(Path(__file__).with_name(".env"))

from services.agent_service import generate_agent_recommendation
from services.bloom_service import chat_with_bloom, bloom_health
from services.places_service import fetch_sunny_places
from services.weather_service import fetch_weather_snapshot


def _bounded_float(value: Any, minimum: float, maximum: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and minimum <= number <= maximum else None


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        lat = _bounded_float(os.getenv("DEFAULT_LOCATION_LAT"), -90, 90)
        lon = _bounded_float(os.getenv("DEFAULT_LOCATION_LON"), -180, 180)
        return render_template(
            "index.html",
            default_location_lat=22.3193 if lat is None else lat,
            default_location_lon=114.1694 if lon is None else lon,
        )

    @app.get("/favicon.ico")
    def favicon() -> Any:
        return ("", 204)

    @app.get("/api/health")
    def health() -> Any:
        return jsonify(
            {
                "ok": True,
                "provider": os.getenv("LLM_PROVIDER", ""),
                "openai_key_configured": bool(os.getenv("OPENAI_API_KEY")),
                "deepseek_key_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
                "openai_model": os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
                "deepseek_model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "deepseek_base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                "bloom": bloom_health(),
            }
        )

    @app.get("/api/weather")
    def weather() -> Any:
        lat = _bounded_float(request.args.get("lat"), -90, 90)
        lon = _bounded_float(request.args.get("lon"), -180, 180)
        if lat is None or lon is None:
            return jsonify({"error": "Valid lat (-90 to 90) and lon (-180 to 180) are required"}), 400
        try:
            snapshot = fetch_weather_snapshot(lat=lat, lon=lon)
            return jsonify(snapshot)
        except Exception:
            app.logger.exception("Weather lookup failed")
            return jsonify(
                {
                    "source": "fallback",
                    "latitude": lat,
                    "longitude": lon,
                    "time": None,
                    "temperature_c": 24,
                    "feels_like_c": 24,
                    "is_day": True,
                    "cloud_cover": 30,
                    "precipitation": 0,
                    "weather_code": -1,
                    "wind_speed_kmh": 5,
                    "uv_index": 4,
                    "aqi_eu": None,
                    "aqi_us": None,
                    "pm2_5": None,
                    "pm10": None,
                    "warning": "Weather lookup unavailable; showing sample conditions.",
                }
            )

    @app.get("/api/places")
    def places() -> Any:
        lat = _bounded_float(request.args.get("lat"), -90, 90)
        lon = _bounded_float(request.args.get("lon"), -180, 180)
        if lat is None or lon is None:
            return jsonify({"error": "Valid lat (-90 to 90) and lon (-180 to 180) are required"}), 400
        try:
            radius = int(request.args.get("radius", "1500"))
        except (TypeError, ValueError):
            return jsonify({"error": "radius must be an integer from 100 to 5000 metres"}), 400
        if not 100 <= radius <= 5000:
            return jsonify({"error": "radius must be an integer from 100 to 5000 metres"}), 400
        try:
            payload = fetch_sunny_places(lat=lat, lon=lon, radius_m=radius)
            return jsonify(payload)
        except Exception:
            app.logger.exception("Place lookup failed")
            return jsonify(
                {
                    "source": "fallback",
                    "count": 0,
                    "candidate_places": [],
                    "warning": "Nearby place lookup is unavailable right now.",
                }
            )

    @app.post("/api/agent/recommend")
    def recommend() -> Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "A JSON object is required"}), 400
        for field in ("user_profile", "today_context", "weather", "places", "recent_behavior", "location"):
            if payload.get(field) is not None and not isinstance(payload[field], dict):
                return jsonify({"error": f"{field} must be an object"}), 400
        places_context = payload.get("places") or {}
        candidates = places_context.get("candidate_places", places_context.get("places"))
        if candidates is not None and (
            not isinstance(candidates, list) or any(not isinstance(place, dict) for place in candidates)
        ):
            return jsonify({"error": "candidate_places must be a list of objects"}), 400
        recommendation = generate_agent_recommendation(payload)
        return jsonify(recommendation)

    @app.post("/api/bloom/chat")
    def bloom_chat() -> Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "A JSON object is required"}), 400
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip() or len(message) > 2000:
            return jsonify({"ok": False, "error": "message must contain 1 to 2000 characters"}), 400
        user_message = message.strip()

        app_context = payload.get("context", {})
        history = payload.get("history", [])
        if not isinstance(app_context, dict):
            return jsonify({"ok": False, "error": "context must be an object"}), 400
        if not isinstance(history, list) or any(
            not isinstance(item, dict)
            or item.get("role") not in ("user", "assistant")
            or not isinstance(item.get("content"), str)
            for item in history
        ):
            return jsonify({"ok": False, "error": "history must contain user or assistant messages"}), 400
        result = chat_with_bloom(
            user_message=user_message,
            app_context=app_context,
            chat_history=history,
        )
        return jsonify({"ok": True, **result})

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
