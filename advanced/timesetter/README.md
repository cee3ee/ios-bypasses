# Pi iOS Auto-Spoofer

Headless, plug-and-play iOS GPS location simulation running on a **Raspberry Pi Zero 2 W** over local Wi-Fi. Once configured, plugging the Pi into any power outlet automatically discovers your paired iPhone over Bonjour/mDNS, establishes an encrypted RemoteXPC tunnel via `pymobiledevice3`, mounts the Developer Disk Image, and locks in your target coordinates—with no cables attached to the phone and no third-party VPN profiles installed on iOS.

## Repository Structure

```text
.
├── auto_spoof.py              # Daemon polling tunneld and applying DVT location locks
├── install.sh                 # Automated Raspberry Pi setup script
├── requirements.txt           # Python dependencies
├── systemd/
│   ├── tunneld.service        # RemoteXPC Wi-Fi tunnel service (with wlan0 readiness guard)
│   └── autospoof.service      # Auto-spoofer watcher service
├── .gitignore                 # Excludes sensitive Apple pairing .plist files and disk images
├── LICENSE
└── README.md
```

## Prerequisites

* **Hardware:** Raspberry Pi Zero 2 W + microSD card + Micro-USB power supply.
* **OS:** Raspberry Pi OS Lite (**64-bit** / `aarch64` recommended so prebuilt cryptography wheels install cleanly).
* **iOS Device:** iPhone with **Developer Mode** enabled (`Settings -> Privacy & Security -> Developer Mode`).
* **Host PC (One-Time Setup):** Windows or Linux machine with `pymobiledevice3` installed to generate the initial USB trust pairing records.
* **Network:** Both the Pi and iPhone must be on the same **2.4 GHz** local Wi-Fi network.

---

## Setup Guide

### 1. Flash Raspberry Pi OS Lite (64-bit)

1. Open **Raspberry Pi Imager** and choose **Raspberry Pi Zero 2 W** -> **Raspberry Pi OS (other)** -> **Raspberry Pi OS Lite (64-bit)**.
2. Click **Edit Settings**:
   * Set hostname (e.g., `pizero`), username, and password.
   * Configure your **2.4 GHz** Wi-Fi SSID/password and country code.
   * Enable **SSH** using password authentication.
3. Flash the microSD card, insert it into the Pi Zero 2 W, plug power into the outer **`PWR IN`** port, and wait ~60–90 seconds for first boot.

---

### 2. Generate & Export Pairing Records (One-Time on Host PC)

Plug your iPhone into your PC via USB, unlock it, and tap **Trust**.

#### On Windows (Admin PowerShell)

```powershell
# 1. Enable Wi-Fi lockdown connections and create RemotePairing record
python -m pymobiledevice3 lockdown wifi-connections on
python -m pymobiledevice3 lockdown remotepairing --pair

# 2. Export both pairing directories to the Raspberry Pi
$exportDir = "$env:TEMP\ios_pair_export"
New-Item -ItemType Directory -Force -Path "$exportDir\lockdown", "$exportDir\pmd3" | Out-Null
Copy-Item -Path "C:\ProgramData\Apple\Lockdown\*" -Destination "$exportDir\lockdown\" -Recurse -Force
Copy-Item -Path "$env:USERPROFILE\.pymobiledevice3\*" -Destination "$exportDir\pmd3\" -Recurse -Force

scp -r "$exportDir" <PI_USER>@pizero.local:~/
Remove-Item -Path "$exportDir" -Recurse -Force
```

#### On Linux

```bash
# 1. Enable Wi-Fi lockdown connections and create RemotePairing record
python3 -m pymobiledevice3 lockdown wifi-connections on
python3 -m pymobiledevice3 lockdown remotepairing --pair

# 2. Export both pairing directories to the Raspberry Pi
mkdir -p /tmp/ios_pair_export/lockdown /tmp/ios_pair_export/pmd3
sudo cp -r /var/lib/lockdown/* /tmp/ios_pair_export/lockdown/
cp -r ~/.pymobiledevice3/* /tmp/ios_pair_export/pmd3/
sudo chown -R "$USER:$USER" /tmp/ios_pair_export

scp -r /tmp/ios_pair_export <PI_USER>@pizero.local:~/
rm -rf /tmp/ios_pair_export
```

---

### 3. Install on the Raspberry Pi

SSH into your Pi (`ssh <PI_USER>@pizero.local`), import the pairing records, and run `install.sh`:

```bash
# Import lockdown and RemotePairing records for root systemd services
sudo mkdir -p /var/lib/lockdown /root/.pymobiledevice3 ~/.pymobiledevice3
sudo cp -r ~/ios_pair_export/lockdown/* /var/lib/lockdown/
sudo chown -R usbmux:root /var/lib/lockdown
sudo chmod 600 /var/lib/lockdown/*.plist

sudo cp -r ~/ios_pair_export/pmd3/* /root/.pymobiledevice3/
cp -r ~/ios_pair_export/pmd3/* ~/.pymobiledevice3/
sudo chmod 600 /root/.pymobiledevice3/*.plist
chmod 600 ~/.pymobiledevice3/*.plist
rm -rf ~/ios_pair_export
sudo systemctl restart usbmuxd

# Clone repository and run installer
git clone [https://github.com/](https://github.com/)<YOUR_USERNAME>/<YOUR_REPO>.git
cd <YOUR_REPO>
sudo bash install.sh
```

---

## Configuration

Target coordinates are stored in `/etc/default/auto-spoof` on the Pi (defaults to Chicago, IL):

```bash
sudo nano /etc/default/auto-spoof
```

```env
TARGET_LAT=41.8781
TARGET_LON=-87.6298
```

Restart the watcher after changing coordinates:

```bash
sudo systemctl restart autospoof.service
```

---

## Usage & Troubleshooting

* **Activate spoofing:** Plug the Pi into power and ensure your iPhone screen is unlocked on the same Wi-Fi network. From a cold boot, the Pi takes roughly **45 seconds** to boot, establish the tunnel, and lock the location.
* **Revert to real GPS:** Unplug the Pi (or run `sudo systemctl stop autospoof.service`) and restart your iPhone.
* **View live logs:**
  ```bash
  sudo journalctl -u tunneld.service -u autospoof.service -f
  ```

## Security Note

Never commit your `lockdown/` or `.pymobiledevice3/` folders (`.plist` pairing certificates) to GitHub—they grant cryptographic developer access to your iPhone over Wi-Fi. `.gitignore` is pre-configured to block these files.
