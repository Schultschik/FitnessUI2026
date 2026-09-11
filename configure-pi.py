"""Preserve private app settings and add a managed portrait output profile."""
import json
import shutil
import sys
from pathlib import Path


def configure(app_dir, home, output, rotation):
    config = app_dir / 'config.json'
    if not config.exists():
        settings = json.loads((app_dir / 'config.example.json').read_text())
        settings['youtube']['brave_profile'] = str(home / '.config/fitness-brave')
        config.write_text(json.dumps(settings, indent=2) + '\n')
        config.chmod(0o600)
    kanshi = home / '.config/kanshi/config'
    kanshi.parent.mkdir(parents=True, exist_ok=True)
    existing = kanshi.read_text() if kanshi.exists() else ''
    begin, end = '# BEGIN FITNESS DISPLAY', '# END FITNESS DISPLAY'
    if existing and not kanshi.with_suffix('.pre-fitness').exists():
        shutil.copy2(kanshi, kanshi.with_suffix('.pre-fitness'))
    if begin in existing:
        before, managed = existing.split(begin, 1)
        _, after = managed.split(end, 1)
        existing = before + after.lstrip('\n')
    profile = f'{begin}\nprofile fitness-portrait {{\n    output {output} enable transform {rotation} scale 1\n}}\n{end}\n'
    kanshi.write_text(profile + existing)


if __name__ == '__main__':
    app_dir, home, output, rotation = sys.argv[1:]
    configure(Path(app_dir), Path(home), output, rotation)
