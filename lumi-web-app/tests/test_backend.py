import os
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app import create_app
from services import agent_service, bloom_service, weather_service


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_invalid_coordinates_are_rejected_before_network_calls(self):
        invalid = ["lat=91&lon=0", "lat=0&lon=-181", "lat=nan&lon=0", "lat=0&lon=inf", "lat=0", "lat=no&lon=0"]
        for endpoint, target in [("weather", "app.fetch_weather_snapshot"), ("places", "app.fetch_sunny_places")]:
            with patch(target, return_value={}) as lookup:
                for query in invalid:
                    with self.subTest(endpoint=endpoint, query=query):
                        self.assertEqual(self.client.get(f"/api/{endpoint}?{query}").status_code, 400)
                lookup.assert_not_called()

    def test_radius_is_bounded_and_invalid_values_are_rejected(self):
        with patch("app.fetch_sunny_places", return_value={"candidate_places": []}) as lookup:
            for radius in ["0", "-1", "5001", "no", "1.5"]:
                with self.subTest(radius=radius):
                    self.assertEqual(self.client.get(f"/api/places?lat=0&lon=0&radius={radius}").status_code, 400)
            lookup.assert_not_called()
            self.assertEqual(self.client.get("/api/places?lat=0&lon=0&radius=100").status_code, 200)
            lookup.assert_called_once_with(lat=0.0, lon=0.0, radius_m=100)

    def test_non_object_and_malformed_json_return_400(self):
        for endpoint in ["/api/agent/recommend", "/api/bloom/chat"]:
            for payload in [[], [1], "hello", 5, None]:
                with self.subTest(endpoint=endpoint, payload=payload):
                    response = self.client.post(endpoint, json=payload)
                    self.assertEqual(response.status_code, 400)
            response = self.client.post(endpoint, data="{bad", content_type="application/json")
            self.assertEqual(response.status_code, 400)

    def test_invalid_bloom_shapes_return_400_without_model_call(self):
        cases = [{"message": 5}, {"message": " "}, {"message": "hi", "context": []}, {"message": "hi", "history": {}}, {"message": "hi", "history": [5]}, {"message": "hi", "history": [{"role": "user", "content": []}]}]
        with patch("app.chat_with_bloom", return_value={}) as chat:
            for payload in cases:
                with self.subTest(payload=payload):
                    self.assertEqual(self.client.post("/api/bloom/chat", json=payload).status_code, 400)
            chat.assert_not_called()

    def test_invalid_agent_context_shapes_return_400(self):
        with patch("app.generate_agent_recommendation", return_value={}) as recommend:
            for payload in [{"weather": []}, {"recent_behavior": "busy"}, {"places": {"candidate_places": "park"}}, {"places": {"candidate_places": ["park"]}}]:
                with self.subTest(payload=payload):
                    self.assertEqual(self.client.post("/api/agent/recommend", json=payload).status_code, 400)
            recommend.assert_not_called()

    def test_non_string_history_role_returns_400(self):
        try:
            response = self.client.post("/api/bloom/chat", json={"message": "hi", "history": [{"role": [], "content": "hello"}]})
        except TypeError:
            self.fail("A malformed history role must return 400 instead of raising")
        self.assertEqual(response.status_code, 400)

    def test_valid_bloom_message_reaches_service(self):
        with patch("app.chat_with_bloom", return_value={"reply": "Hello", "fallback_used": False}) as chat:
            response = self.client.post("/api/bloom/chat", json={"message": " hi ", "context": {}, "history": []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["reply"], "Hello")
        chat.assert_called_once_with(user_message="hi", app_context={}, chat_history=[])

    def test_weather_and_places_fallbacks_do_not_expose_exception_details(self):
        for endpoint, target in [("weather", "app.fetch_weather_snapshot"), ("places", "app.fetch_sunny_places")]:
            with self.subTest(endpoint=endpoint), patch(target, side_effect=RuntimeError("private-test-value")), patch.object(self.app.logger, "exception"):
                response = self.client.get(f"/api/{endpoint}?lat=0&lon=0")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["source"], "fallback")
                self.assertNotIn("private-test-value", response.get_data(as_text=True))

    def test_location_environment_is_validated_for_template(self):
        with patch.dict(os.environ, {"DEFAULT_LOCATION_LAT": "nan", "DEFAULT_LOCATION_LON": "181"}), patch("app.render_template", return_value="page") as render:
            self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(render.call_args.kwargs.get("default_location_lat"), 22.3193)
        self.assertEqual(render.call_args.kwargs.get("default_location_lon"), 114.1694)
        with patch.dict(os.environ, {"DEFAULT_LOCATION_LAT": "0", "DEFAULT_LOCATION_LON": "-73.5"}), patch("app.render_template", return_value="page") as render:
            self.client.get("/")
        self.assertEqual(render.call_args.kwargs["default_location_lat"], 0.0)
        self.assertEqual(render.call_args.kwargs["default_location_lon"], -73.5)

    def test_debug_is_off_by_default(self):
        with patch.dict(os.environ, {}, clear=True), patch("flask.Flask.run") as run:
            runpy.run_path(str(Path(__file__).resolve().parents[1] / "app.py"), run_name="__main__")
        self.assertFalse(run.call_args.kwargs["debug"])


class ModelTests(unittest.TestCase):
    def test_bloom_uses_runtime_environment_and_bounded_network_settings(self):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="A gentle hello."))])
        with patch.dict(os.environ, {"BLOOM_API_BASE_URL": "http://127.0.0.1:9000/v1", "BLOOM_API_KEY": "test-local", "BLOOM_MODEL": "runtime-model"}), patch.object(bloom_service, "OpenAI", return_value=client) as constructor:
            result = bloom_service.chat_with_bloom("hello", {}, [])
            health = bloom_service.bloom_health()
        self.assertEqual(result["reply"], "A gentle hello.")
        self.assertFalse(result["fallback_used"])
        constructor.assert_called_once_with(api_key="test-local", base_url="http://127.0.0.1:9000/v1", timeout=20.0, max_retries=0)
        self.assertEqual(client.chat.completions.create.call_args.kwargs["model"], "runtime-model")
        self.assertEqual(health["model"], "runtime-model")

    def test_bloom_has_documented_local_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            health = bloom_service.bloom_health()
        self.assertEqual(health["api_base_url"], "http://127.0.0.1:8080/v1")
        self.assertEqual(health["model"], "qwen-local")

    def test_model_failure_reasons_do_not_expose_exception_details(self):
        with patch.object(bloom_service, "_chat_openai_compatible", side_effect=RuntimeError("private-test-value")):
            result = bloom_service.chat_with_bloom("hello", {}, [])
        self.assertTrue(result["fallback_used"])
        self.assertNotIn("private-test-value", str(result))
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}), patch.object(agent_service, "_model_recommendation", side_effect=RuntimeError("private-test-value")):
            result = agent_service.generate_agent_recommendation({})
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["provider"], "heuristic")
        self.assertNotIn("private-test-value", str(result))

    def test_main_model_clients_use_bounded_network_settings(self):
        client = Mock()
        client.responses.create.return_value.output_text = '{"nudge_text":"hello"}'
        client.chat.completions.create.return_value.choices = [SimpleNamespace(message=SimpleNamespace(content='{"nudge_text":"hello"}'))]
        for provider in ["openai", "deepseek"]:
            with self.subTest(provider=provider), patch.dict(os.environ, {"OPENAI_API_KEY": "test-value", "DEEPSEEK_API_KEY": "test-value"}), patch.object(agent_service, "OpenAI", return_value=client) as constructor:
                getattr(agent_service, f"_{provider}_recommendation")({})
                self.assertEqual(constructor.call_args.kwargs.get("timeout"), 20.0)
                self.assertEqual(constructor.call_args.kwargs.get("max_retries"), 0)

    def test_heuristic_keeps_three_candidate_places_and_uv_decisions(self):
        places = [{"name": f"Park {i}", "distance_m": 100 * i, "type": "park", "map_url": "https://www.openstreetmap.org/"} for i in range(1, 5)]
        with patch.dict(os.environ, {"LLM_PROVIDER": "heuristic"}):
            result = agent_service.generate_agent_recommendation({"weather": {"uv_index": 9}, "places": {"candidate_places": places}})
        self.assertEqual(result["decision_type"], "seek_shade")
        self.assertEqual(len(result["place_recommendations"]), 3)
        self.assertFalse(result["fallback_used"])


class WeatherTests(unittest.TestCase):
    def test_optional_air_quality_failure_preserves_current_weather_and_uv(self):
        weather = Mock()
        weather.json.return_value = {"current": {"time": "2026-11-17T14:00", "temperature_2m": 20, "uv_index": 3.5, "is_day": 1}}
        with patch.object(weather_service.requests, "get", side_effect=[weather, weather_service.requests.RequestException("unavailable")]):
            try:
                result = weather_service.fetch_weather_snapshot(0, 0)
            except weather_service.requests.RequestException:
                self.fail("An optional AQI outage must preserve the successful weather response")
        self.assertEqual(result["source"], "open-meteo")
        self.assertEqual(result["temperature_c"], 20)
        self.assertEqual(result["uv_index"], 3.5)
        self.assertIsNone(result["aqi_us"])

    def test_current_weather_uv_is_used_and_air_quality_is_enriched(self):
        weather, air = Mock(), Mock()
        weather.json.return_value = {"current": {"temperature_2m": 21, "uv_index": 0, "is_day": 0}}
        air.json.return_value = {"current": {"us_aqi": 40, "uv_index": 1.5}}
        with patch.object(weather_service.requests, "get", side_effect=[weather, air]):
            result = weather_service.fetch_weather_snapshot(22, 114)
        self.assertEqual(result["uv_index"], 0)
        self.assertFalse(result["is_day"])
        self.assertEqual(result["aqi_us"], 40)


if __name__ == "__main__":
    unittest.main()
