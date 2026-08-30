# IDM Linux - Complete Architecture & Technical Design Specification

**Date:** 2026-08-30  
**Project:** IDM Linux (Internet Download Manager for Linux)  
**Status:** Approved / In Design  
**License:** GNU General Public License v3.0 (GPL-3.0)  

---

## 1. Executive Summary

IDM Linux is an open-source, feature-complete clone of the Internet Download Manager (IDM) built for Linux desktop environments (X11 & Wayland). It replicates IDM's iconic look, feel, and performance characteristics, featuring:
1. **Dynamic Multi-Segment Download Engine**: Dynamically splits and re-allocates chunks across up to 32 concurrent connections to maximize bandwidth utilization.
2. **Browser Download Interception & Media Sniffer**: Extension for Chromium (Chrome, Brave, Edge, Opera, Vivaldi) and Firefox with Native Messaging IPC, automatically catching downloads and injecting the floating "Download this video" panel on web videos (HTML5, HLS `.m3u8`, DASH `.mpd`, YouTube/streaming platforms).
3. **Authentic Desktop GUI (PyQt6)**: Classic IDM interface featuring the category tree sidebar, detailed download table, **dynamic segment connection visualizer** (colored chunk block progress bar), live speed graph, queue manager, and scheduler.
4. **Resilient Daemon & CLI**: Unix Domain Socket IPC allowing background downloading, seamless browser handoff, and full CLI control (`idm add`, `idm list`, `idm pause`, etc.).

---

## 2. System Architecture

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
                                        | Unix Domain Socket (~/.config/idm-linux/idm.sock)
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
|  |  * SQLite Database (~/.config/idm-linux/idm.db)                         |  |
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

## 3. Core Engine Specifications (`idm_core`)

### 3.1. Dynamic Segmentation Algorithm (`dynamic_allocator.py`)
Standard downloaders split a file into $N$ static parts. If one server connection is slow or finishes early, the connection sits idle. IDM's secret is **Dynamic Re-segmentation**:
1. When a task starts with $N$ connections (e.g. 8), the file of size $S$ is divided into $N$ equal chunks: $[0, \frac{S}{N}), [\frac{S}{N}, \frac{2S}{N}), \dots$.
2. Each worker pulls data via HTTP `Range: bytes=start-end`.
3. When any worker $W_i$ completes its chunk, the engine inspects all active workers and finds the worker $W_{max}$ with the largest remaining byte range $\Delta = \text{end} - \text{current\_pos}$.
4. If $\Delta \ge \text{MIN\_SPLIT\_SIZE}$ (default: 1 MB):
   - $W_{max}$'s boundary is truncated to $\text{new\_end} = \text{current\_pos} + \lfloor \Delta / 2 \rfloor$.
   - Idle worker $W_i$ is immediately assigned $[\text{new\_end} + 1, \text{end}]$.
5. This guarantees that all $N$ connections remain saturated at 100% bandwidth until the last megabyte of the file.

### 3.2. Resume and Crash Recovery
- Every segment's active state (`start_byte`, `current_byte`, `end_byte`, `status`, `temp_path`) is continually recorded in SQLite.
- Upon pause, network drop, or app restart:
  - If server responded with `Accept-Ranges: bytes`, the engine resumes from `current_byte`.
  - Temporary segment files are kept in `~/.config/idm-linux/temp/<download_id>/` and merged into the destination file via fast zero-copy or sequential block copying upon 100% completion.

### 3.3. Streaming & Media Downloader (`stream_downloader.py`)
- For live or VoD HLS (`.m3u8`) and DASH (`.mpd`):
  - Fetches manifest, extracts audio/video playlists and individual segment URLs (`.ts` or `.m4s`).
  - Downloads segments concurrently using the worker pool with retry logic.
  - Automatically stitches or remuxes into clean MP4/MKV using native stream assembly or `ffmpeg` if available.
- YouTube / Social Media sniffing:
  - Captures direct video URLs or extracts stream formats preserving browser cookies and User-Agent.

### 3.4. Database Schema (`database.py`)
SQLite database at `~/.config/idm-linux/idm.db`:
- `downloads`: `id`, `url`, `filename`, `save_path`, `total_bytes`, `downloaded_bytes`, `status` (queued, downloading, paused, completed, error), `category`, `connections_count`, `speed_limit`, `created_at`, `completed_at`, `headers_json`, `error_msg`, `queue_id`.
- `segments`: `id`, `download_id`, `segment_index`, `start_byte`, `current_byte`, `end_byte`, `status`, `temp_file`.
- `queues`: `id`, `name`, `max_concurrent`, `is_active`, `start_time`, `stop_time`, `post_action` (none, shutdown, sleep).
- `settings`: Key-value configuration table (default download path, categories, max connections, speed cap, filetype intercept list, proxy).

---

## 4. IPC & Native Messaging Protocol (`idm_ipc` & `idm_native_host`)

### 4.1. Unix Domain Socket Server
- Socket Path: `~/.config/idm-linux/idm.sock`
- Framing: 4-byte big-endian unsigned integer (message length) followed by UTF-8 encoded JSON payload.

### 4.2. IPC Command Protocol
```json
// Add download request
{
  "action": "add_download",
  "url": "https://example.com/file.zip",
  "filename": "file.zip",
  "save_path": "/home/user/Downloads",
  "headers": {
    "User-Agent": "...",
    "Cookie": "...",
    "Referer": "..."
  },
  "category": "Compressed",
  "start_immediately": true,
  "queue_id": null
}

// Response
{
  "status": "ok",
  "download_id": "d-8f92a1",
  "file_size": 104857600
}
```

### 4.3. Native Messaging Host (`idm-native-host`)
- Reads standard 32-bit little-endian length-prefixed JSON from browser extension stdio.
- Bridges the message to `~/.config/idm-linux/idm.sock`.
- If the IDM daemon/GUI is not running, it launches `idm-gui --minimized` or the background daemon automatically.

---

## 5. Desktop GUI (`idm_gui` with PyQt6)

### 5.1. Main Window Layout
1. **Menu Bar**: Tasks, File, Downloads, View, Queue, Options, Help.
2. **Toolbar**:
   - `Add URL` (Plus icon)
   - `Resume` (Play icon)
   - `Stop` (Pause icon)
   - `Stop All` (Stop all icon)
   - `Delete` (Trash icon)
   - `Delete Completed` (Clean icon)
   - `Options` (Gear icon)
   - `Scheduler` (Clock icon)
   - `Start Queue` / `Stop Queue`
3. **Category Tree Sidebar**:
   - All Downloads (Total count)
   - Unfinished
   - Finished
   - Queues (Main Queue, Custom Queues)
   - Categories:
     - Compressed (`.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.xz`, `.iso`)
     - Documents (`.pdf`, `.doc`, `.docx`, `.epub`, `.txt`, `.xls`)
     - Music (`.mp3`, `.flac`, `.aac`, `.wav`, `.ogg`, `.m4a`)
     - Programs (`.exe`, `.deb`, `.rpm`, `.AppImage`, `.sh`, `.bin`, `.pkg`)
     - Video (`.mp4`, `.mkv`, `.avi`, `.webm`, `.flv`, `.mov`, `.m3u8`)
4. **Downloads Table**:
   - Columns: File Name, Size, Status, Progress (Visual bar + %), Transfer Rate, Time Left, Date Added, Category, URL.
   - Context Menu: Open File, Open Directory, Resume, Pause, Stop, Redownload, Delete (From list / From disk), Move to Queue, Properties.

### 5.2. Download Progress Dialog (IDM Iconic Window)
- **Top Section**: URL, Status, File Size, Downloaded Size, Transfer Rate, Time Left, Resume Capability.
- **Dynamic Segment Visualizer Widget**:
  - Displays a custom rendered multi-segment progress bar.
  - Divided into 1 to 32 discrete color blocks corresponding to active connections.
  - As each connection downloads bytes, its segment bar fills up in real time with distinct colors, perfectly mimicking IDM's visual progress feedback.
- **Speed Limiter Slider**: Allows dynamic throttle adjustment (e.g. 50 KB/s to Unlimited) on the fly.
- **Tabs**:
  - `Download Status`: General stats and segment breakdown.
  - `Speed Graph`: Real-time transfer rate over time.
  - `Log`: Live HTTP request/response headers, chunk handoffs, retry events.

### 5.3. Download Info Dialog (Interception Popup)
- Pops up when a download is intercepted or added.
- Shows URL, inferred filename, auto-detected category, destination path, and file size probed via `HEAD`.
- Buttons: "Download Now", "Download Later", "Cancel", "Remember this path for category".

### 5.4. Queue & Scheduler Dialog
- Multiple queue management (create, delete, reorder downloads).
- Scheduled start time, stop time, days of week.
- Concurrency limit (1 to 10 files at once).
- Post-download triggers: Show notification, play sound, shut down computer, suspend.

---

## 6. Universal Browser Extension (`extension/`)

### 6.1. Manifest V3 & V2 Compatibility
- Supports Google Chrome, Chromium, Brave, Microsoft Edge, Opera, Vivaldi, and Mozilla Firefox.

### 6.2. Download Interceptor (`service_worker.js` / `download_interceptor.js`)
- Listens to `chrome.downloads.onDeterminingFilename` and `chrome.webRequest.onHeadersReceived`.
- Filters out non-downloadable assets (HTML, scripts, stylesheets).
- When a downloadable extension or MIME type is detected:
  - Pauses/cancels native browser download.
  - Extracts full request context: Target URL, Cookies, User-Agent, Referer, Request Headers.
  - Passes payload to `idm-native-host` for immediate IDM pickup.

### 6.3. Video Sniffer & Floating Bar (`video_sniffer.js`)
- Monitors DOM for `<video>`, `<audio>`, iframe video players, and network media requests (MP4, WebM, HLS `.m3u8`, DASH `.mpd`).
- Injects a sleek floating "Download this video" button in the upper-right corner of the video player.
- Hovering/clicking reveals a dropdown menu listing available formats, resolutions (1080p, 720p, 480p, Audio MP3), and file sizes.
- Clicking a format instantly sends the media stream to IDM.

---

## 7. CLI Interface (`idm_cli`)

Commands:
- `idm add <url> [-o <output>] [-c <connections>] [--category <cat>] [--later]`
- `idm list [--status active|queued|completed|all]`
- `idm pause <download_id>`
- `idm resume <download_id>`
- `idm stop <download_id>`
- `idm delete <download_id> [--files]`
- `idm queue start [queue_name]`
- `idm queue stop [queue_name]`
- `idm status`

---

## 8. Open Source & Installation Setup

- `install_native_host.py`: Auto-detects installed browsers on Linux and creates the native messaging manifest in:
  - `~/.config/google-chrome/NativeMessagingHosts/`
  - `~/.config/chromium/NativeMessagingHosts/`
  - `~/.config/BraveSoftware/Brave-Browser/NativeMessagingHosts/`
  - `~/.config/microsoft-edge/NativeMessagingHosts/`
  - `~/.mozilla/native-messaging-hosts/`
- `idm-linux.desktop`: XDG desktop entry for application menus and autostart.
- `pyproject.toml` & `setup.py`: Standard Python packaging.
- GPL-3.0 License.

---

## 9. Verification & Testing Strategy

- **Unit Tests**:
  - `test_dynamic_allocator.py`: Chunk splitting under various connection completions, boundary conditions, edge cases (file size < 1MB, non-resumable servers).
  - `test_storage.py`: Sparse file creation, segment merging, checksum validation.
  - `test_speed_limiter.py`: Token bucket rate limiting accuracy.
  - `test_database.py`: CRUD operations, migration, transaction safety.
  - `test_ipc_protocol.py`: Message framing, serialization, error recovery.
- **Integration Tests**:
  - Local HTTP range test server simulating slow chunks, dropped connections, and resume verification.
  - Native messaging stdio framing tests.
  - End-to-end download verification comparing downloaded files with upstream SHA-256 hashes.
