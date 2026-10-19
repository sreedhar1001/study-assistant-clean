"""Streamlit integration test using a mocked provider (no Tavily request)."""

from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import server


class StreamlitAppTests(unittest.TestCase):
    def test_existing_chat_renders_and_uses_tutor_agent(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        with patch.object(
            server,
            "generate_answer",
            return_value={"answer": "Mocked tutor answer.", "images": []},
        ) as provider:
            app = AppTest.from_file(str(app_path)).run()
            self.assertEqual(len(app.exception), 0)
            app.chat_input[0].set_value("Explain gravity").run()

        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Mocked tutor answer." in item.value for item in app.markdown))
        provider.assert_called_once()
        self.assertEqual(app.session_state["sessions"][0]["messages"][-1]["agent"], "tutor")


if __name__ == "__main__":
    unittest.main()
