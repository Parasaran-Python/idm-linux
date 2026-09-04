@echo off
setlocal
echo =======================================================
echo PV-IDM - Browser Native Messaging Host Registration
echo =======================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "EXE_CANDIDATE=%SCRIPT_DIR%pv-idm.exe"
if not exist "%EXE_CANDIDATE%" (
    set "EXE_CANDIDATE=%SCRIPT_DIR%idm.exe"
)

set "HOST_CANDIDATE=%SCRIPT_DIR%pv-idm-native-host.exe"
if not exist "%HOST_CANDIDATE%" (
    set "HOST_CANDIDATE=%SCRIPT_DIR%idm-native-host.exe"
)

if exist "%EXE_CANDIDATE%" (
    if exist "%HOST_CANDIDATE%" (
        "%EXE_CANDIDATE%" install-native-host -b "%HOST_CANDIDATE%" %*
    ) else (
        "%EXE_CANDIDATE%" install-native-host %*
    )
) else if exist "%SCRIPT_DIR%_internal\scripts\install_native_host.py" (
    python "%SCRIPT_DIR%_internal\scripts\install_native_host.py" %*
) else if exist "%SCRIPT_DIR%scripts\install_native_host.py" (
    python "%SCRIPT_DIR%scripts\install_native_host.py" %*
) else (
    python -m idm_cli.cli install-native-host %*
)

echo.
echo =======================================================
echo Process completed.
echo Please restart or reload your browser extension if open.
echo =======================================================
if not "%1"=="--no-pause" (
    pause
)
