#!/usr/bin/env bash
# Render Build Script for Point-Tracker
# Installs Python dependencies, Node.js dependencies, and Chromium for WhatsApp

set -o errexit  # Exit on error

echo "=== Installing Python dependencies ==="
pip install -r requirements.txt

echo "=== Installing Node.js dependencies for WhatsApp service ==="
# Check if Node.js is available
if command -v node &> /dev/null; then
    echo "Node.js version: $(node --version)"
    echo "npm version: $(npm --version)"

    # Install WhatsApp service dependencies
    cd whatsapp_service
    npm install

    # Install Chromium for Puppeteer
    echo "=== Installing Chromium for Puppeteer ==="
    npx puppeteer browsers install chrome

    cd ..

    echo "WhatsApp service dependencies installed successfully"
else
    echo "WARNING: Node.js not found. WhatsApp automation will not be available."
    echo "To enable WhatsApp, ensure Node.js is installed on the server."
fi

echo "=== Build complete ==="
