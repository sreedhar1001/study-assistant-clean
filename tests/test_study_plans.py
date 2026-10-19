"""Offline tests for the planner's Groq generation and optional Tavily research."""

import unittest
from urllib.error import HTTPError
from io import BytesIO
from unittest.mock import Mock
from unittest.mock import patch

from study_assistant.services.study_plans import generate_plan_answer, needs_current_research
from study_assistant.providers.groq import chat_completion


class StudyPlanProviderTests(unittest.TestCase):
    def test_general_study_plan_uses_groq_without_tavily(self):
        complete = Mock(return_value="plan")
        search = Mock(side_effect=AssertionError("ordinary study plans should not search"))
        result = generate_plan_answer(
            "plan prompt",
            "Create a 7-day beginner machine-learning plan",
            {"GROQ_API_KEY": "test-only"},
            search=search,
            complete=complete,
        )
        self.assertEqual(result, "plan")
        complete.assert_called_once()
        search.assert_not_called()

    def test_current_research_request_adds_tavily_results_for_groq_synthesis(self):
        complete = Mock(return_value="plan")
        search = Mock(return_value={"results": [
            {"title": "Current ML course", "content": "A current learning outline."},
        ]})
        result = generate_plan_answer(
            "plan prompt",
            "Make a plan based on the latest machine-learning research",
            {"GROQ_API_KEY": "test-only", "TAVILY_API_KEY": "test-only"},
            search=search,
            complete=complete,
        )
        self.assertEqual(result, "plan")
        search.assert_called_once()
        self.assertIn("Current ML course", complete.call_args.args[1])

    def test_empty_current_search_results_still_produce_general_plan(self):
        complete = Mock(return_value="general plan")
        result = generate_plan_answer(
            "plan prompt",
            "Make a plan using the latest AI news",
            {"GROQ_API_KEY": "test-only"},
            search=Mock(return_value={"results": []}),
            complete=complete,
        )
        self.assertEqual(result, "general plan")
        self.assertIn("no useful current sources", complete.call_args.args[1])

    def test_tavily_failure_is_graceful_and_groq_still_generates(self):
        complete = Mock(return_value="general plan")
        result = generate_plan_answer(
            "plan prompt",
            "Make a plan using current research",
            {"GROQ_API_KEY": "test-only"},
            search=Mock(side_effect=ValueError("offline")),
            complete=complete,
        )
        self.assertEqual(result, "general plan")
        self.assertIn("research was unavailable", complete.call_args.args[1])

    def test_tavily_search_errors_do_not_prevent_plan_generation(self):
        complete = Mock(return_value="general plan")
        result = generate_plan_answer(
            "plan prompt",
            "Make a plan using recent research",
            {"GROQ_API_KEY": "test-only"},
            search=Mock(side_effect=RuntimeError("transport failed")),
            complete=complete,
        )
        self.assertEqual(result, "general plan")
        self.assertIn("research was unavailable", complete.call_args.args[1])

    def test_pdf_grounding_uses_groq_without_tavily_when_request_is_not_current(self):
        complete = Mock(return_value="grounded plan")
        search = Mock(side_effect=AssertionError("PDF planning should not search by default"))
        result = generate_plan_answer(
            "plan prompt",
            "Create a plan based on my PDF",
            {"GROQ_API_KEY": "test-only"},
            has_document=True,
            search=search,
            complete=complete,
        )
        self.assertEqual(result, "grounded plan")
        self.assertIn("learner's document as the primary reference", complete.call_args.args[1])
        search.assert_not_called()

    def test_empty_groq_api_key_returns_safe_message(self):
        with self.assertRaisesRegex(ValueError, "Add GROQ_API_KEY"):
            chat_completion({}, "a private prompt")

    def test_groq_rate_limit_is_reported_without_exposing_provider_response(self):
        error = HTTPError("https://api.groq.com", 429, "rate limited", {}, BytesIO(b"private response"))
        with patch("study_assistant.providers.groq.urlopen", side_effect=error):
            with self.assertRaisesRegex(ValueError, "Groq rate limit") as raised:
                chat_completion({"GROQ_API_KEY": "test-only"}, "private prompt")
        self.assertNotIn("private response", str(raised.exception))

    def test_malformed_groq_json_has_a_safe_error(self):
        class MockResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b"not-json"

        with patch("study_assistant.providers.groq.urlopen", return_value=MockResponse()):
            with self.assertRaisesRegex(ValueError, "unreadable response"):
                chat_completion({"GROQ_API_KEY": "test-only"}, "private prompt")

    def test_current_info_detection_does_not_search_for_general_plan(self):
        self.assertFalse(needs_current_research("Create a 7-day beginner study plan"))
        self.assertTrue(needs_current_research("Create a plan using the latest research"))


if __name__ == "__main__":
    unittest.main()
