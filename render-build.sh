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

    # Set Puppeteer cache to a persistent location within the project
    export PUPPETEER_CACHE_DIR="/opt/render/project/src/.puppeteer"
    mkdir -p "$PUPPETEER_CACHE_DIR"

    # Install WhatsApp service dependencies
    cd whatsapp_service
    npm install

    # Install Chromium for Puppeteer in the persistent location
    echo "=== Installing Chromium for Puppeteer ==="
    echo "Cache directory: $PUPPETEER_CACHE_DIR"
    npx puppeteer browsers install chrome

    cd ..

    echo "WhatsApp service dependencies installed successfully"
    echo "Chrome installed to: $PUPPETEER_CACHE_DIR"
else
    echo "WARNING: Node.js not found. WhatsApp automation will not be available."
    echo "To enable WhatsApp, ensure Node.js is installed on the server."
fi

echo "=== Build complete ==="
