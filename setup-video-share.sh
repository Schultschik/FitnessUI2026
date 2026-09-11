#!/usr/bin/env bash
set -euo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
if (( EUID != 0 )); then exec sudo bash "$0" "${1:-$USER}"; fi
user_name="${1:-${SUDO_USER:-}}"
[[ "$user_name" =~ ^[a-z_][a-z0-9_-]*$ && "$user_name" != root ]] || exit 1
id "$user_name" >/dev/null
export DEBIAN_FRONTEND=noninteractive
apt-get -o Acquire::Retries=3 update
apt-get -o Acquire::Retries=3 install -y samba smbclient
install -d -o "$user_name" -g "$(id -gn "$user_name")" -m 2770 /mnt/fitness-media/videos
python3 - "$user_name" <<'PY'
import shutil
import sys
from pathlib import Path
path = Path('/etc/samba/smb.conf')
original = path.read_text()
backup = path.with_suffix('.conf.pre-fitness')
if not backup.exists():
    shutil.copy2(path, backup)
begin, end = '# BEGIN FITNESS VIDEOS', '# END FITNESS VIDEOS'
if begin in original:
    before, managed = original.split(begin, 1)
    _, after = managed.split(end, 1)
    original = before + after.lstrip('\n')
elif '[Videos]' in original:
    raise SystemExit('An unmanaged Videos share exists; inspect it before replacing it.')
block = f'''{begin}
[Videos]
    path = /mnt/fitness-media/videos
    browseable = yes
    read only = no
    guest ok = no
    valid users = {sys.argv[1]}
    create mask = 0660
    directory mask = 0770
{end}
'''
path.write_text(original.rstrip() + '\n\n' + block)
PY
testparm -s >/dev/null
systemctl enable --now smbd
systemctl reload smbd
echo "Videos share configured. Set the share password with: sudo smbpasswd -a $user_name"
