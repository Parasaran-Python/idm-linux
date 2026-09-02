"""
Platform Abstraction Layer for IDM
Provides cross-platform paths, OS detection, binary resolution, and system actions.
Supports Linux, Windows, and macOS.
"""

import os
import shutil
import subprocess
import sys
from typing import Optional


def is_windows() -> bool:
    """Return True if running on Microsoft Windows."""
    return sys.platform.startswith("win32") or sys.platform.startswith("cygwin")


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
    """
    Return the base configuration and data directory.
    - Windows: %APPDATA%\\idm-linux (fallback to ~/.config/idm-linux)
    - Linux: ~/.config/idm-linux (or $XDG_CONFIG_HOME/idm-linux)
    - macOS: ~/Library/Application Support/idm-linux
    """
    if custom_dir:
        return os.path.abspath(custom_dir)

    if is_windows():
        appdata = os.environ.get("APPDATA")
        if appdata:
            return os.path.join(appdata, "idm-linux")
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            return os.path.join(localappdata, "idm-linux")
        return os.path.expanduser("~/.config/idm-linux")

    if is_macos():
        return os.path.expanduser("~/Library/Application Support/idm-linux")

    # Linux / FreeDesktop default
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return os.path.join(xdg_config, "idm-linux")
    return os.path.expanduser("~/.config/idm-linux")


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
    - Linux/macOS: ~/.config/idm-linux/idm.sock
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
    candidate = os.path.join(app_dir, exe_name)
    if os.path.isfile(candidate) and (is_windows() or os.access(candidate, os.X_OK)):
        return candidate
    candidate_bin = os.path.join(app_dir, "bin", exe_name)
    if os.path.isfile(candidate_bin) and (is_windows() or os.access(candidate_bin, os.X_OK)):
        return candidate_bin

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
                    ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                    check=False
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
            trash_dir = os.path.expanduser("~/.local/share/Trash/files")
            os.makedirs(trash_dir, exist_ok=True)
            dest = os.path.join(trash_dir, os.path.basename(abs_path))
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
    safe_title = (title or "IDM Linux").replace('"', '\\"')
    safe_msg = (message or "").replace('"', '\\"')

    # 1. Windows: Try windows-toasts library
    if is_windows():
        try:
            from windows_toasts import InteractableWindowsToaster, Toast, ToastDisplayImage
            toaster = InteractableWindowsToaster("IDM Linux", "IDMLinux.IDM.App.1.0")
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
