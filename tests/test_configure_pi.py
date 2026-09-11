import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('configure_pi', Path(__file__).parents[1] / 'configure-pi.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ConfigureTests(unittest.TestCase):
    def test_preserves_private_config_and_other_display_profiles_on_reinstall(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, home = root / 'app', root / 'home'
            app.mkdir()
            config = app / 'config.json'
            private = '{"video_directory": "/custom/videos", "youtube": {"brave_profile": "/custom/profile"}}\n'
            config.write_text(private)
            kanshi = home / '.config/kanshi/config'
            kanshi.parent.mkdir(parents=True)
            original = 'profile other {\n output HDMI-A-2 enable\n}\n'
            kanshi.write_text(original)
            module.configure(app, home, 'HDMI-A-1', '90')
            module.configure(app, home, 'HDMI-A-1', '270')
            self.assertEqual(config.read_text(), private)
            self.assertEqual(kanshi.with_suffix('.pre-fitness').read_text(), original)
            self.assertEqual(kanshi.read_text().count('profile fitness-portrait'), 1)
            self.assertIn(original, kanshi.read_text())
            self.assertIn('transform 270', kanshi.read_text())

    def test_new_config_uses_desktop_users_home(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, home = root / 'app', root / 'home'
            app.mkdir()
            (app / 'config.example.json').write_text('{"youtube": {"brave_profile": "/home/pi/old"}}')
            module.configure(app, home, 'HDMI-A-1', '90')
            settings = json.loads((app / 'config.json').read_text())
            self.assertEqual(settings['youtube']['brave_profile'], str(home / '.config/fitness-brave'))


if __name__ == '__main__':
    unittest.main()
