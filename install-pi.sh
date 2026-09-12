#!/usr/bin/env bash
set -euo pipefail

# Usage: sudo bash install-pi.sh stefan HDMI-A-1 90
cd "$(dirname "$(readlink -f "$0")")"
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
if (( EUID != 0 )); then exec sudo bash "$0" "${1:-$USER}" "${2:-HDMI-A-1}" "${3:-90}"; fi
USER_NAME="${1:-${SUDO_USER:-}}"
OUTPUT="${2:-HDMI-A-1}"
ROTATION="${3:-90}"
if [[ ! "$USER_NAME" =~ ^[a-z_][a-z0-9_-]*$ ]] || [[ "$USER_NAME" == root ]]; then
    echo 'Specify the desktop user, not root.' >&2; exit 1
fi
id "$USER_NAME" >/dev/null
[[ "$OUTPUT" =~ ^[A-Za-z0-9-]+$ ]] || exit 1
[[ "$ROTATION" == 90 || "$ROTATION" == 270 ]] || exit 1
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6)
USER_GROUP=$(id -gn "$USER_NAME")
APP_DIR=/opt/fitness-app
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 update
apt-get -o Acquire::Retries=3 install -y python3-venv python3-pyqt5 qtwayland5 \
    python3-gpiozero python3-lgpio python3-googleapi python3-google-auth \
    python3-websocket mpv curl ca-certificates kanshi wlr-randr
if ! command -v brave-browser >/dev/null; then
    curl --retry 3 -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg \
        https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg
    curl --retry 3 -fsSLo /etc/apt/sources.list.d/brave-browser-release.sources \
        https://brave-browser-apt-release.s3.brave.com/brave-browser.sources
    apt-get -o Acquire::Retries=3 update
    apt-get -o Acquire::Retries=3 install -y brave-browser
fi
install -d -o "$USER_NAME" -g "$USER_GROUP" "$APP_DIR"
install -o "$USER_NAME" -g "$USER_GROUP" -m 644 fitness_app.py youtube_navigation.js config.example.json requirements.txt "$APP_DIR/"
install -Dm644 brave-kiosk-policy.json /etc/brave/policies/managed/fitness-kiosk.json
install -o "$USER_NAME" -g "$USER_GROUP" -m 755 launch-pi.sh "$APP_DIR/"
if [[ -f credentials.json ]]; then
    install -o "$USER_NAME" -g "$USER_GROUP" -m 600 credentials.json "$APP_DIR/credentials.json"
fi
runuser -u "$USER_NAME" -- python3 configure-pi.py "$APP_DIR" "$USER_HOME" "$OUTPUT" "$ROTATION"
# Use OS-provided ARM64 Qt/GPIO modules; avoid replacing them with pip wheels.
runuser -u "$USER_NAME" -- python3 -m venv --system-site-packages "$APP_DIR/.venv"
runuser -u "$USER_NAME" -- "$APP_DIR/.venv/bin/python" -c 'import PyQt5.QtWidgets, gpiozero, lgpio, googleapiclient.discovery, google.auth, websocket'
install -d -o "$USER_NAME" -g "$USER_GROUP" /mnt/fitness-media /mnt/fitness-media/videos
install -d -o "$USER_NAME" -g "$USER_GROUP" "$USER_HOME/.config/autostart"
install -o "$USER_NAME" -g "$USER_GROUP" -m 644 autostart/fitness-app.desktop "$USER_HOME/.config/autostart/fitness-app.desktop"
# Remove the previous installer entry to avoid launching twice.
if [[ -f /etc/xdg/autostart/fitness-app.desktop ]] && grep -q '/opt/fitness-app/' /etc/xdg/autostart/fitness-app.desktop; then
    rm /etc/xdg/autostart/fitness-app.desktop
fi
sudoers=$(mktemp)
trap 'rm -f "$sudoers"' EXIT
printf '%s ALL=(root) NOPASSWD: /usr/bin/systemctl reboot, /usr/bin/systemctl poweroff\n' "$USER_NAME" > "$sudoers"
visudo -cf "$sudoers"
install -m 440 "$sudoers" /etc/sudoers.d/fitness-app
echo 'Installed. Enable desktop automatic login, then reboot. No disks were formatted.'
