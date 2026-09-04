#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${REPO_DIR}/dist"
APPDIR="${DIST_DIR}/AppDir"

echo "[*] Building PV-IDM AppDir..."
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin" "${APPDIR}/usr/share/applications" "${APPDIR}/usr/share/icons/hicolor/128x128/apps" "${APPDIR}/usr/lib/pv-idm"

# Copy python packages
cp -r "${REPO_DIR}/idm_core" "${APPDIR}/usr/lib/pv-idm/"
cp -r "${REPO_DIR}/idm_gui" "${APPDIR}/usr/lib/pv-idm/"
cp -r "${REPO_DIR}/idm_ipc" "${APPDIR}/usr/lib/pv-idm/"
cp -r "${REPO_DIR}/idm_cli" "${APPDIR}/usr/lib/pv-idm/"
cp -r "${REPO_DIR}/idm_native_host" "${APPDIR}/usr/lib/pv-idm/"
cp -r "${REPO_DIR}/extension" "${APPDIR}/usr/lib/pv-idm/"
cp -r "${REPO_DIR}/scripts" "${APPDIR}/usr/lib/pv-idm/"

# Copy desktop and icon
cp "${REPO_DIR}/scripts/pv-idm.desktop" "${APPDIR}/pv-idm.desktop"
cp "${REPO_DIR}/scripts/pv-idm.desktop" "${APPDIR}/usr/share/applications/pv-idm.desktop"
cp "${REPO_DIR}/extension/icons/icon128.png" "${APPDIR}/pv-idm.png"
cp "${REPO_DIR}/extension/icons/icon128.png" "${APPDIR}/.DirIcon"
cp "${REPO_DIR}/extension/icons/icon128.png" "${APPDIR}/usr/share/icons/hicolor/128x128/apps/pv-idm.png"

# Create AppRun
cat << 'EOF' > "${APPDIR}/AppRun"
#!/bin/bash
APPDIR="$(dirname "$(readlink -f "$0")")"
export PYTHONPATH="${APPDIR}/usr/lib/pv-idm:${PYTHONPATH}"
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
