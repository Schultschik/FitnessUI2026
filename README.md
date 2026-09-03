# Fitness App for Raspberry Pi 5

Portrait, button-first fitness kiosk for a 2160×3840 display.

## Controls and wiring

Buttons use internal pull-ups: wire each momentary switch between the GPIO pin and any GND pin.

| Action | BCM GPIO | Physical header pin |
| --- | ---: | ---: |
| Up | 17 | 11 |
| Down | 27 | 13 |
| Select | 22 | 15 |

The Geekworm X1002 uses the Pi's PCIe FFC connection and does not reserve these GPIO inputs.

## Prepare the Pi

1. Use Raspberry Pi OS Desktop (Wayland), set HDMI output to portrait, and enable automatic login.
2. Format/mount the NVMe by UUID at `/mnt/fitness-media`; put MP4 files in `/mnt/fitness-media/videos`.
3. Copy this folder and your private Google `credentials.json` to the Pi. Share the Sheet with the service-account email from that JSON file.
4. Ensure Brave is already installed. Run `chmod +x install-pi.sh && ./install-pi.sh`.
5. Reboot. The app opens fullscreen; closing it from System returns to the desktop.

The installer grants the logged-in user passwordless permission for only `systemctl reboot` and `systemctl poweroff`; this makes the confirmed System menu actions work without a keyboard.

## Google Sheets

Only `Sheet1!A1:Z100` is read. Blank column headers are suppressed. The display refreshes every five seconds. Do not commit `credentials.json`.

## YouTube and ads

YouTube Music opens Brave in a dedicated persistent kiosk profile: `/home/pi/.config/fitness-brave`. Start Brave once with that profile and install/configure your preferred content blocker there. The app rotates a configured search term at each launch and adds a large button-friendly selection outline to YouTube results. If your Pi username is not `pi`, update `brave_profile` in `config.json`.

Ad blocking is not guaranteed because YouTube and browser extensions change; YouTube Premium is the reliable official ad-free option.

## Notes

- MP4 order is shuffled once for each app launch.
- Leaving a video returns directly to the video list with that item highlighted. Selecting that immediately previous unfinished video offers Resume or Restart; all other videos play normally. This temporary choice disappears after an app restart.
- Landscape video is letterboxed, never cropped.
