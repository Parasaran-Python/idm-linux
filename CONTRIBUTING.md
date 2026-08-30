# Contributing to IDM Linux

Thank you for your interest in contributing to **IDM Linux**! This project is an open-source, feature-complete clone of Internet Download Manager designed natively for Linux desktop environments.

---

## 1. Development Setup

### Prerequisites
- Python 3.10+
- PyQt6
- `ffmpeg` (optional, for stream remuxing)

### Clone & Install
```bash
git clone https://github.com/your-username/idm-linux.git
cd idm-linux

# Test run without installation
PYTHONPATH=. python3 -m idm_gui.app

# Run test suite
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## 2. Architecture Overview

- **`idm_core/`**: High performance segmented download manager, dynamic chunk splitting allocator, HLS/DASH video stream assembler, SQLite database storage, speed throttler, and scheduler.
- **`idm_ipc/`**: Unix Domain Socket server and client implementing a 4-byte length-prefixed JSON protocol at `~/.config/idm-linux/idm.sock`.
- **`idm_native_host/`**: Standard stdio-based native messaging bridge connecting browser extensions to the local IDM IPC daemon.
- **`idm_gui/`**: PyQt6 desktop application featuring the category sidebar, downloads table, dynamic segment colored progress widget, and settings dialogs.
- **`idm_cli/`**: Command line interface tool (`idm add`, `idm list`, `idm pause`, `idm resume`, `idm queue`).
- **`extension/`**: Universal WebExtension (Manifest V3 for Chrome/Chromium/Brave/Edge and Manifest V2/V3 for Firefox) with download interceptor and floating video sniffer panel.

---

## 3. Running Tests

To run all unit and integration tests:
```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p "test_*.py"
```

---

## 4. Submitting Pull Requests

1. Fork the repository and create your feature branch: `git checkout -b feat/my-new-feature`
2. Ensure all tests pass: `python3 -m unittest discover -s tests`
3. Add new unit tests covering your changes in `tests/`
4. Commit with clear conventional commit messages (`feat: ...`, `fix: ...`, `docs: ...`)
5. Open a Pull Request!
