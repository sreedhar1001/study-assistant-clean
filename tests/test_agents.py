"""Offline unit tests for agent prompts, validation, and request routing."""

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from agents import quiz_agent, study_planner_agent, supervisor, tutor_agent
import server
from study_assistant.services import answers


class RecordingAnswer:
    def __init__(self):
        self.prompt = None

    def __call__(self, prompt: str) -> str:
        self.prompt = prompt
        return "provider response"


class TutorAgentTests(unittest.TestCase):
    def test_tutor_builds_explanation_prompt_and_uses_provider(self):
        answer = RecordingAnswer()
        result = tutor_agent.respond("Explain fractions", answer)
        self.assertEqual(result, "provider response")
        self.assertIn("step", answer.prompt.lower())
        self.assertIn("simple example", answer.prompt.lower())
        self.assertIn("Explain fractions", answer.prompt)


class QuizAgentTests(unittest.TestCase):
    def test_mixed_quiz_requests_both_formats_without_answer_key(self):
        answer = RecordingAnswer()
        quiz_agent.respond("Quiz me on photosynthesis", answer)
        self.assertIn("multiple-choice", answer.prompt)
        self.assertIn("short-answer", answer.prompt)
        self.assertIn("Do not show the answer key", answer.prompt)

    def test_rejects_unknown_quiz_format(self):
        with self.assertRaises(ValueError):
            quiz_agent.respond("Quiz me", RecordingAnswer(), question_type="Essay")

    def test_quiz_evaluates_a_response_using_recent_question_context(self):
        answer = RecordingAnswer()
        quiz_agent.respond(
            "B",
            answer,
            history=[{"role": "assistant", "text": "Question: Which option is correct? A, B, C, or D."}],
        )
        self.assertIn("evaluate that response", answer.prompt)
        self.assertIn("Question: Which option is correct?", answer.prompt)


class StudyPlannerAgentTests(unittest.TestCase):
    @staticmethod
    def make_plan(day_count=7, daily_minutes=60):
        return json.dumps({"days": [
            {
                "day": day,
                "topic": f"Topic {day}",
                "learning_objective": f"Understand concept {day}",
                "practical_exercise": f"Complete practice {day}",
                "time_allocation": [
                    {"activity": "Learn", "minutes": daily_minutes // 2},
                    {"activity": "Practice", "minutes": daily_minutes - daily_minutes // 2},
                ],
            }
            for day in range(1, day_count + 1)
        ]})

    def test_planner_uses_all_supplied_constraints(self):
        prompts = []
        result = study_planner_agent.respond(
            "Make my schedule",
            lambda prompt: (prompts.append(prompt) or self.make_plan(daily_minutes=45)),
            planning_details={
                "subjects": "Maths, Biology",
                "goal": "Review chapters 1-3",
                "minutes_per_day": 45,
                "deadline": "Friday",
            },
        )
        self.assertEqual(result.count("**Day "), 7)
        for detail in ("Maths, Biology", "Review chapters 1-3", "45 minutes", "Friday"):
            self.assertIn(detail, prompts[0])

    def test_generates_exactly_seven_days_with_required_fields_and_bounded_time(self):
        prompts = []
        result = study_planner_agent.respond(
            "Create a beginner 7-day machine-learning plan with one hour per day",
            lambda prompt: (prompts.append(prompt) or self.make_plan()),
            planning_details={"minutes_per_day": 60},
        )
        self.assertEqual(result.count("**Day "), 7)
        self.assertIn("420 minutes total", result)
        self.assertEqual(len(prompts), 1)
        self.assertIn("7 sequential days", prompts[0])
        self.assertLessEqual(len(prompts[0]), 900)
        for day in range(1, 8):
            self.assertIn(f"**Day {day}: Topic {day}**", result)
        self.assertEqual(result.count("Learning objective:"), 7)
        self.assertEqual(result.count("Practical exercise:"), 7)
        self.assertEqual(result.count("60/60 min"), 7)

    def test_typed_daily_time_overrides_the_sidebar_default(self):
        prompts = []
        result = study_planner_agent.respond(
            "Create a 7-day plan with one hour per day",
            lambda prompt: (prompts.append(prompt) or self.make_plan()),
            planning_details={"minutes_per_day": 30},
        )
        self.assertIn("available time=60 minutes per day", prompts[0])
        self.assertIn("60/60 min", result)

    def test_invalid_plan_is_repaired_once_then_returned(self):
        responses = iter(["not json", self.make_plan()])
        result = study_planner_agent.respond("Make a 7-day plan", lambda _prompt: next(responses))
        self.assertEqual(result.count("**Day "), 7)

    def test_provider_failure_is_reported_without_repeating_api_call(self):
        calls = []
        def unavailable(_prompt):
            calls.append(True)
            raise ValueError("Groq rate limit or account quota was reached.")
        with self.assertRaisesRegex(ValueError, "Groq rate limit"):
            study_planner_agent.respond("Make a 7-day plan", unavailable)
        self.assertEqual(len(calls), 1)

    def test_incomplete_or_over_limit_plan_is_rejected_after_retry(self):
        incomplete = json.dumps({"days": [{"day": 1}]})
        with self.assertRaisesRegex(ValueError, "complete, time-checked"):
            study_planner_agent.respond("Make a 7-day plan", lambda _prompt: incomplete)
        too_long = self.make_plan(daily_minutes=61)
        with self.assertRaisesRegex(ValueError, "complete, time-checked"):
            study_planner_agent.respond("Make a 7-day plan", lambda _prompt: too_long)

    def test_pdf_material_is_grounded_only_when_explicitly_requested(self):
        prompts = []
        result = study_planner_agent.respond(
            "Create a 7-day plan based on the attached PDF",
            lambda prompt: (prompts.append(prompt) or self.make_plan()),
            document={"name": "course.pdf", "text": "Lesson 1: supervised learning."},
        )
        self.assertEqual(result.count("**Day "), 7)
        self.assertIn("Lesson 1: supervised learning", prompts[0])
        self.assertTrue(study_planner_agent.requests_document("Make a plan from the attached PDF"))
        self.assertFalse(study_planner_agent.requests_document("Make me a beginner ML plan"))

    def test_explicit_pdf_request_requires_an_attached_document(self):
        with self.assertRaisesRegex(ValueError, "Attach the study PDF"):
            study_planner_agent.respond("Make a plan based on my PDF", lambda _: "")

    def test_planner_rejects_invalid_time(self):
        with self.assertRaises(ValueError):
            study_planner_agent.validate_planning_details({"minutes_per_day": 0})


class SupervisorTests(unittest.TestCase):
    def test_automatic_routes_quiz_planner_and_tutor_requests(self):
        self.assertEqual(supervisor.route_request("Give me a quiz on cells"), "quiz")
        self.assertEqual(supervisor.route_request("Make a study plan for exams"), "planner")
        self.assertEqual(supervisor.route_request("Create a schedule for my exams"), "planner")
        self.assertEqual(supervisor.route_request("Explain how cells work"), "tutor")

    def test_short_answer_after_quiz_stays_with_quiz_agent(self):
        history = [{"role": "assistant", "agent": "quiz", "text": "Question: 2+2?"}]
        self.assertEqual(supervisor.route_request("4", history=history), "quiz")

    def test_explicit_new_question_after_quiz_routes_to_tutor(self):
        history = [{"role": "assistant", "agent": "quiz", "text": "Question: 2+2?"}]
        self.assertEqual(supervisor.route_request("What is ATP?", history=history), "tutor")

    def test_manual_agent_choice_overrides_automatic_routing(self):
        self.assertEqual(supervisor.route_request("quiz me", mode="Tutor Agent"), "tutor")

    def test_dispatch_returns_agent_and_response(self):
        result = supervisor.dispatch("Explain gravity", RecordingAnswer())
        self.assertEqual(result["agent"], "tutor")
        self.assertEqual(result["text"], "provider response")

    def test_dispatch_uses_planner_specific_answer_callback(self):
        def plan(_prompt):
            return StudyPlannerAgentTests.make_plan()
        result = supervisor.dispatch(
            "Create a 7-day study plan",
            RecordingAnswer(),
            planner_answer=plan,
        )
        self.assertEqual(result["agent"], "planner")
        self.assertEqual(result["text"].count("**Day "), 7)


class ExistingAssistantRegressionTests(unittest.TestCase):
    def test_primary_arithmetic_is_answered_without_search(self):
        answer = RecordingAnswer()
        result = supervisor.dispatch("What is 1 + 1?", answer)
        self.assertIn("answer is 2", result["text"])
        self.assertIsNone(answer.prompt)

    def test_higher_education_question_uses_selected_context_and_language(self):
        with patch("server.tavily_search", return_value={"answer": "A mocked explanation.", "results": []}) as search:
            result = server.generate_answer(
                "tavily",
                [{"role": "user", "text": "Explain eigenvalues"}],
                {"TAVILY_API_KEY": "test-key"},
                education_context={"stage": "Undergraduate", "subject": "Mathematics"},
                answer_language="hi",
            )
        self.assertEqual(result["answer"], "A mocked explanation.")
        self.assertIn("Undergraduate studying Mathematics", search.call_args.args[1])
        self.assertIn("Respond in Hindi", search.call_args.args[1])

    def test_discovery_discards_unrelated_results_and_preserves_source_metadata(self):
        with patch("server.tavily_search", return_value={
            "results": [
                {"title": "Quantum computing advances", "url": "https://example.org/quantum", "content": "New quantum computing research", "published_date": datetime.now(timezone.utc).date().isoformat()},
                {"title": "Garden planning", "url": "https://example.org/garden", "content": "How to grow tomatoes", "published_date": datetime.now(timezone.utc).date().isoformat()},
            ],
            "images": [],
        }):
            result = server.search_discovery_section("advanced_technology", "quantum computing", {})
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["title"], "Quantum computing advances")
        self.assertEqual(result["results"][0]["url"], "https://example.org/quantum")

    def test_existing_tavily_answer_flow_still_returns_answer(self):
        with patch("server.tavily_search", return_value={"answer": "A supported answer.", "results": []}):
            result = server.generate_answer(
                "tavily",
                [{"role": "user", "text": "Explain gravity"}],
                {"TAVILY_API_KEY": "test-key"},
            )
        self.assertEqual(result["answer"], "A supported answer.")

    def test_tavily_prompt_includes_grounding_and_pdf_source_labels(self):
        document = {
            "name": "Biology.pdf",
            "text": "[Biology.pdf, page 5] Plants use sunlight to make food.",
        }
        with patch("server.tavily_search", return_value={"answer": "Plants use sunlight.", "results": []}) as search:
            server.generate_answer(
                "tavily",
                [{"role": "user", "text": "How do plants make food?"}],
                {"TAVILY_API_KEY": "test-key"},
                document=document,
                document_source_only=True,
            )
        query = search.call_args.args[1]
        self.assertIn("use only the supplied retrieved passages", query)
        self.assertIn("[Biology.pdf, page 5]", query)


if __name__ == "__main__":
    unittest.main()
