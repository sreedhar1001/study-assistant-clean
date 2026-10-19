"""HTTP smoke tests for the public static-asset boundary."""

from http.server import ThreadingHTTPServer
import json
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import StudyAssistantHandler


class StaticServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), StudyAssistantHandler)
        cls.thread = Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)

    def test_homepage_is_served(self):
        with urlopen(f"{self.base_url}/", timeout=3) as response:
            body = response.read().decode("utf-8")
        self.assertEqual(response.status, 200)
        self.assertIn("<html", body.lower())

    def test_frontend_assets_are_served(self):
        for asset in ("app.js", "styles.css", "live.css"):
            with self.subTest(asset=asset), urlopen(f"{self.base_url}/{asset}", timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertGreater(int(response.headers["Content-Length"]), 0)

    def test_provider_configuration_does_not_expose_api_keys(self):
        with patch("server.load_config", return_value={
            "TAVILY_API_KEY": "test-tavily-secret",
            "GROQ_API_KEY": "test-groq-secret",
        }):
            with urlopen(f"{self.base_url}/api/config", timeout=3) as response:
                body = response.read().decode("utf-8")
        self.assertIn('"planner_provider": "groq"', body)
        self.assertNotIn("test-tavily-secret", body)
        self.assertNotIn("test-groq-secret", body)

    def test_repository_files_are_not_served(self):
        for path in (
            "/server.py",
            "/app.py",
            "/study_aassistant.py",
            "/agents/supervisor.py",
            "/tests/test_agents.py",
            "/README.md",
            "/AGENTS.md",
        ):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                urlopen(f"{self.base_url}{path}", timeout=3)
            self.assertEqual(error.exception.code, 404)

    def test_rejects_unsupported_study_attachment_on_server(self):
        payload = {
            "provider": "tavily",
            "messages": [{"role": "user", "text": "Summarize this"}],
            "document": {"name": "notes.exe", "text": "some content"},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=3)
        self.assertEqual(error.exception.code, 400)
        self.assertIn("TXT, Markdown, CSV, or JSON", error.exception.read().decode("utf-8"))

    def test_rejects_empty_study_attachment_on_server(self):
        payload = {
            "provider": "tavily",
            "messages": [{"role": "user", "text": "Summarize this"}],
            "document": {"name": "notes.txt", "text": "  "},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=3)
        self.assertEqual(error.exception.code, 400)
        self.assertIn("empty or has no readable text", error.exception.read().decode("utf-8"))

    def test_chat_in_learning_section_respects_selected_agent(self):
        payload = {
            "provider": "tavily",
            "messages": [{"role": "user", "text": "Give me a quiz about plants"}],
            "agent_mode": "Quiz Agent",
            "learning_context": {"grade": 4, "subject": "Science"},
            "answer_language": "en",
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with patch("server.load_config", return_value={"TAVILY_API_KEY": "test-key"}), patch(
            "server.generate_answer", return_value={"answer": "Quiz result", "images": []}
        ) as provider:
            with urlopen(request, timeout=3) as response:
                result = json.loads(response.read().decode("utf-8"))
        self.assertEqual(result["answer"], "Quiz result")
        self.assertIn("Quiz Agent", provider.call_args.args[1][0]["text"])

    def test_general_study_plan_uses_groq_path_without_tavily_answer(self):
        prompt = "Create a beginner 7-day machine-learning study plan with one hour per day"
        plan = {"days": [
            {
                "day": day,
                "topic": f"Topic {day}",
                "learning_objective": f"Objective {day}",
                "practical_exercise": f"Exercise {day}",
                "time_allocation": [{"activity": "Study and practice", "minutes": 60}],
            }
            for day in range(1, 8)
        ]}
        payload = {
            "provider": "tavily",
            "messages": [{"role": "user", "text": prompt}],
            "planning_details": {"minutes_per_day": 60},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with patch("server.load_config", return_value={"GROQ_API_KEY": "test-only"}), patch(
            "server.generate_plan_answer", return_value=json.dumps(plan)
        ) as groq, patch("server.generate_answer", side_effect=AssertionError("Tavily must not generate ordinary plans")):
            with urlopen(request, timeout=3) as response:
                result = json.loads(response.read().decode("utf-8"))
        self.assertEqual(result["answer"].count("**Day "), 7)
        groq.assert_called_once()

    def test_rejects_text_attachment_over_character_limit(self):
        payload = {
            "provider": "tavily",
            "messages": [{"role": "user", "text": "Summarize this"}],
            "document": {"name": "notes.txt", "text": "x" * 8001},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=3)
        self.assertEqual(error.exception.code, 400)
        self.assertIn("8,000 characters", error.exception.read().decode("utf-8"))

    def test_rejects_malformed_json_study_attachment(self):
        payload = {
            "provider": "tavily",
            "messages": [{"role": "user", "text": "Summarize this"}],
            "document": {"name": "notes.json", "text": "{ invalid"},
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=3)
        self.assertEqual(error.exception.code, 400)
        self.assertIn("JSON study file is malformed", error.exception.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
