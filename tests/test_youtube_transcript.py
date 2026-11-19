import os
import unittest
from unittest.mock import DEFAULT, Mock, patch

from core.youtube_transcript import fetch_youtube_transcript, is_youtube_url

URL = "https://www.youtube.com/watch?v=example"


class YouTubeCaptionTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"SUPADATA_API_KEY": "test-key", "MAX_MEDIA_SECONDS": "300"})
        env.start()
        self.addCleanup(env.stop)

    def test_host_validation(self):
        self.assertTrue(is_youtube_url(URL))
        self.assertTrue(is_youtube_url("https://youtu.be/example"))
        self.assertFalse(is_youtube_url("https://youtube.com.attacker.test/example"))
        self.assertFalse(is_youtube_url("file://youtube.com/example"))

    @patch("core.youtube_transcript.requests.get")
    def test_native_caption_request_does_not_generate_audio(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"content": [
            {"text": "Alice sends the report.", "offset": 0, "duration": 2000}
        ]}
        self.assertEqual(fetch_youtube_transcript(URL), "Alice sends the report.")
        self.assertEqual(get.call_args.kwargs["params"]["mode"], "native")
        self.assertEqual(get.call_args.kwargs["headers"]["x-api-key"], "test-key")

    @patch("core.youtube_transcript.requests.get")
    def test_missing_key_makes_no_request(self, get):
        with patch.dict(os.environ, {"SUPADATA_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "SUPADATA_API_KEY"):
                fetch_youtube_transcript(URL)
        get.assert_not_called()

    @patch("core.youtube_transcript.requests.get")
    def test_provider_errors_are_actionable(self, get):
        for status, expected in ((401, "API key"), (429, "quota"), (404, "captions")):
            with self.subTest(status=status):
                get.return_value = Mock(status_code=status)
                with self.assertRaisesRegex(RuntimeError, expected):
                    fetch_youtube_transcript(URL)

    @patch("core.youtube_transcript.requests.get")
    def test_caption_duration_limit(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"content": [
            {"text": "Too long", "offset": 300000, "duration": 2000}
        ]}
        with self.assertRaisesRegex(ValueError, "300 seconds"):
            fetch_youtube_transcript(URL)

    @patch("core.youtube_transcript.requests.get")
    def test_empty_captions_fail(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"content": []}
        with self.assertRaisesRegex(RuntimeError, "No existing captions"):
            fetch_youtube_transcript(URL)

    @patch("core.youtube_transcript.time.sleep")
    @patch("core.youtube_transcript.requests.get")
    def test_async_job_is_polled(self, get, sleep):
        pending = Mock(status_code=202)
        pending.json.return_value = {"jobId": "test-job"}
        completed = Mock(status_code=200)
        completed.json.return_value = {"status": "completed", "content": [
            {"text": "Ready", "offset": 0, "duration": 1000}
        ]}
        get.side_effect = [pending, completed]
        self.assertEqual(fetch_youtube_transcript(URL), "Ready")
        self.assertTrue(get.call_args.args[0].endswith("/test-job"))

    def test_pipeline_skips_audio_for_configured_youtube_links(self):
        from main import run_pipeline
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
            with patch.multiple("main", process_input=DEFAULT, transcribe_all=DEFAULT,
                                fetch_youtube_transcript=DEFAULT, generate_title=DEFAULT,
                                summarize=DEFAULT, extract_action_items=DEFAULT,
                                extract_key_decisions=DEFAULT, extract_questions=DEFAULT,
                                build_rag_chain=DEFAULT) as mocks:
                mocks["fetch_youtube_transcript"].return_value = "Alice sends the report."
                result = run_pipeline(URL)
                self.assertEqual(result["transcript"], "Alice sends the report.")
                mocks["process_input"].assert_not_called()
                mocks["transcribe_all"].assert_not_called()
                mocks["summarize"].assert_called_once_with("Alice sends the report.")
