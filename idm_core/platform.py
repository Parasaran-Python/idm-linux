"""
Platform Abstraction Layer for IDM
Provides cross-platform paths, OS detection, binary resolution, and system actions.
Supports Linux, Windows, and macOS.
"""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple


def is_windows() -> bool:
    """Return True if running on Microsoft Windows."""
    return sys.platform == "win32" or sys.platform.startswith("cygwin")


def is_linux() -> bool:
    """Return True if running on a Linux kernel."""
    return sys.platform.startswith("linux")


def is_macos() -> bool:
    """Return True if running on macOS (Darwin)."""
    return sys.platform.startswith("darwin")


def get_platform_name() -> str:
    """Return normalized platform name: 'windows', 'linux', or 'macos'."""
    if is_windows():
        return "windows"
    if is_macos():
        return "macos"
    return "linux"


def get_config_dir(custom_dir: Optional[str] = None) -> str:
    r"""
    Return the base configuration and data directory.
    - Windows: %APPDATA%\pv-idm (fallback to ~/.config/pv-idm)
    - Linux: ~/.config/pv-idm (or $XDG_CONFIG_HOME/pv-idm)
    - macOS: ~/Library/Application Support/pv-idm
    """
    if custom_dir:
        return os.path.abspath(custom_dir)

    if is_windows():
        appdata = os.environ.get("APPDATA")
        if appdata:
            target = os.path.join(appdata, "pv-idm")
            legacy = os.path.join(appdata, "idm-linux")
            if not os.path.exists(target) and os.path.exists(legacy):
                return legacy
            return target
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            target = os.path.join(localappdata, "pv-idm")
            legacy = os.path.join(localappdata, "idm-linux")
            if not os.path.exists(target) and os.path.exists(legacy):
                return legacy
            return target
        target = os.path.expanduser("~/.config/pv-idm")
        legacy = os.path.expanduser("~/.config/idm-linux")
        if not os.path.exists(target) and os.path.exists(legacy):
            return legacy
        return target

    if is_macos():
        target = os.path.expanduser("~/Library/Application Support/pv-idm")
        legacy = os.path.expanduser("~/Library/Application Support/idm-linux")
        if not os.path.exists(target) and os.path.exists(legacy):
            return legacy
        return target

    # Linux / FreeDesktop default
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        target = os.path.join(xdg_config, "pv-idm")
        legacy = os.path.join(xdg_config, "idm-linux")
        if not os.path.exists(target) and os.path.exists(legacy):
            return legacy
        return target
    target = os.path.expanduser("~/.config/pv-idm")
    legacy = os.path.expanduser("~/.config/idm-linux")
    if not os.path.exists(target) and os.path.exists(legacy):
        return legacy
    return target


def get_download_dir() -> str:
    """
    Return standard user Downloads directory.
    - Windows: Downloads folder via USERPROFILE or Windows Known Folders
    - Linux: ~/Downloads (or XDG_DOWNLOAD_DIR if defined)
    - macOS: ~/Downloads
    """
    if is_windows():
        # Try Windows Known Folder for Downloads via Win32 Shell API
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", wintypes.BYTE * 8)
                ]

            guid_downloads = GUID(
                0x374DE290, 0x123F, 0x4565,
                (wintypes.BYTE * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B)
            )
            buf = wintypes.LPWSTR()
            hr = ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid_downloads), 0, None, ctypes.byref(buf)
            )
            if hr == 0 and buf.value:
                res = str(buf.value)
                ctypes.windll.ole32.CoTaskMemFree(buf)
                if os.path.exists(res):
                    return res
        except Exception:
            pass

        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            return os.path.join(user_profile, "Downloads")

        return os.path.expanduser("~/Downloads")

    if is_linux():
        user_dirs = os.path.expanduser("~/.config/user-dirs.dirs")
        if os.path.exists(user_dirs):
            try:
                with open(user_dirs, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("XDG_DOWNLOAD_DIR="):
                            raw_val = line.split("=", 1)[1].strip('"\'')
                            raw_val = raw_val.replace("$HOME", os.path.expanduser("~"))
                            if os.path.exists(raw_val):
                                return raw_val
            except Exception:
                pass

    return os.path.expanduser("~/Downloads")


def get_temp_dir(config_dir: Optional[str] = None) -> str:
    """Return default temp directory for segmented download chunk buffers."""
    base = config_dir or get_config_dir()
    return os.path.join(base, "temp")


def get_database_path(config_dir: Optional[str] = None) -> str:
    """Return default SQLite database path."""
    base = config_dir or get_config_dir()
    return os.path.join(base, "idm.db")


def get_default_ipc_endpoint(config_dir: Optional[str] = None) -> str:
    """
    Return default IPC endpoint.
    - Windows: \\\\.\\pipe\\idm_ipc_socket
    - Linux/macOS: ~/.config/pv-idm/idm.sock
    """
    if is_windows():
        return r"\\.\pipe\idm_ipc_socket"
    base = config_dir or get_config_dir()
    return os.path.join(base, "idm.sock")


def get_binary_name(base_name: str) -> str:
    """Return executable filename for platform (e.g. ffmpeg -> ffmpeg.exe on Windows)."""
    if is_windows() and not base_name.lower().endswith(".exe"):
        return f"{base_name}.exe"
    return base_name


def resolve_binary(base_name: str) -> Optional[str]:
    """
    Locate an executable binary looking in:
    1. PyInstaller frozen bundled resource directory (_MEIPASS)
    2. Application directory / bin subdirectory
    3. System PATH (via shutil.which)
    """
    exe_name = get_binary_name(base_name)

    # 1. PyInstaller bundled directory
    if hasattr(sys, "_MEIPASS"):
        candidate = os.path.join(sys._MEIPASS, exe_name)
        if os.path.isfile(candidate) and (is_windows() or os.access(candidate, os.X_OK)):
            return candidate
        candidate_bin = os.path.join(sys._MEIPASS, "bin", exe_name)
        if os.path.isfile(candidate_bin) and (is_windows() or os.access(candidate_bin, os.X_OK)):
            return candidate_bin

    # 2. Next to running executable or script
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv else __file__))
    candidates = [
        os.path.join(app_dir, exe_name),
        os.path.join(app_dir, "bin", exe_name),
        os.path.join(app_dir, "_internal", "bin", exe_name),
        os.path.join(app_dir, "..", "bin", exe_name),
    ]
    for c in candidates:
        if os.path.isfile(c) and (is_windows() or os.access(c, os.X_OK)):
            return c

    # 3. Look in system PATH
    found = shutil.which(exe_name) or shutil.which(base_name)
    return found


def open_path(path: str):
    """Open a file or directory with system default application."""
    if not path or not os.path.exists(path):
        return

    if is_windows():
        try:
            os.startfile(path)  # type: ignore[attr-defined]
            return
        except Exception:
            pass

    if is_macos():
        try:
            subprocess.Popen(["open", path])
            return
        except Exception:
            pass

    # Linux fallback
    if shutil.which("xdg-open"):
        try:
            subprocess.Popen(["xdg-open", path])
            return
        except Exception:
            pass

    # Generic Qt QDesktopServices fallback if available
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))
    except Exception:
        pass


def reveal_in_file_manager(path: str):
    """Open file manager highlighting/selecting the target file or directory."""
    if not path or not os.path.exists(path):
        return

    abs_path = os.path.abspath(path)

    if is_windows():
        try:
            if os.path.isfile(abs_path):
                subprocess.Popen(["explorer.exe", "/select,", abs_path])
            else:
                subprocess.Popen(["explorer.exe", abs_path])
            return
        except Exception:
            pass

    if is_macos():
        try:
            subprocess.Popen(["open", "-R", abs_path])
            return
        except Exception:
            pass

    # Linux: If file, open its parent folder
    folder = abs_path if os.path.isdir(abs_path) else os.path.dirname(abs_path)
    open_path(folder)


def system_power_action(action: str) -> bool:
    """
    Perform system power action ('shutdown' or 'sleep'/'suspend').
    Cross-platform support for Linux, Windows, and macOS.
    """
    act = (action or "none").lower().strip()

    if act == "shutdown":
        if is_windows():
            res = subprocess.run(["shutdown", "/s", "/t", "0"], check=False)
            return res.returncode == 0
        if is_macos():
            res = subprocess.run(
                ["osascript", "-e", 'tell app "System Events" to shut down'],
                check=False
            )
            return res.returncode == 0
        res = subprocess.run(["systemctl", "poweroff"], check=False)
        return res.returncode == 0

    if act in ["sleep", "suspend"]:
        if is_windows():
            try:
                import ctypes
                ret = ctypes.windll.PowrProf.SetSuspendState(0, 1, 0)
                return bool(ret)
            except Exception:
                res = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState([System.Windows.Forms.PowerState]::Suspend, $false, $false)",
                    ],
                    check=False,
                )
                return res.returncode == 0
        if is_macos():
            res = subprocess.run(["pmset", "sleepnow"], check=False)
            return res.returncode == 0
        res = subprocess.run(["systemctl", "suspend"], check=False)
        return res.returncode == 0

    return False


def move_to_trash(filepath: str) -> bool:
    """
    Move a file to system Recycle Bin / Trash.
    Supports Windows Recycle Bin, Linux FreeDesktop Trash, and macOS Trash.
    """
    if not filepath or not os.path.exists(filepath):
        return False

    abs_path = os.path.abspath(filepath)

    # 1. Windows Recycle Bin via SHFileOperationW
    if is_windows():
        try:
            import ctypes
            from ctypes import wintypes

            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_SILENT = 0x0004

            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.WORD),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR),
                ]

            p_from = abs_path + "\0\0"
            fileop = SHFILEOPSTRUCTW()
            fileop.hwnd = None
            fileop.wFunc = FO_DELETE
            fileop.pFrom = p_from
            fileop.pTo = None
            fileop.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
            fileop.fAnyOperationsAborted = False
            fileop.hNameMappings = None
            fileop.lpszProgressTitle = None

            result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(fileop))
            if result == 0 and not fileop.fAnyOperationsAborted:
                return True
        except Exception:
            pass

    # 2. Linux gio trash
    if shutil.which("gio"):
        try:
            res = subprocess.run(["gio", "trash", abs_path], capture_output=True)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 3. Linux trash-put (trash-cli)
    if shutil.which("trash-put"):
        try:
            res = subprocess.run(["trash-put", abs_path], capture_output=True)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 4. Linux FreeDesktop fallback folder
    if is_linux():
        try:
            import datetime
            import urllib.parse
            trash_files = os.path.expanduser("~/.local/share/Trash/files")
            trash_info = os.path.expanduser("~/.local/share/Trash/info")
            os.makedirs(trash_files, exist_ok=True)
            os.makedirs(trash_info, exist_ok=True)

            fname = os.path.basename(abs_path)
            dest = os.path.join(trash_files, fname)
            info_file = os.path.join(trash_info, f"{fname}.trashinfo")
            del_date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            with open(info_file, "w", encoding="utf-8") as f:
                f.write(f"[Trash Info]\nPath={urllib.parse.quote(abs_path)}\nDeletionDate={del_date}\n")
            shutil.move(abs_path, dest)
            return True
        except Exception:
            pass

    # 5. Fallback: standard file removal
    try:
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
        else:
            os.remove(abs_path)
        return True
    except Exception:
        return False


def setup_windows_app_id():
    """Register explicit Application User Model ID (AUMID) on Windows for taskbar icon & notifications."""
    if is_windows():
        try:
            import ctypes
            app_id = "IDMLinux.IDM.App.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass


def show_desktop_notification(title: str, message: str, icon_path: Optional[str] = None) -> bool:
    """
    Display native OS desktop notification.
    - Windows: Uses windows-toasts if installed, or PowerShell WinRT ToastNotificationManager
    - Linux: Uses notify-send if available
    - macOS: Uses AppleScript display notification
    Returns True if successfully dispatched, False if fallback to Qt tray is required.
    """
    safe_title = (title or "PV-IDM").replace("`", "``").replace("'", "''").replace('"', '\\"')
    safe_msg = (message or "").replace("`", "``").replace("'", "''").replace('"', '\\"')

    # 1. Windows: Try windows-toasts library
    if is_windows():
        try:
            from windows_toasts import InteractableWindowsToaster, Toast, ToastDisplayImage
            toaster = InteractableWindowsToaster("PV-IDM", "PVIDM.IDM.App.1.0")
            toast = Toast()
            toast.text_fields = [title, message]
            if icon_path and os.path.exists(icon_path):
                toast.AddImage(ToastDisplayImage.fromPath(icon_path))
            toaster.show_toast(toast)
            return True
        except Exception:
            pass

        # Windows PowerShell WinRT Toast Notification fallback
        try:
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
            $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
            $textNodes = $template.GetElementsByTagName("text")
            $textNodes.Item(0).AppendChild($template.CreateTextNode("{safe_title}")) > $null
            $textNodes.Item(1).AppendChild($template.CreateTextNode("{safe_msg}")) > $null
            $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("IDMLinux.IDM.App.1.0")
            $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
            $notifier.Show($notification)
            """
            creationflags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags |= subprocess.CREATE_NO_WINDOW
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags
            )
            return True
        except Exception:
            pass

    # 2. Linux: notify-send
    if is_linux() and shutil.which("notify-send"):
        try:
            cmd = ["notify-send", title, message]
            if icon_path and os.path.exists(icon_path):
                cmd.extend(["-i", icon_path])
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    # 3. macOS: AppleScript notification
    if is_macos():
        try:
            ascript = f'display notification "{safe_msg}" with title "{safe_title}"'
            subprocess.Popen(["osascript", "-e", ascript], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass

    return False


# =====================================================================
# Native Messaging Host Registration & Discovery
# =====================================================================

NATIVE_HOST_NAME = "com.idm.linux.native_host"


def derive_chrome_extension_id(key_b64: str) -> str:
    """Compute 32-character Chrome extension ID from public key DER base64."""
    try:
        der = base64.b64decode(key_b64)
        sha = hashlib.sha256(der).digest()
        return "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 0x0F)) for b in sha[:16])
    except Exception:
        return ""


def get_default_chrome_extension_ids(repo_root: Optional[str] = None) -> List[str]:
    """Extract standard extension IDs from manifest.json and defaults."""
    ids = set()
    root = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest_path = os.path.join(root, "extension", "manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = data.get("key")
                if key:
                    derived_id = derive_chrome_extension_id(key)
                    if derived_id:
                        ids.add(derived_id)
        except Exception:
            pass

    # Ensure known fixed ID is present
    if not ids:
        ids.add("cacfhfpjipjnanbefddajafhgpmpibej")
    return sorted(list(ids))


def resolve_native_host_binary(explicit_path: Optional[str] = None, repo_root: Optional[str] = None) -> Optional[str]:
    """
    Locate the native messaging host binary (idm-native-host.exe on Windows, idm-native-host on Linux).
    Checks explicit path, next to running executable, parent directories (handles _internal/ in PyInstaller),
    repo paths, and PATH.
    """
    if explicit_path and os.path.exists(explicit_path):
        return os.path.abspath(explicit_path)

    base_name = "idm-native-host"
    exe_name = get_binary_name(base_name)

    # 1. Standard resolve_binary lookup (MEIPASS, argv[0], bin, PATH)
    found = resolve_binary(base_name)
    if found and os.path.isfile(found):
        return os.path.abspath(found)

    # 2. Check around sys.executable (essential for PyInstaller frozen app and pip venv)
    py_exec = sys.executable or ""
    if py_exec:
        app_dir = os.path.dirname(os.path.abspath(py_exec))
        candidates = [
            os.path.join(app_dir, exe_name),
            os.path.join(app_dir, "..", exe_name),
            os.path.join(app_dir, "Scripts", exe_name),
            os.path.join(app_dir, "bin", exe_name),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return os.path.abspath(c)

    # 3. Check around repo_root and _internal structure
    root = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_candidates = [
        os.path.join(root, exe_name),
        os.path.join(root, "..", exe_name),
        os.path.join(root, "dist", "pv-idm", exe_name),
        os.path.join(root, "dist", "idm-linux", exe_name),
    ]
    for c in repo_candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)

    # 4. Global fallback to PATH
    which_path = shutil.which(exe_name) or shutil.which(base_name)
    if which_path:
        return os.path.abspath(which_path)

    return None


def is_native_messaging_host_registered(expected_binary: Optional[str] = None) -> bool:
    """
    Check if the native messaging host is registered in the OS for standard browsers.
    Returns True if valid registration exists and points to an existing host binary.
    If expected_binary is specified, also validates that the registered binary matches expected_binary.
    """
    if is_windows():
        try:
            import winreg
            reg_paths = [
                r"Software\Google\Chrome\NativeMessagingHosts",
                r"Software\Microsoft\Edge\NativeMessagingHosts",
                r"Software\Mozilla\NativeMessagingHosts",
            ]
            for rp in reg_paths:
                full_key = f"{rp}\\{NATIVE_HOST_NAME}"
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, full_key) as k:
                        manifest_path = winreg.QueryValue(k, "")
                        if manifest_path and os.path.isfile(manifest_path):
                            with open(manifest_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            host_bin = data.get("path", "")
                            if host_bin and os.path.exists(host_bin):
                                if expected_binary:
                                    if os.path.normcase(os.path.abspath(host_bin)) != os.path.normcase(os.path.abspath(expected_binary)):
                                        return False
                                return True
                except Exception:
                    continue
            return False
        except Exception:
            return False
    else:
        home = os.path.expanduser("~")
        if is_macos():
            candidate_manifests = [
                os.path.join(home, "Library", "Application Support", "Google", "Chrome", "NativeMessagingHosts", f"{NATIVE_HOST_NAME}.json"),
                os.path.join(home, "Library", "Application Support", "Chromium", "NativeMessagingHosts", f"{NATIVE_HOST_NAME}.json"),
                os.path.join(home, "Library", "Application Support", "Mozilla", "NativeMessagingHosts", f"{NATIVE_HOST_NAME}.json"),
            ]
        else:
            candidate_manifests = [
                os.path.join(home, ".config", "google-chrome", "NativeMessagingHosts", f"{NATIVE_HOST_NAME}.json"),
                os.path.join(home, ".config", "chromium", "NativeMessagingHosts", f"{NATIVE_HOST_NAME}.json"),
                os.path.join(home, ".mozilla", "native-messaging-hosts", f"{NATIVE_HOST_NAME}.json"),
            ]
        for cm in candidate_manifests:
            if os.path.isfile(cm):
                try:
                    with open(cm, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    host_bin = data.get("path", "")
                    if host_bin and os.path.exists(host_bin):
                        if expected_binary:
                            if os.path.normcase(os.path.abspath(host_bin)) != os.path.normcase(os.path.abspath(expected_binary)):
                                return False
                        return True
                except Exception:
                    pass
        return False


class RegistrationResult(tuple):
    """Result of registering native messaging host, supporting tuple unpacking, bool check, and dict/attribute access."""
    def __new__(cls, success: bool, count: int, host_path: str, targets: Optional[List[str]] = None):
        return super().__new__(cls, (success, count, host_path))

    def __init__(self, success: bool, count: int, host_path: str, targets: Optional[List[str]] = None):
        self.success = bool(success)
        self.count = count
        self.host_path = host_path
        self.manifest_path = host_path
        self.targets = targets or [f"{count} browser locations configured"]

    def __bool__(self):
        return self.success

    def get(self, key, default=None):
        if key in ("status", "success"):
            return "ok" if self.success else "error"
        elif key == "count":
            return self.count
        elif key in ("manifest_path", "host_path"):
            return self.manifest_path
        elif key == "targets":
            return self.targets
        return default


class UnregistrationResult(tuple):
    """Result of unregistering native messaging host, supporting tuple unpacking, bool check, and dict/attribute access."""
    def __new__(cls, removed: bool, count: int = 0, targets: Optional[List[str]] = None):
        return super().__new__(cls, (removed, count))

    def __init__(self, removed: bool, count: int = 0, targets: Optional[List[str]] = None):
        self.removed = bool(removed)
        self.count = count
        self.targets = targets or ([f"{count} locations"] if count else [])

    def __bool__(self):
        return self.removed

    def get(self, key, default=None):
        if key in ("status", "success", "removed"):
            return self.removed
        elif key == "count":
            return self.count
        elif key == "targets":
            return self.targets
        return default


def register_native_messaging_host(
    binary_path: Optional[str] = None,
    custom_chrome_ids: Optional[List[str]] = None,
    additional_chrome_ids: Optional[List[str]] = None,
    repo_root: Optional[str] = None
) -> RegistrationResult:
    """
    Install and register native messaging host manifests for Chrome, Edge, Brave, and Firefox.
    Returns RegistrationResult which can be unpacked as (success, count, host_path) or accessed like a dict.
    """
    chrome_ids_list: List[str] = []
    if custom_chrome_ids:
        chrome_ids_list.extend(custom_chrome_ids)
    if additional_chrome_ids:
        chrome_ids_list.extend(additional_chrome_ids)

    root = repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resolved_binary = resolve_native_host_binary(binary_path, root)

    host_path = ""
    if resolved_binary:
        host_path = resolved_binary
    elif is_windows():
        # Fallback to permanent wrapper script on Windows
        base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        native_dir = os.path.join(base_dir, "pv-idm", "native-messaging-hosts")
        os.makedirs(native_dir, exist_ok=True)
        host_path = os.path.join(native_dir, "idm-native-host-wrapper.bat")
        py_exec = sys.executable or "python.exe"
        if py_exec.lower().endswith("pythonw.exe"):
            py_exec = py_exec[:-10] + "python.exe"
        script_content = f"""@echo off
setlocal
where idm-native-host.exe >nul 2>nul
if %ERRORLEVEL% equ 0 (
    idm-native-host.exe %*
    exit /b %ERRORLEVEL%
)
if exist "%~dp0idm-native-host.exe" (
    "%~dp0idm-native-host.exe" %*
    exit /b %ERRORLEVEL%
)
if exist "%~dp0..\\idm-native-host.exe" (
    "%~dp0..\\idm-native-host.exe" %*
    exit /b %ERRORLEVEL%
)
set "PYTHONPATH={root};%PYTHONPATH%"
"{py_exec}" -m idm_native_host.host %*
"""
        with open(host_path, "w", encoding="utf-8") as f:
            f.write(script_content)
    else:
        # Linux / POSIX shell wrapper
        host_path = os.path.join(root, "scripts", "idm-native-host-wrapper.sh")
        py_exec = sys.executable or "/usr/bin/python3"
        py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        script_content = f"""#!/bin/bash
export PYTHONPATH="/usr/lib/python3/dist-packages:/usr/local/lib/{py_ver}/dist-packages:/usr/local/lib/python3/dist-packages:{root}:$PYTHONPATH"
exec "{py_exec}" -m idm_native_host.host "$@"
"""
        os.makedirs(os.path.dirname(os.path.abspath(host_path)), exist_ok=True)
        with open(host_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        try:
            st = os.stat(host_path)
            os.chmod(host_path, st.st_mode | 0o755)
        except Exception:
            pass

    # Collect Chrome / Chromium extension IDs
    chrome_ids = get_default_chrome_extension_ids(root)
    if chrome_ids_list:
        for cid in chrome_ids_list:
            clean_id = (cid or "").strip()
            if clean_id and clean_id not in chrome_ids:
                chrome_ids.append(clean_id)

    env_id = os.environ.get("IDM_CHROME_EXTENSION_ID")
    if env_id and env_id.strip() not in chrome_ids:
        chrome_ids.append(env_id.strip())

    allowed_origins = [f"chrome-extension://{cid}/" for cid in chrome_ids]

    chrome_manifest = {
        "name": NATIVE_HOST_NAME,
        "description": "PV-IDM Browser Integration Native Messaging Host",
        "path": host_path,
        "type": "stdio",
        "allowed_origins": allowed_origins
    }

    firefox_manifest = {
        "name": NATIVE_HOST_NAME,
        "description": "PV-IDM Browser Integration Native Messaging Host",
        "path": host_path,
        "type": "stdio",
        "allowed_extensions": [
            "pv-idm@pv-idm.local",
            "idm-linux@idm-linux.local"
        ]
    }

    installed_count = 0

    if is_windows():
        try:
            import winreg
            base_dir = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
            manifests_dir = os.path.join(base_dir, "pv-idm", "native-messaging-hosts")
            os.makedirs(manifests_dir, exist_ok=True)

            chrome_manifest_file = os.path.join(manifests_dir, f"{NATIVE_HOST_NAME}.json")
            firefox_manifest_file = os.path.join(manifests_dir, f"{NATIVE_HOST_NAME}.firefox.json")

            with open(chrome_manifest_file, "w", encoding="utf-8") as f:
                json.dump(chrome_manifest, f, indent=2)
            with open(firefox_manifest_file, "w", encoding="utf-8") as f:
                json.dump(firefox_manifest, f, indent=2)

            target_names = []
            reg_paths_chrome = [
                ("Google Chrome", r"Software\Google\Chrome\NativeMessagingHosts"),
                ("Microsoft Edge", r"Software\Microsoft\Edge\NativeMessagingHosts"),
                ("Brave Browser", r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts"),
            ]
            for browser_name, rp in reg_paths_chrome:
                try:
                    full_key = f"{rp}\\{NATIVE_HOST_NAME}"
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, full_key) as k:
                        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, chrome_manifest_file)
                    installed_count += 1
                    target_names.append(f"{browser_name} (HKCU)")
                except Exception:
                    pass

            try:
                ff_key = f"Software\\Mozilla\\NativeMessagingHosts\\{NATIVE_HOST_NAME}"
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ff_key) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, firefox_manifest_file)
                installed_count += 1
                target_names.append("Mozilla Firefox (HKCU)")
            except Exception:
                pass

        except Exception:
            pass
    else:
        target_names = []
        home = os.path.expanduser("~")
        if is_macos():
            chromium_targets = [
                os.path.join(home, "Library", "Application Support", "Google", "Chrome", "NativeMessagingHosts"),
                os.path.join(home, "Library", "Application Support", "Chromium", "NativeMessagingHosts"),
                os.path.join(home, "Library", "Application Support", "BraveSoftware", "Brave-Browser", "NativeMessagingHosts"),
                os.path.join(home, "Library", "Application Support", "Microsoft Edge", "NativeMessagingHosts"),
            ]
            firefox_targets = [
                os.path.join(home, "Library", "Application Support", "Mozilla", "NativeMessagingHosts"),
            ]
        else:
            chromium_targets = [
                os.path.join(home, ".config", "google-chrome", "NativeMessagingHosts"),
                os.path.join(home, ".config", "chromium", "NativeMessagingHosts"),
                os.path.join(home, ".config", "BraveSoftware", "Brave-Browser", "NativeMessagingHosts"),
                os.path.join(home, ".config", "microsoft-edge", "NativeMessagingHosts"),
                os.path.join(home, ".config", "opera", "NativeMessagingHosts"),
                os.path.join(home, ".config", "vivaldi", "NativeMessagingHosts"),
            ]
            firefox_targets = [
                os.path.join(home, ".mozilla", "native-messaging-hosts"),
                os.path.join(home, ".librewolf", "native-messaging-hosts"),
            ]

        for target_dir in chromium_targets:
            try:
                os.makedirs(target_dir, exist_ok=True)
                manifest_file = os.path.join(target_dir, f"{NATIVE_HOST_NAME}.json")
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(chrome_manifest, f, indent=2)
                installed_count += 1
                target_names.append(manifest_file)
            except Exception:
                pass

        for target_dir in firefox_targets:
            try:
                os.makedirs(target_dir, exist_ok=True)
                manifest_file = os.path.join(target_dir, f"{NATIVE_HOST_NAME}.json")
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(firefox_manifest, f, indent=2)
                installed_count += 1
                target_names.append(manifest_file)
            except Exception:
                pass

    return RegistrationResult(installed_count > 0, installed_count, host_path, targets=target_names)


def unregister_native_messaging_host() -> UnregistrationResult:
    """Unregister and clean up native messaging host manifests and registry keys."""
    removed = False
    removed_targets = []
    if is_windows():
        try:
            import winreg
            reg_paths = [
                ("Google Chrome", r"Software\Google\Chrome\NativeMessagingHosts"),
                ("Microsoft Edge", r"Software\Microsoft\Edge\NativeMessagingHosts"),
                ("Brave Browser", r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts"),
                ("Mozilla Firefox", r"Software\Mozilla\NativeMessagingHosts"),
            ]
            for browser_name, rp in reg_paths:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{rp}\\{NATIVE_HOST_NAME}")
                    removed = True
                    removed_targets.append(f"{browser_name} (HKCU)")
                except Exception:
                    pass
        except Exception:
            pass
    else:
        home = os.path.expanduser("~")
        if is_macos():
            dirs = [
                os.path.join(home, "Library", "Application Support", "Google", "Chrome", "NativeMessagingHosts"),
                os.path.join(home, "Library", "Application Support", "Chromium", "NativeMessagingHosts"),
                os.path.join(home, "Library", "Application Support", "BraveSoftware", "Brave-Browser", "NativeMessagingHosts"),
                os.path.join(home, "Library", "Application Support", "Microsoft Edge", "NativeMessagingHosts"),
                os.path.join(home, "Library", "Application Support", "Mozilla", "NativeMessagingHosts"),
            ]
        else:
            dirs = [
                os.path.join(home, ".config", "google-chrome", "NativeMessagingHosts"),
                os.path.join(home, ".config", "chromium", "NativeMessagingHosts"),
                os.path.join(home, ".config", "BraveSoftware", "Brave-Browser", "NativeMessagingHosts"),
                os.path.join(home, ".config", "microsoft-edge", "NativeMessagingHosts"),
                os.path.join(home, ".config", "opera", "NativeMessagingHosts"),
                os.path.join(home, ".config", "vivaldi", "NativeMessagingHosts"),
                os.path.join(home, ".mozilla", "native-messaging-hosts"),
                os.path.join(home, ".librewolf", "native-messaging-hosts"),
            ]
        for d in dirs:
            mf = os.path.join(d, f"{NATIVE_HOST_NAME}.json")
            if os.path.exists(mf):
                try:
                    os.remove(mf)
                    removed = True
                    removed_targets.append(mf)
                except Exception:
                    pass
    return UnregistrationResult(removed, count=len(removed_targets), targets=removed_targets)
