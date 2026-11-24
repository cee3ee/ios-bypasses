#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "[!] Please run as root: sudo bash install.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="/opt/ios-spoofer"
TARGET_BIN="/usr/local/bin/auto_spoof.py"
DEFAULT_CFG="/etc/default/auto-spoof"

echo "[1/5] Installing system dependencies..."
apt-get update
apt-get install -y usbmuxd libusb-1.0-0 openssl avahi-daemon python3-pip python3-venv

echo "[2/5] Setting up Python virtual environment in ${VENV_DIR}..."
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --no-cache-dir --upgrade pip
"${VENV_DIR}/bin/pip" install --no-cache-dir -r "${SCRIPT_DIR}/requirements.txt"

echo "[3/5] Installing auto_spoof.py to ${TARGET_BIN}..."
install -m 0755 "${SCRIPT_DIR}/auto_spoof.py" "${TARGET_BIN}"

if [[ ! -f "${DEFAULT_CFG}" ]]; then
  echo "[4/5] Creating default coordinate config at ${DEFAULT_CFG}..."
  cat << 'EOF' > "${DEFAULT_CFG}"
# Target GPS coordinates applied upon iPhone connection
TARGET_LAT=41.8781
TARGET_LON=-87.6298
EOF
else
  echo "[4/5] Existing ${DEFAULT_CFG} preserved."
fi

echo "[5/5] Installing and enabling systemd services..."
install -m 0644 "${SCRIPT_DIR}/systemd/tunneld.service" /etc/systemd/system/tunneld.service
install -m 0644 "${SCRIPT_DIR}/systemd/autospoof.service" /etc/systemd/system/autospoof.service

systemctl daemon-reload
systemctl enable --now tunneld.service autospoof.service

echo "[✓] Installation complete. Ensure pairing records are copied to /var/lib/lockdown and /root/.pymobiledevice3."
