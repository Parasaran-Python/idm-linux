#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_DIR}/dist"

mkdir -p "${DIST_DIR}/chrome-extension"
mkdir -p "${DIST_DIR}/firefox-extension"

echo "[*] Packaging Chrome Extension (MV3)..."
rm -rf "${DIST_DIR}/chrome-extension"/*
cp -r "${REPO_DIR}/extension/background" \
      "${REPO_DIR}/extension/content" \
      "${REPO_DIR}/extension/popup" \
      "${REPO_DIR}/extension/icons" \
      "${REPO_DIR}/extension/manifest.json" \
      "${DIST_DIR}/chrome-extension/"

(cd "${DIST_DIR}/chrome-extension" && zip -q -r "${DIST_DIR}/idm-linux-extension-chrome-mv3.zip" .)

echo "[*] Packaging Firefox Extension (MV2/MV3)..."
rm -rf "${DIST_DIR}/firefox-extension"/*
cp -r "${REPO_DIR}/extension/background" \
      "${REPO_DIR}/extension/content" \
      "${REPO_DIR}/extension/popup" \
      "${REPO_DIR}/extension/icons" \
      "${DIST_DIR}/firefox-extension/"
cp "${REPO_DIR}/extension/manifest.firefox.json" "${DIST_DIR}/firefox-extension/manifest.json"

(cd "${DIST_DIR}/firefox-extension" && zip -q -r "${DIST_DIR}/idm-linux-extension-firefox.zip" .)
cp "${DIST_DIR}/idm-linux-extension-firefox.zip" "${DIST_DIR}/idm-linux-extension-firefox.xpi"

rm -rf "${DIST_DIR}/chrome-extension" "${DIST_DIR}/firefox-extension"

echo "[OK] Built:"
echo "  - ${DIST_DIR}/idm-linux-extension-chrome-mv3.zip"
echo "  - ${DIST_DIR}/idm-linux-extension-firefox.zip"
echo "  - ${DIST_DIR}/idm-linux-extension-firefox.xpi"
