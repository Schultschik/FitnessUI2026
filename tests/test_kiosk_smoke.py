"""Run on the Pi with QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

from PyQt5.QtWidgets import QApplication

import fitness_app


class KioskSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.gpio = patch.object(fitness_app, 'GPIOButtons')
        self.gpio.start()
        self.window = fitness_app.Kiosk()
        self.window.resize(1080, 1920)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.gpio.stop()

    def test_navigation_and_portrait_layout(self):
        self.assertEqual(self.window.current_view, 'home')
        self.assertEqual(len(self.window.items), 5)
        for card in self.window.home_cards:
            self.assertTrue(self.window.home.rect().contains(card.geometry()))
        self.window.on_select()
        self.assertEqual(self.window.current_view, 'videos')
        self.window.index = len(self.window.video_cards)
        self.window.on_select()
        self.assertEqual(self.window.current_view, 'home')
        for _ in range(3):
            self.window.on_down()
        self.window.on_select()
        self.assertEqual(self.window.current_view, 'pace')
        self.window.on_select()
        self.assertEqual(self.window.current_view, 'home')
        self.window.on_up()
        self.window.on_select()
        self.assertEqual(self.window.current_view, 'system')

    def test_missing_sheets_credentials_keeps_app_open(self):
        self.window.cfg['sheets']['credentials_file'] = '/nonexistent/fitness-test-credentials.json'
        self.window.strength_view()
        self.app.processEvents()
        self.assertEqual(self.window.current_view, 'strength')
        self.assertIn('Could not update', self.window.strength_content.itemAt(0).widget().text())
        self.window.on_select()
        self.assertEqual(self.window.current_view, 'home')

    def test_shared_uploads_appear_when_reopening_videos(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, uploaded = root / 'first.mp4', root / 'uploaded.MP4'
            first.touch()
            self.window.cfg['video_directory'] = directory
            self.window.video_view()
            self.assertEqual(self.window.videos, [first])
            uploaded.touch()
            self.window.home_view()
            self.window.video_view()
            self.assertEqual(self.window.videos, [first, uploaded])
            first.unlink()
            self.window.video_view()
            self.assertEqual(self.window.videos, [uploaded])

    def test_youtube_home_stops_browser_and_restores_kiosk(self):
        process = Mock(pid=987654)
        self.window.brave = process
        self.window.browser_mode = True
        self.window.youtube_timer.start(750)
        with patch.object(fitness_app.os, 'killpg') as kill:
            self.window.close_youtube()
        kill.assert_called_once_with(987654, fitness_app.signal.SIGTERM)
        self.assertFalse(self.window.youtube_timer.isActive())
        self.assertFalse(self.window.browser_mode)
        self.assertIsNone(self.window.brave)
        self.assertEqual(self.window.current_view, 'home')
        self.assertTrue(self.window.isVisible())

    def test_youtube_browser_exit_restores_kiosk(self):
        self.window.browser_mode = True
        self.window.brave = Mock()
        self.window.brave.poll.return_value = 0
        with patch.object(self.window, 'close_youtube') as close:
            self.window.install_youtube_navigation()
        close.assert_called_once()

    def test_youtube_home_request_is_handled(self):
        self.window.browser_mode = True
        self.window.brave = Mock()
        self.window.brave.poll.return_value = None
        with patch.object(self.window, 'browser_eval', return_value={'homeRequested': True}), patch.object(self.window, 'close_youtube') as close:
            self.window.install_youtube_navigation()
        close.assert_called_once()
        self.window.brave = None

    def test_missing_browser_keeps_home_visible(self):
        with patch.object(fitness_app.subprocess, 'Popen', side_effect=FileNotFoundError):
            self.window.youtube_view()
        self.assertFalse(self.window.browser_mode)
        self.assertTrue(self.window.isVisible())


if __name__ == '__main__':
    unittest.main()
