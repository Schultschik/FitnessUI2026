# Fitness App for Raspberry Pi 5

Portrait, button-first fitness kiosk for Raspberry Pi OS Desktop. Tested on a Pi 5 with a 1920x1080 HDMI monitor rotated 90 degrees (1080x1920 desktop).

## Controls and wiring

Buttons use internal pull-ups: wire each momentary switch between the GPIO pin and any GND pin.

| Action | BCM GPIO | Physical header pin |
| --- | ---: | ---: |
| Up | 17 | 11 |
| Down | 27 | 13 |
| Select | 22 | 15 |

The Geekworm X1002 uses the Pi's PCIe FFC connection and does not reserve these GPIO inputs.

## Prepare the Pi

1. Use Raspberry Pi OS Desktop with labwc/Wayland and enable desktop automatic login using `sudo raspi-config`.
2. Obtain this repository on the Pi. From the project folder, run `sudo bash install-pi.sh stefan HDMI-A-1 90`, substituting your desktop username, output name from `wlr-randr`, and rotation (`90` or `270`).
3. The installer adds Qt/Wayland, GPIO, Google API, mpv, and Brave dependencies. It installs the app at `/opt/fitness-app`, preserves existing `config.json`, and configures portrait orientation through kanshi. Rerun the installer after updating the checkout.
4. Put MP4 files in `/mnt/fitness-media/videos`. This is an ordinary folder on the existing filesystem: **do not format the NVMe when it is your OS boot disk**. For a separate media disk, configure its mount independently.
5. Copy your private Google `credentials.json` into the project before installation, or place it at `/opt/fitness-app/credentials.json` owned by your desktop user with mode `600`. Share the Sheet with the service-account email. The home screen and offline features work without this file.
6. Reboot. The app opens fullscreen from the user's XDG autostart entry, including on labwc. Closing it from System returns to the desktop. A launch lock prevents duplicate instances.

The installer never repartitions storage and does not change bootloader or PCIe settings. Existing kanshi configuration is backed up as `~/.config/kanshi/config.pre-fitness` before the first modification. The managed portrait profile is placed first; other profiles are retained.

Python dependencies on the Pi come from APT and are exposed through a virtual environment with `--system-site-packages`. `requirements.txt` remains available for development on other systems; the Pi installer does not replace distribution Qt/GPIO modules with pip wheels.

The installer grants the logged-in user passwordless permission for only `systemctl reboot` and `systemctl poweroff`; this makes the confirmed System menu actions work without a keyboard.

## Google Sheets

Only `Sheet1!A1:Z100` is read. Blank column headers are suppressed. The display refreshes every five seconds. Do not commit `credentials.json`.

## YouTube and ads

YouTube Music opens Brave in a dedicated persistent kiosk profile under the installing user's `~/.config/fitness-brave`. The installer sets this path when creating a new configuration. Existing private configurations are preserved; check `youtube.brave_profile` if migrating from another username. The app rotates a configured search term at each launch and adds a large button-friendly selection outline to YouTube results. Brave is installed from its [official signed APT repository](https://brave.com/linux/).

## Diagnostics

- App log: `/opt/fitness-app/fitness-app.log`.
- Launch manually from a desktop terminal: `/opt/fitness-app/launch-pi.sh`.
- Display orientation: `wlr-randr` in the desktop session; the output should show `Transform: 90`.
- Source checkout and installed files are separate. Run the installer to deploy source updates.
- Never commit `credentials.json`, `config.json`, private keys, or playback state.

## Windows Video Share

Run `sudo bash setup-video-share.sh stefan`, then `sudo smbpasswd -a stefan` to set the SMB password. The authenticated, writable share is `\\fitnessui\Videos`, backed by `/mnt/fitness-media/videos` on the existing filesystem. Sign in from Windows as `stefan` with that SMB password. The share starts at boot and does not allow guest access.

Copy MP4 files into the share, wait for the copy to finish, then reopen Fitness Videos. New files are added without restarting the app; removed files disappear and the order of remaining videos is preserved. `.mp4` and `.MP4` extensions are accepted.

## Current Pi Deployment

### Remote Desktop

WayVNC is enabled for the labwc desktop with `sudo raspi-config nonint do_vnc 0`. It starts at boot on TCP port 5900, with authentication enabled through PAM. Connect a WayVNC-compatible viewer to `fitnessui:5900` (currently `192.168.1.201:5900`) using the Pi account `stefan` and its password. Check `systemctl status wayvnc` if the desktop is unavailable. No router port forwarding is configured.

The installation at `/opt/fitness-app` runs as `stefan` on Raspberry Pi OS Trixie/labwc. The source checkout is `/home/stefan/FitnessUI2026`. HDMI-A-1 is rotated 90 degrees, giving a 1080x1920 desktop. Desktop automatic login launches the user's XDG autostart entry.

The Pi boots from the TEAM 512 GB NVMe on an X1002 shield. Existing settings are `dtparam=pciex1`, `dtparam=pciex1_gen=2`, EEPROM `BOOT_ORDER=0xf416` and `PCIE_PROBE=1`. The prior NVMe stability workaround is `nvme_core.default_ps_max_latency_us=0 pcie_aspm=off pcie_port_pm=off` on the single kernel command line. Wi-Fi power saving is disabled in its NetworkManager connection profile. These hardware settings are separate from the app installer; retain the official Pi power supply.

Run `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v` on the Pi for configuration preservation, menu navigation, portrait layout, missing-credentials handling, and shared-video refresh checks. GPIO is mocked in these tests; physical button wiring still needs a hardware check.

Ad blocking is not guaranteed because YouTube and browser extensions change; YouTube Premium is the reliable official ad-free option.

## Notes

- MP4 order is shuffled once for each app launch; newly discovered uploads are shuffled and appended when the library is reopened.
- Leaving a video returns directly to the video list with that item highlighted. Selecting that immediately previous unfinished video offers Resume or Restart; all other videos play normally. This temporary choice disappears after an app restart.
- Landscape video is letterboxed, never cropped.
