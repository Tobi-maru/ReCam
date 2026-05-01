#!/bin/bash

# ReCam Installation Script
# Run this script with sudo

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (e.g., sudo ./scripts/install.sh)"
  exit 1
fi

echo "--- ReCam Installation ---"

# 1. Install dependencies
echo "[1/4] Installing system dependencies..."
if command -v apt-get &> /dev/null; then
  apt-get update
  apt-get install -y scrcpy adb v4l2loopback-dkms v4l-utils python3
elif command -v pacman &> /dev/null; then
  pacman -Sy --noconfirm scrcpy android-tools v4l2loopback-dkms v4l-utils python
elif command -v dnf &> /dev/null; then
  dnf install -y scrcpy android-tools v4l2loopback v4l-utils python3
else
  echo "Warning: Package manager not found. Please ensure scrcpy, adb, v4l2loopback, and v4l-utils are installed."
fi

# 2. Setup Udev Rules & Triggers
echo "[2/4] Setting up Android USB rules and triggers..."
install -m 755 deploy/ReCam-map-triggers.sh /usr/local/bin/recam-map-triggers.sh
install -m 644 deploy/ReCam.rules /etc/udev/rules.d/99-recam.rules
udevadm control --reload-rules
udevadm trigger

# 3. Setup v4l2loopback Systemd Service
echo "[3/4] Configuring v4l2loopback systemd service..."
install -m 644 deploy/ReCam.service /etc/systemd/system/recam-loopback.service
systemctl daemon-reload
systemctl enable recam-loopback.service
systemctl start recam-loopback.service

# 4. Verify Virtual Camera Status
echo "[4/4] Verifying the virtual interface..."
sleep 2
if [ -c /dev/video9 ]; then
  echo "Success: /dev/video9 placeholder is active."
else
  echo "Warning: /dev/video9 is not present. You may need to reboot your machine."
fi

echo "--- Installation Complete ---"
echo "You can now start the engine by running: python3 src/main.py"
