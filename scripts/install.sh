#!/bin/bash

# --- Color Codes ---
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== ReCam: Cross-Distro Setup ===${NC}"

# 1. Detect Package Manager
if command -v pacman &> /dev/null; then
    PKG_MGR="pacman"
    DEPS=("scrcpy" "v4l2loopback-dkms" "android-tools" "linux-headers")
    INSTALL_CMD="pacman -S --noconfirm --needed"
elif command -v apt-get &> /dev/null; then
    PKG_MGR="apt"
    DEPS=("scrcpy" "v4l2loopback-dkms" "android-tools-adb" "linux-headers-$(uname -r)")
    INSTALL_CMD="apt-get install -y"
else
    echo -e "${RED}Unsupported distribution. Manually install scrcpy and v4l2loopback.${NC}"
    exit 1
fi

# 2. Execute Installation
echo -e "${BLUE}Detected $PKG_MGR. Installing dependencies...${NC}"
pkexec $INSTALL_CMD "${DEPS[@]}"

# 3. Arch-Specific DKMS Check
if [ "$PKG_MGR" == "pacman" ]; then
    echo -e "${BLUE}Ensuring DKMS is active for Arch...${NC}"
    pkexec systemctl enable --now dkms
fi

# 4. Kernel Module Configuration (The "Pro" Standard)
CONF_FILE="/etc/modprobe.d/recam.conf"
MODULE_OPTIONS="options v4l2loopback devices=1 video_nr=9 card_label='ReCam' exclusive_caps=1"

if [ ! -f "$CONF_FILE" ]; then
    echo "$MODULE_OPTIONS" | pkexec tee "$CONF_FILE" > /dev/null
    pkexec modprobe v4l2loopback
fi

echo -e "${GREEN}Environment ready for ReCam development.${NC}"