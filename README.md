# PV-IDM ⚡

<p align="center">
  <b>A Feature-Complete, High-Performance Internet Download Manager (IDM) Clone for Linux</b><br>
  <i>Dynamic Multi-Segment Downloading • Browser Download Interceptor • Floating Video Sniffer • Iconic Chunk Progress Visualizer • Scheduler & Queues</i>
</p>

<p align="center">
  <a href="https://github.com/Parasaran-Python/idm-linux/actions/workflows/ci.yml"><img src="https://github.com/Parasaran-Python/idm-linux/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a>
  <img src="https://img.shields.io/badge/Platform-Linux%20(X11%20%26%20Wayland)-blue" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.10+-brightgreen" alt="Python">
  <img src="https://img.shields.io/badge/GUI-PyQt6-blueviolet" alt="GUI">
  <img src="https://img.shields.io/badge/Browsers-Chrome%20%7C%20Firefox%20%7C%20Edge%20%7C%20Brave-orange" alt="Browsers">
  <img src="https://img.shields.io/badge/License-GPL--3.0-green" alt="License">
</p>

---

## 🌟 Overview

**PV-IDM** brings the beloved, high-speed downloading experience of Internet Download Manager to the Linux desktop. Engineered with a modular, lightweight Python core and native PyQt6 widgets, it features IDM's iconic dynamic segment re-allocation algorithm, seamless multi-browser integration, floating video grabber overlay, queue scheduler, and background daemon.

```
+-------------------------------------------------------------------------------+
|                             Web Browsers                                      |
|    Chrome / Brave / Edge / Chromium (MV3)  |  Firefox / Librewolf (MV2/MV3)    |
|  +-------------------------------------+  +--------------------------------+  |
|  | Download Interceptor (Headers/Auth) |  | Video Sniffer (Floating Bar)   |  |
|  +-------------------------------------+  +--------------------------------+  |
+---------------------------------------+---------------------------------------+
                                        | Native Messaging (stdio)
                                        v
+-------------------------------------------------------------------------------+
|                       idm-native-host (Native Messaging Host)                 |
|             Translates browser JSON messages to Unix Domain Socket IPC        |
+---------------------------------------+---------------------------------------+
                                        | Unix Domain Socket (~/.config/pv-idm/idm.sock)
                                        v
+-------------------------------------------------------------------------------+
|                          IDM Core Daemon / Service                            |
|  +-------------------------------------------------------------------------+  |
|  | IPC Server (Length-Prefixed JSON Protocol)                              |  |
|  +-------------------------------------------------------------------------+  |
|  | Download Engine & Orchestrator                                          |  |
|  |  * SegmentDownloader (HTTP/HTTPS/FTP Range Requests)                     |  |
|  |  * DynamicAllocator (Dynamic Sub-chunk splitting algorithm)             |  |
|  |  * StreamDownloader (HLS .m3u8 & DASH .mpd segment assembler)           |  |
|  |  * SpeedLimiter (Token-bucket per-task & global bandwidth throttling)   |  |
|  |  * StorageManager (Sparse file allocation, chunk merging, checksums)    |  |
|  |  * CategoryManager (Filetype rules: Compressed, Video, Music, Docs...)  |  |
|  |  * Queue & Scheduler Manager (Periodic start/stop, max concurrent jobs) |  |
|  |  * SQLite Database (~/.config/pv-idm/idm.db)                             |  |
|  +-------------------------------------------------------------------------+  |
+-------------------+---------------------------------------+-------------------+
                    ^                                       ^
                    | Local IPC                             | Local IPC
+-------------------+-------------------+   +---------------+-------------------+
|            PyQt6 Desktop GUI          |   |              CLI Tool             |
|  * Main Window & Toolbar              |   |  * idm add <url>                  |
|  * Dynamic Segment Visualizer         |   |  * idm list / pause / resume      |
|  * Download Info & Progress Dialogs   |   |  * idm queue start / stop         |
|  * Scheduler & Queue Dialog           |   +-----------------------------------+
|  * Options & Settings Dialog          |
|  * System Tray & Notifications        |
+---------------------------------------+
```

---

## ✨ Features

### 🚀 High-Speed Dynamic Download Engine
- **Dynamic Re-segmentation**: Splits files across up to 32 concurrent connections. When any connection finishes early, the engine dynamically splits the remaining byte range of the busiest connection in half to ensure 100% bandwidth saturation at all times.
- **Robust Pause & Resume**: Resumes interrupted or paused downloads from exact byte offsets without re-downloading completed chunks.
- **Speed Limiter**: Dynamic token-bucket bandwidth throttle slider (from 50 KB/s to Unlimited).
- **HLS & DASH Stream Capture**: Multi-threaded segment downloader for `.m3u8` and `.mpd` playlists with automatic `ffmpeg` lossless remuxing into `.mp4`.

### 🌐 Universal Browser Integration & Video Sniffer
- **Automatic Interception**: Intercepts file downloads from Chrome, Brave, Edge, Chromium, Vivaldi, Opera, and Firefox, preserving all cookies, session headers, User-Agent, and Referer.
- **Floating Video Grabber Panel**: Injects the classic "Download this video" button above HTML5 video/audio players, YouTube, and streaming media with quality/resolution dropdowns (1080p, 720p, 480p, MP3 audio).
- **Context Menus**: Right-click "Download with IDM" or "Download all links with IDM".

### 🖥 Authentic Desktop Interface (PyQt6)
- **Main Window**: Toolbar (Add URL, Resume, Stop, Stop All, Delete, Options, Scheduler, Start/Stop Queue), Category Tree sidebar (Compressed, Documents, Music, Programs, Video), and Sortable Downloads Table.
- **Iconic Download Progress Dialog**: Features the authentic IDM multi-segment progress bar with real-time color-coded connection blocks, live speed curve graph, and HTTP log console.
- **Download File Info Popup**: Shows URL, file size probe, category auto-detection, and destination path selector.
- **Scheduler & Queue Manager**: Automated time-based triggers (e.g. start at 02:00, stop at 06:00), concurrency limits, and post-completion actions (power off, suspend, notify).
- **System Tray**: Minimizes to Linux system tray with live speed tooltips and desktop notifications.

### ⌨ Powerful CLI Tool
- Full command-line control (`idm add`, `idm list`, `idm pause`, `idm resume`, `idm queue`).

---

## 📦 Installation

### 1. Prerequisites
Ensure Python 3.10+ and PyQt6 are installed on your distribution:

**Debian / Ubuntu / Linux Mint:**
```bash
sudo apt update
sudo apt install python3 python3-pyqt6 ffmpeg
```

**Arch Linux / Manjaro:**
```bash
sudo pacman -S python python-pyqt6 ffmpeg
```

**Fedora / RHEL:**
```bash
sudo dnf install python3 python3-pyqt6 ffmpeg
```

---

### 2. Quick One-Click Setup
Clone the repository and run the automated installer:

```bash
git clone https://github.com/your-username/pv-idm.git
cd pv-idm

# Run the installer script
./scripts/install.sh
```

This will:
1. Create executable wrappers in `~/.local/bin/pv-idm` and `~/.local/bin/pv-idm-gui` (with `idm`/`idm-gui` symlink aliases).
2. Install desktop launcher to `~/.local/share/applications/pv-idm.desktop`.
3. Register Native Messaging Host manifests for all installed browsers.

---

### 3. Load Browser Extension

#### For Chromium Browsers (Google Chrome, Brave, Edge, Chromium, Vivaldi):
1. Open your browser and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in upper-right corner).
3. Click **Load unpacked** and select the `pv-idm/extension` directory.

#### For Mozilla Firefox / Librewolf:
1. Navigate to `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on...** and select `pv-idm/extension/manifest.firefox.json` (or `manifest.json`).

---

## 🚀 Usage

### Launch Desktop GUI
```bash
pv-idm-gui
```
*(Or launch **PV-IDM** directly from your application launcher / desktop menu).*

---

### Command Line Interface (CLI)

> **Note:** Both `pv-idm` and the short alias `idm` (as well as `idm-linux`) are supported.

#### Add a new download:
```bash
pv-idm add "https://example.com/large_archive.zip"
```

#### Specify destination and connections:
```bash
pv-idm add "https://example.com/video.mp4" -o ~/Videos/movie.mp4 -c 16
```

#### Add to queue without starting immediately:
```bash
pv-idm add "https://example.com/backup.iso" --later
```

#### List all downloads:
```bash
pv-idm list
```

#### Pause / Resume / Delete:
```bash
pv-idm pause dl-8f92a1
pv-idm resume dl-8f92a1
pv-idm delete dl-8f92a1 --files
```

#### Manage Queues:
```bash
pv-idm queue start main
pv-idm queue stop main
```

#### Check Daemon Status:
```bash
pv-idm status
```

---

## ⚙ Configuration & Storage Paths

All persistent settings, state, and logs are stored according to XDG standards:
- **Configuration & Database**: `~/.config/pv-idm/idm.db`
- **IPC Socket**: `~/.config/pv-idm/idm.sock`
- **Temporary Segments**: `~/.config/pv-idm/temp/`
- **Default Downloads**: `~/Downloads/` (subdivided into `Compressed`, `Documents`, `Music`, `Programs`, `Video`)

---

## 🧪 Running the Test Suite

Run the full automated unit and integration test suite:
```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p "test_*.py"
```

---

## 🤝 Contributing

Contributions, feature requests, and bug reports are welcome! Please check [CONTRIBUTING.md](file:///run/media/parasaran/Dev/linux_dev/git/idm-linux/CONTRIBUTING.md) for development guidelines.

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. See the [LICENSE](file:///run/media/parasaran/Dev/linux_dev/git/idm-linux/LICENSE) file for details.
