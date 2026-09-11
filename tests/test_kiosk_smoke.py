"""Run on the Pi with QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

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


if __name__ == '__main__':
    unittest.main()
