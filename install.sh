#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Starting URL image to e-ink Installation ==="

# 1. Check for root privileges
if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run this script with sudo: sudo ./install.sh"
  exit 1
fi

echo "=== Updating package index and installing system dependencies ==="
sudo apt update
sudo apt install -y python3 python3-pip python3-pil python3-rpi.gpio python3-spidev git

echo "==> Enabling SPI interface..."
if command -v raspi-config > /dev/null; then
    sudo raspi-config nonint do_spi 0
    echo "SPI enabled successfully."
else
    echo "Warning: raspi-config not found. Make sure SPI is enabled manually."
fi

echo "==> Cloning Waveshare repository (shallow clone)..."
git clone --depth 1 https://github.com/waveshare/e-Paper.git /tmp/e-Paper-repo

echo "==> Installing Waveshare e-Paper library globally..."
sudo pip3 install --break-system-packages /tmp/e-Paper-repo/RaspberryPi_JetsonNano/python

echo "==> Cleaning up temporary files..."
rm -rf /tmp/e-Paper-repo

echo "=========================================================="
echo " Installation Complete!"
echo " You can now run the script directly with system Python. Examples:"
echo " Generate a local preview:"
echo " python3 url_jpg_to_eink.py 'https://picsum.photos/800/480' --width 800 --height 480 --output /tmp/random_eink.png"
echo " Send directly to the connected Waveshare screen:"
echo " python3 url_jpg_to_eink.py 'https://picsum.photos/800/480' --width 800 --height 480 --model epd7in5_V2 --display"
echo "=========================================================="
