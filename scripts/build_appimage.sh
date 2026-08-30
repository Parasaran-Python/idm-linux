#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_DIR}/dist"
APPDIR="${DIST_DIR}/AppDir"

echo "[*] Building IDM Linux AppDir..."
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" "${APPDIR}/usr/share/icons/hicolor/128x128/apps" "${APPDIR}/usr/lib/idm-linux"

# Copy python packages
cp -r "${REPO_DIR}/idm_core" "${APPDIR}/usr/lib/idm-linux/"
cp -r "${REPO_DIR}/idm_gui" "${APPDIR}/usr/lib/idm-linux/"
cp -r "${REPO_DIR}/idm_ipc" "${APPDIR}/usr/lib/idm-linux/"
cp -r "${REPO_DIR}/idm_cli" "${APPDIR}/usr/lib/idm-linux/"
cp -r "${REPO_DIR}/idm_native_host" "${APPDIR}/usr/lib/idm-linux/"
cp -r "${REPO_DIR}/extension" "${APPDIR}/usr/lib/idm-linux/"
cp -r "${REPO_DIR}/scripts" "${APPDIR}/usr/lib/idm-linux/"

# Copy desktop and icon
cp "${REPO_DIR}/scripts/idm-linux.desktop" "${APPDIR}/idm-linux.desktop"
cp "${REPO_DIR}/scripts/idm-linux.desktop" "${APPDIR}/usr/share/applications/idm-linux.desktop"
cp "${REPO_DIR}/extension/icons/icon128.png" "${APPDIR}/idm-linux.png"
cp "${REPO_DIR}/extension/icons/icon128.png" "${APPDIR}/.DirIcon"
cp "${REPO_DIR}/extension/icons/icon128.png" "${APPDIR}/usr/share/icons/hicolor/128x128/apps/idm-linux.png"

# Create AppRun
cat << 'EOF' > "${APPDIR}/AppRun"
#!/bin/bash
APPDIR="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="${APPDIR}/usr/lib/idm-linux:${PYTHONPATH}"
export PATH="${APPDIR}/usr/bin:${PATH}"

if [ "$1" = "cli" ] || [ "$1" = "add" ] || [ "$1" = "list" ] || [ "$1" = "pause" ] || [ "$1" = "resume" ]; then
    exec python3 -m idm_cli.cli "$@"
elif [ "$1" = "daemon" ]; then
    exec python3 -m idm_ipc.daemon "$@"
elif [ "$1" = "native-host" ]; then
    exec python3 -m idm_native_host.host "$@"
else
    exec python3 -m idm_gui.app "$@"
fi
EOF
chmod +x "${APPDIR}/AppRun"

echo "[OK] AppDir generated at: ${APPDIR}"
