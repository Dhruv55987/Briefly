"""YouTube access errors should give users an actionable upload fallback."""
import unittest
from unittest.mock import patch

import yt_dlp
from utils.audio_processor import download_youtube_audio


class YouTubeDownloadTests(unittest.TestCase):
    @patch("utils.audio_processor.yt_dlp.YoutubeDL")
    def test_bot_challenge_has_upload_fallback(self, downloader):
        downloader.return_value.__enter__.return_value.extract_info.side_effect = (
            yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot")
        )
        with self.assertRaisesRegex(ValueError, "Choose Upload file"):
            download_youtube_audio("https://www.youtube.com/watch?v=example")

    @patch("utils.audio_processor.yt_dlp.YoutubeDL")
    def test_unrelated_download_errors_are_preserved(self, downloader):
        error = yt_dlp.utils.DownloadError("Video unavailable")
        downloader.return_value.__enter__.return_value.extract_info.side_effect = error
        with self.assertRaises(yt_dlp.utils.DownloadError) as caught:
            download_youtube_audio("https://www.youtube.com/watch?v=example")
        self.assertIs(caught.exception, error)
