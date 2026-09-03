#!/usr/bin/env bash
set -euo pipefail

# Run once on the Pi from this project directory after copying credentials.json.
APP_DIR=/opt/fitness-app
USER_NAME="${SUDO_USER:-$USER}"
sudo mkdir -p "$APP_DIR"
sudo cp fitness_app.py config.example.json requirements.txt "$APP_DIR/"
if [ -f credentials.json ]; then sudo cp credentials.json "$APP_DIR/credentials.json"; fi
if [ ! -f "$APP_DIR/config.json" ]; then sudo cp "$APP_DIR/config.example.json" "$APP_DIR/config.json"; fi
sudo sed -i "s|/home/pi/|/home/$USER_NAME/|g" "$APP_DIR/config.json"
sudo chown -R "$USER_NAME:$USER_NAME" "$APP_DIR"
sudo apt update
sudo apt install -y python3-venv python3-pyqt5 python3-lgpio mpv
python3 -m venv --system-site-packages "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
sudo install -Dm644 autostart/fitness-app.desktop /etc/xdg/autostart/fitness-app.desktop
printf '%s ALL=(root) NOPASSWD: /usr/bin/systemctl reboot, /usr/bin/systemctl poweroff\n' "$USER_NAME" | sudo tee /etc/sudoers.d/fitness-app >/dev/null
sudo chmod 440 /etc/sudoers.d/fitness-app
echo "Installed. Configure the NVMe mount and edit $APP_DIR/config.json before rebooting."
