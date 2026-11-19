"""Offline checks for hosted transcription; no keys or model downloads required."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from core.transcriber import transcribe_all, transcribe_chunk, transcribe_chunk_groq


class HostedTranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.audio = Path(self.temp.name) / "audio.wav"
        self.audio.write_bytes(b"RIFF-test-audio")
        env = patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
        env.start()
        self.addCleanup(env.stop)

    @patch("core.transcriber.requests.post")
    def test_default_route_uses_api_even_with_stale_local_setting(self, post):
        response = post.return_value
        response.json.return_value = {"text": " Meeting transcript. "}
        with patch.dict(os.environ, {"TRANSCRIPTION_BACKEND": "local"}):
            self.assertEqual(transcribe_chunk(str(self.audio)), "Meeting transcript.")
        args, kwargs = post.call_args
        self.assertTrue(args[0].endswith("/audio/transcriptions"))
        self.assertEqual(kwargs["data"]["model"], "whisper-large-v3-turbo")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertTrue(kwargs["files"]["file"][1].closed)

    @patch("core.transcriber.requests.post")
    def test_missing_key_fails_before_network_call(self, post):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY"):
                transcribe_chunk_groq(str(self.audio))
        post.assert_not_called()

    @patch("core.transcriber.os.path.getsize", return_value=26 * 1024 * 1024)
    @patch("core.transcriber.requests.post")
    def test_oversized_chunk_fails_before_upload(self, post, size):
        with self.assertRaisesRegex(ValueError, "25 MB"):
            transcribe_chunk_groq(str(self.audio))
        post.assert_not_called()

    @patch("core.transcriber.requests.post")
    def test_api_error_propagates_and_closes_audio(self, post):
        post.return_value.raise_for_status.side_effect = requests.HTTPError("429 rate limited")
        with self.assertRaises(requests.HTTPError):
            transcribe_chunk_groq(str(self.audio))
        self.assertTrue(post.call_args.kwargs["files"]["file"][1].closed)

    @patch("core.transcriber.requests.post")
    def test_empty_transcript_is_reported(self, post):
        post.return_value.json.return_value = {"text": " "}
        with self.assertRaisesRegex(RuntimeError, "empty or invalid"):
            transcribe_chunk_groq(str(self.audio))

    @patch("core.transcriber.transcribe_chunk_sarvam", return_value="English translation")
    def test_hinglish_keeps_translation_api(self, sarvam):
        self.assertEqual(transcribe_chunk(str(self.audio), " Hinglish "), "English translation")

    @patch("core.transcriber.transcribe_chunk", side_effect=["First.", "Second."])
    def test_chunk_order_is_preserved(self, transcribe):
        self.assertEqual(transcribe_all(["one.wav", "two.wav"]), "First. Second.")

    def test_invalid_language_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Language"):
            transcribe_chunk(str(self.audio), "invalid")


class AppSmokeTests(unittest.TestCase):
    def test_health_and_frontend_without_local_models(self):
        import sys
        from fastapi.testclient import TestClient
        from backend import app
        with TestClient(app) as client:
            self.assertEqual(client.get("/health").json(), {"status": "ok"})
            self.assertEqual(client.get("/").status_code, 200)
        for module in ("whisper", "torch", "sentence_transformers", "core.vector_store"):
            self.assertNotIn(module, sys.modules)

    def test_default_retrieval_builds_without_embedding_model(self):
        from core.rag_engine import build_rag_chain
        from langchain_core.runnables import RunnableLambda
        with patch.dict(os.environ, {}, clear=True):
            with patch("core.rag_engine.get_llm", return_value=RunnableLambda(lambda _: "Answer")):
                chain = build_rag_chain("Alice will send the report on Monday.")
                self.assertEqual(chain.invoke("Who sends the report?"), "Answer")
