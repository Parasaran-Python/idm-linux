#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/128x128/apps"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || echo "python3")}"
PY_VER="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")"
EXTRA_PY_PATHS="/usr/lib/python3/dist-packages"
if [ -n "${PY_VER}" ]; then
    EXTRA_PY_PATHS="${EXTRA_PY_PATHS}:/usr/local/lib/python${PY_VER}/dist-packages"
fi

echo "========================================================"
echo "          Installing PV-IDM Integration                 "
echo "========================================================"

mkdir -p "${BIN_DIR}" "${DESKTOP_DIR}" "${ICON_DIR}"

# 1. Create CLI Wrapper (`pv-idm`, `idm`, `idm-linux`)
rm -f "${BIN_DIR}/pv-idm" "${BIN_DIR}/idm" "${BIN_DIR}/idm-linux"
cat << EOF > "${BIN_DIR}/pv-idm"
#!/bin/bash
REPO_DIR="${REPO_DIR}"
PYTHON_BIN="${PYTHON_BIN}"
export PYTHONPATH="${EXTRA_PY_PATHS}:\${REPO_DIR}:\$PYTHONPATH"
exec "\${PYTHON_BIN}" -m idm_cli.cli "\$@"
EOF
chmod +x "${BIN_DIR}/pv-idm"
ln -sf "${BIN_DIR}/pv-idm" "${BIN_DIR}/idm"
ln -sf "${BIN_DIR}/pv-idm" "${BIN_DIR}/idm-linux"

# 2. Create GUI Wrapper (`pv-idm-gui`, `idm-gui`, `idm-linux-gui`)
rm -f "${BIN_DIR}/pv-idm-gui" "${BIN_DIR}/idm-gui" "${BIN_DIR}/idm-linux-gui"
cat << EOF > "${BIN_DIR}/pv-idm-gui"
#!/bin/bash
REPO_DIR="${REPO_DIR}"
PYTHON_BIN="${PYTHON_BIN}"
export PYTHONPATH="${EXTRA_PY_PATHS}:\${REPO_DIR}:\$PYTHONPATH"
exec "\${PYTHON_BIN}" -m idm_gui.app "\$@"
EOF
chmod +x "${BIN_DIR}/pv-idm-gui"
ln -sf "${BIN_DIR}/pv-idm-gui" "${BIN_DIR}/idm-gui"
ln -sf "${BIN_DIR}/pv-idm-gui" "${BIN_DIR}/idm-linux-gui"

# 3. Create Daemon Wrapper (`pv-idm-daemon`, `idm-daemon`)
rm -f "${BIN_DIR}/pv-idm-daemon" "${BIN_DIR}/idm-daemon"
cat << EOF > "${BIN_DIR}/pv-idm-daemon"
#!/bin/bash
REPO_DIR="${REPO_DIR}"
PYTHON_BIN="${PYTHON_BIN}"
export PYTHONPATH="${EXTRA_PY_PATHS}:\${REPO_DIR}:\$PYTHONPATH"
exec "\${PYTHON_BIN}" -m idm_ipc.daemon "\$@"
EOF
chmod +x "${BIN_DIR}/pv-idm-daemon"
ln -sf "${BIN_DIR}/pv-idm-daemon" "${BIN_DIR}/idm-daemon"

# 4. Create Native Host Wrapper (`pv-idm-native-host`, `idm-native-host`)
rm -f "${BIN_DIR}/pv-idm-native-host" "${BIN_DIR}/idm-native-host"
cat << EOF > "${BIN_DIR}/pv-idm-native-host"
#!/bin/bash
REPO_DIR="${REPO_DIR}"
PYTHON_BIN="${PYTHON_BIN}"
export PYTHONPATH="${EXTRA_PY_PATHS}:\${REPO_DIR}:\$PYTHONPATH"
exec "\${PYTHON_BIN}" -m idm_native_host.host "\$@"
EOF
chmod +x "${BIN_DIR}/pv-idm-native-host"
ln -sf "${BIN_DIR}/pv-idm-native-host" "${BIN_DIR}/idm-native-host"

# 5. Install Desktop File and Multi-Resolution Icons
for sz in 16 32 48 128 256 512; do
    target_dir="${HOME}/.local/share/icons/hicolor/${sz}x${sz}/apps"
    mkdir -p "${target_dir}"
    if [ -f "${REPO_DIR}/extension/icons/icon${sz}.png" ]; then
        cp "${REPO_DIR}/extension/icons/icon${sz}.png" "${target_dir}/pv-idm.png"
        cp "${REPO_DIR}/extension/icons/icon${sz}.png" "${target_dir}/idm-linux.png"
    fi
done
cp "${REPO_DIR}/scripts/pv-idm.desktop" "${DESKTOP_DIR}/pv-idm.desktop"
rm -f "${DESKTOP_DIR}/idm-linux.desktop"

# 6. Register Browser Native Messaging Hosts
echo "[*] Registering Browser Native Messaging Hosts..."
PYTHONPATH="${EXTRA_PY_PATHS}:${REPO_DIR}:$PYTHONPATH" \
  "${PYTHON_BIN}" "${REPO_DIR}/scripts/install_native_host.py"

# 7. Package Browser Extensions into dist/
echo "[*] Packaging Browser Extensions..."
"${PYTHON_BIN}" "${REPO_DIR}/scripts/package_extensions.py"

# 8. Update Desktop and Icon Databases if available
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${DESKTOP_DIR}" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo "========================================================"
echo " [OK] PV-IDM Installed Successfully!"
echo " Binaries: ${BIN_DIR}/pv-idm, ${BIN_DIR}/pv-idm-gui, ${BIN_DIR}/pv-idm-daemon, ${BIN_DIR}/pv-idm-native-host"
echo " Desktop Launcher: ${DESKTOP_DIR}/pv-idm.desktop"
echo " Chrome Extension: ${REPO_DIR}/dist/chrome-extension"
echo " Firefox Extension: ${REPO_DIR}/dist/pv-idm-extension-firefox.xpi"
echo "========================================================"
