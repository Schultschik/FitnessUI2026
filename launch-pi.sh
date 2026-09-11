#!/usr/bin/env bash
set -euo pipefail
cd /opt/fitness-app
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/fitness-app-$(id -u).lock"
flock -n 9 || exit 0
if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=wayland
fi
exec .venv/bin/python fitness_app.py
