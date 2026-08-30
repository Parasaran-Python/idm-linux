#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/128x128/apps"
PYTHON_BIN="${PYTHON_BIN:-/run/media/parasaran/Dev/SDK/python/install/bin/python3}"

echo "========================================================"
echo "          Installing IDM Linux Integration              "
echo "========================================================"

mkdir -p "${BIN_DIR}" "${DESKTOP_DIR}" "${ICON_DIR}"

# 1. Create CLI Wrapper (`idm`)
cat << EOF > "${BIN_DIR}/idm"
#!/bin/bash
REPO_DIR="${REPO_DIR}"
PYTHON_BIN="${PYTHON_BIN}"
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/local/lib/python3.14/dist-packages:\${REPO_DIR}:\$PYTHONPATH"
exec "\${PYTHON_BIN}" -m idm_cli.cli "\$@"
EOF
chmod +x "${BIN_DIR}/idm"

# 2. Create GUI Wrapper (`idm-gui`)
cat << EOF > "${BIN_DIR}/idm-gui"
#!/bin/bash
REPO_DIR="${REPO_DIR}"
PYTHON_BIN="${PYTHON_BIN}"
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/local/lib/python3.14/dist-packages:\${REPO_DIR}:\$PYTHONPATH"
exec "\${PYTHON_BIN}" -m idm_gui.app "\$@"
EOF
chmod +x "${BIN_DIR}/idm-gui"

# 3. Create Daemon Wrapper (`idm-daemon`)
cat << EOF > "${BIN_DIR}/idm-daemon"
#!/bin/bash
REPO_DIR="${REPO_DIR}"
PYTHON_BIN="${PYTHON_BIN}"
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/local/lib/python3.14/dist-packages:\${REPO_DIR}:\$PYTHONPATH"
exec "\${PYTHON_BIN}" -m idm_ipc.daemon "\$@"
EOF
chmod +x "${BIN_DIR}/idm-daemon"

# 4. Install Desktop File and Multi-Resolution Icons
for sz in 16 32 48 128 256 512; do
    target_dir="${HOME}/.local/share/icons/hicolor/${sz}x${sz}/apps"
    mkdir -p "${target_dir}"
    if [ -f "${REPO_DIR}/extension/icons/icon${sz}.png" ]; then
        cp "${REPO_DIR}/extension/icons/icon${sz}.png" "${target_dir}/idm-linux.png"
    fi
done
cp "${REPO_DIR}/scripts/idm-linux.desktop" "${DESKTOP_DIR}/idm-linux.desktop"

# 5. Register Browser Native Messaging Hosts
echo "[*] Registering Browser Native Messaging Hosts..."
PYTHONPATH="/usr/lib/python3/dist-packages:/usr/local/lib/python3.14/dist-packages:${REPO_DIR}:$PYTHONPATH" \
  "${PYTHON_BIN}" "${REPO_DIR}/scripts/install_native_host.py"

# 6. Update Desktop and Icon Databases if available
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo "========================================================"
echo " [OK] IDM Linux Installed Successfully!"
echo " Binaries: ${BIN_DIR}/idm, ${BIN_DIR}/idm-gui"
echo " Desktop Launcher: ${DESKTOP_DIR}/idm-linux.desktop"
echo " Browser Extension Directory: ${REPO_DIR}/extension"
echo "========================================================"
