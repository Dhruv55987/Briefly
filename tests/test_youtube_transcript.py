import os
import unittest
from types import SimpleNamespace
from unittest.mock import DEFAULT, Mock, patch

from youtube_transcript_api import IpBlocked, RequestBlocked, NoTranscriptFound, TranscriptsDisabled
from core.youtube_transcript import extract_video_id, fetch_youtube_transcript, is_youtube_url

VIDEO_ID = "HbY8eY8Wj8w"
URL = "https://www.youtube.com/watch?v=" + VIDEO_ID


class YouTubeCaptionTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"MAX_MEDIA_SECONDS": "300"})
        env.start()
        self.addCleanup(env.stop)
        client = patch("core.youtube_transcript.YouTubeTranscriptApi")
        self.api = client.start().return_value
        self.addCleanup(client.stop)
        self.tracks = self.api.list.return_value
        self.track = self.tracks.find_transcript.return_value
        self.track.language_code = "en"
        self.track.fetch.return_value = [SimpleNamespace(
            text="Alice sends the report.", start=0, duration=2
        )]

    def test_url_variants_extract_video_id(self):
        for url in (URL, "https://youtu.be/"+VIDEO_ID+"?t=10",
                    "https://youtube.com/shorts/"+VIDEO_ID,
                    "https://www.youtube.com/embed/"+VIDEO_ID,
                    "https://m.youtube.com/live/"+VIDEO_ID):
            with self.subTest(url=url):
                self.assertEqual(extract_video_id(url), VIDEO_ID)

    def test_invalid_urls_are_rejected_before_network(self):
        for url in ("https://youtube.com.attacker.test/watch?v="+VIDEO_ID,
                    "file://youtube.com/watch?v="+VIDEO_ID,
                    "https://youtube.com/@channel", "https://youtu.be/invalid"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    fetch_youtube_transcript(url)
        self.api.list.assert_not_called()

    def test_existing_captions_need_no_provider_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(fetch_youtube_transcript(URL), "Alice sends the report.")
        self.api.list.assert_called_once_with(VIDEO_ID)
        self.track.translate.assert_not_called()

    def test_non_english_captions_translate_when_supported(self):
        self.track.language_code = "hi"
        self.track.is_translatable = True
        self.track.translate.return_value.fetch.return_value = [SimpleNamespace(
            text="Translated caption", start=0, duration=2
        )]
        self.assertEqual(fetch_youtube_transcript(URL), "Translated caption")
        self.track.translate.assert_called_once_with("en")

    def test_falls_back_to_another_available_language(self):
        self.tracks.find_transcript.side_effect = NoTranscriptFound(VIDEO_ID, ["en"], [])
        self.api.list.return_value = Mock(find_transcript=self.tracks.find_transcript)
        self.api.list.return_value.__iter__ = Mock(return_value=iter([self.track]))
        self.assertEqual(fetch_youtube_transcript(URL), "Alice sends the report.")

    def test_cloud_ip_blocks_are_reported(self):
        for error in (RequestBlocked(VIDEO_ID), IpBlocked(VIDEO_ID)):
            with self.subTest(error=type(error).__name__):
                self.api.list.side_effect = error
                with self.assertRaisesRegex(RuntimeError, "server's IP address"):
                    fetch_youtube_transcript(URL)

    def test_disabled_captions_are_reported(self):
        self.api.list.side_effect = TranscriptsDisabled(VIDEO_ID)
        with self.assertRaisesRegex(RuntimeError, "No accessible captions"):
            fetch_youtube_transcript(URL)

    def test_long_videos_use_text_size_limit_instead_of_audio_duration(self):
        self.track.fetch.return_value = [SimpleNamespace(text="Long video captions", start=600, duration=2)]
        self.assertEqual(fetch_youtube_transcript(URL), "Long video captions")
        self.track.fetch.return_value = [SimpleNamespace(text="x"*50001, start=0, duration=2)]
        with self.assertRaisesRegex(ValueError, "too long"):
            fetch_youtube_transcript(URL)

    def test_empty_captions_fail(self):
        self.track.fetch.return_value = []
        with self.assertRaisesRegex(RuntimeError, "No existing captions"):
            fetch_youtube_transcript(URL)

    def test_pipeline_uses_captions_for_youtube_and_whisper_for_files(self):
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
                mocks["process_input"].return_value = ["audio.wav"]
                mocks["transcribe_all"].return_value = "Uploaded speech"
                result = run_pipeline("upload.mp3")
                self.assertEqual(result["transcript"], "Uploaded speech")
                mocks["transcribe_all"].assert_called_once_with(["audio.wav"], "english")
                mocks["fetch_youtube_transcript"].assert_called_once_with(URL)
