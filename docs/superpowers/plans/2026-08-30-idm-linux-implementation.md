# IDM Linux Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete open-source Internet Download Manager (IDM) clone for Linux featuring dynamic multi-segmented chunk downloading, browser download interception, floating video sniffer panel, PyQt6 desktop UI with dynamic segment progress visualizer, queue scheduler, CLI, and Native Messaging host.

**Architecture:** A modular Python 3 architecture split into `idm_core` (download engine, dynamic segment allocator, HLS/DASH stream capture, SQLite store), `idm_ipc` (Unix domain socket server & client), `idm_native_host` (stdio browser bridge), `idm_gui` (PyQt6 desktop interface with authentic IDM widgets and dialogs), `idm_cli` (command line manager), and `extension/` (Chrome MV3 + Firefox extension).

**Tech Stack:** Python 3.14 (`/run/media/parasaran/Dev/SDK/python/install/bin/python3`), PyQt6, SQLite3, standard library `urllib`/`http.client`/`asyncio`/`threading`/`socket`, `ffmpeg` (for media remuxing), JavaScript (WebExtensions API Manifest V3/V2).

**Spec:** [docs/superpowers/specs/2026-08-30-idm-linux-design.md](file:///run/media/parasaran/Dev/linux_dev/git/idm-linux/docs/superpowers/specs/2026-08-30-idm-linux-design.md)

## Global Constraints
- Python interpreter path: `/run/media/parasaran/Dev/SDK/python/install/bin/python3` (with `PYTHONPATH=/usr/lib/python3/dist-packages:/usr/local/lib/python3.14/dist-packages`).
- Zero external pip network requirements — rely on clean, robust standard library (`urllib.request`, `http.client`, `socket`, `sqlite3`, `threading`, `asyncio`) + PyQt6.
- Authentic IDM dynamic re-segmentation: splitting remaining byte ranges of slowest/largest active connections when workers complete.
- Cross-browser extension support: Chrome, Chromium, Brave, Edge, Opera, Vivaldi, Firefox.
- GPL-3.0 License and clean Git commit per task.

---

### Task 1: Project Scaffolding, Configuration & Database Schema

**Files:**
- Create: `pyproject.toml`
- Create: `idm_core/__init__.py`
- Create: `idm_core/config.py`
- Create: `idm_core/database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Produces: `Config` dataclass, `Database` class with methods `init_db()`, `add_download(download_data)`, `update_download(download_id, **kwargs)`, `get_download(download_id)`, `list_downloads(category=None, status=None, queue_id=None)`, `delete_download(download_id)`, `save_segments(download_id, segments)`, `get_segments(download_id)`, `update_segment(segment_id, **kwargs)`, `get_setting(key, default)`, `set_setting(key, value)`.

- [ ] **Step 1: Write the failing test for Database and Config**
Create `tests/test_database.py` with test cases verifying database initialization, download CRUD, segment tracking, and setting persistence in SQLite in-memory and file modes.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_database.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'idm_core'`

- [ ] **Step 3: Write minimal implementation**
Create `pyproject.toml`, `idm_core/__init__.py`, `idm_core/config.py` (paths, defaults, connection limits, category mappings), and `idm_core/database.py` implementing thread-safe SQLite operations.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_database.py`
Expected: PASS (all tests pass)

- [ ] **Step 5: Commit**
Run:
```bash
git add pyproject.toml idm_core/__init__.py idm_core/config.py idm_core/database.py tests/test_database.py
git commit -m "feat(core): initialize project config and database schema"
```

---

### Task 2: Storage Manager, Sparse File Allocator & Checksums

**Files:**
- Create: `idm_core/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `idm_core/config.py`
- Produces: `StorageManager` class with methods `prepare_download_file(filepath, total_bytes)`, `get_temp_segment_path(download_id, segment_idx)`, `write_segment_chunk(temp_path, offset, data)`, `merge_segments(download_id, segment_files, destination_path, total_bytes)`, `verify_checksum(filepath, expected_hash, algorithm="sha256")`, `cleanup_temp(download_id)`.

- [ ] **Step 1: Write the failing test for StorageManager**
Create `tests/test_storage.py` testing sparse file pre-allocation, chunk writing, segment merging with exact boundary validation, and checksum verification.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_storage.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'idm_core.storage'`

- [ ] **Step 3: Write minimal implementation**
Create `idm_core/storage.py` implementing robust atomic file allocation, buffered chunk writes, multi-segment file stitching, and SHA256/MD5 validation.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_storage.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_core/storage.py tests/test_storage.py
git commit -m "feat(core): implement storage manager with sparse allocation and segment merging"
```

---

### Task 3: Dynamic Segmentation Allocator & Speed Limiter

**Files:**
- Create: `idm_core/dynamic_allocator.py`
- Create: `idm_core/speed_limiter.py`
- Test: `tests/test_dynamic_allocator.py`
- Test: `tests/test_speed_limiter.py`

**Interfaces:**
- Produces:
  - `Segment` dataclass (`index`, `start_byte`, `current_byte`, `end_byte`, `status`, `worker_id`)
  - `DynamicAllocator` with methods `initial_partition(total_bytes, num_connections)`, `request_subchunk_split(active_segments, min_split_size=1048576)`, `update_progress(segment_index, bytes_downloaded)`, `is_complete()`, `get_segment_states()`
  - `SpeedLimiter` with methods `set_rate_limit(bytes_per_sec)`, `acquire(num_bytes)`

- [ ] **Step 1: Write failing tests for DynamicAllocator and SpeedLimiter**
Create `tests/test_dynamic_allocator.py` (testing initial partition, dynamic sub-chunk splitting when one worker finishes early, edge cases where remaining size is < min_split_size) and `tests/test_speed_limiter.py` (testing token-bucket bandwidth throttle).

- [ ] **Step 2: Run tests to verify they fail**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_dynamic_allocator.py tests/test_speed_limiter.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Create `idm_core/dynamic_allocator.py` with the IDM dynamic re-segmentation algorithm and `idm_core/speed_limiter.py` with token-bucket rate limiting.

- [ ] **Step 4: Run tests to verify they pass**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_dynamic_allocator.py tests/test_speed_limiter.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_core/dynamic_allocator.py idm_core/speed_limiter.py tests/test_dynamic_allocator.py tests/test_speed_limiter.py
git commit -m "feat(core): add dynamic segment allocator and token bucket speed limiter"
```

---

### Task 4: Multi-Segment HTTP/HTTPS Range Downloader

**Files:**
- Create: `idm_core/segment_downloader.py`
- Test: `tests/test_segment_downloader.py`

**Interfaces:**
- Consumes: `idm_core/storage.py`, `idm_core/dynamic_allocator.py`, `idm_core/speed_limiter.py`
- Produces: `SegmentDownloader` class with methods `probe_url(url, headers=None)`, `start()`, `pause()`, `resume()`, `cancel()`, callback events `on_progress(download_id, stats)`, `on_segment_update(download_id, segments)`, `on_complete(download_id, filepath)`, `on_error(download_id, error_msg)`.

- [ ] **Step 1: Write the failing test with a local mock HTTP Range server**
Create `tests/test_segment_downloader.py` using `http.server` supporting `Range: bytes=X-Y`, testing multi-connection downloads, dynamic segment allocation in real network transfer, pausing and resuming from byte offsets.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_segment_downloader.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Create `idm_core/segment_downloader.py` managing thread pools for range chunks, handling SSL, redirects, cookie/referer headers, fallbacks for non-range servers, and dynamic split triggers.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_segment_downloader.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_core/segment_downloader.py tests/test_segment_downloader.py
git commit -m "feat(core): implement multi-segment HTTP/HTTPS range downloader with dynamic re-allocation"
```

---

### Task 5: Media & Stream Downloader (HLS .m3u8, DASH .mpd, Video Sniffer)

**Files:**
- Create: `idm_core/stream_downloader.py`
- Create: `idm_core/category_manager.py`
- Test: `tests/test_stream_downloader.py`
- Test: `tests/test_category_manager.py`

**Interfaces:**
- Consumes: `idm_core/storage.py`, `idm_core/speed_limiter.py`
- Produces: `StreamDownloader` (parses HLS master/media playlists `.m3u8` and DASH manifests `.mpd`, concurrently downloads segments, muxes to `.mp4` using `ffmpeg` or direct byte concatenation), `CategoryManager` (categorizes by extension and MIME type into Video, Music, Compressed, Documents, Programs).

- [ ] **Step 1: Write failing tests for StreamDownloader and CategoryManager**
Create `tests/test_stream_downloader.py` (with mock HLS playlist and segment files) and `tests/test_category_manager.py`.

- [ ] **Step 2: Run tests to verify they fail**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_stream_downloader.py tests/test_category_manager.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Create `idm_core/category_manager.py` with extension mapping and `idm_core/stream_downloader.py` supporting HLS/DASH playlist parsing and concurrent chunk retrieval.

- [ ] **Step 4: Run tests to verify they pass**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_stream_downloader.py tests/test_category_manager.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_core/stream_downloader.py idm_core/category_manager.py tests/test_stream_downloader.py tests/test_category_manager.py
git commit -m "feat(core): add HLS/DASH stream downloader and category manager"
```

---

### Task 6: Central Download Engine, Queue & Scheduler

**Files:**
- Create: `idm_core/queue_manager.py`
- Create: `idm_core/scheduler.py`
- Create: `idm_core/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: `idm_core/database.py`, `idm_core/segment_downloader.py`, `idm_core/stream_downloader.py`, `idm_core/category_manager.py`
- Produces: `DownloadEngine` with methods `add_download()`, `pause_download()`, `resume_download()`, `stop_all()`, `delete_download()`, `start_queue()`, `stop_queue()`, `set_speed_limit()`, `get_stats()`, and event callbacks.

- [ ] **Step 1: Write failing tests for Engine and Scheduler**
Create `tests/test_engine.py` testing end-to-end task queueing, concurrency limiting, scheduler triggers, and state persistence.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_engine.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Create `idm_core/queue_manager.py`, `idm_core/scheduler.py`, and `idm_core/engine.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_engine.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_core/queue_manager.py idm_core/scheduler.py idm_core/engine.py tests/test_engine.py
git commit -m "feat(core): implement download engine orchestrator, queue manager, and scheduler"
```

---

### Task 7: IPC Protocol, Unix Domain Socket Server & Daemon

**Files:**
- Create: `idm_ipc/__init__.py`
- Create: `idm_ipc/protocol.py`
- Create: `idm_ipc/socket_server.py`
- Create: `idm_ipc/socket_client.py`
- Create: `idm_ipc/daemon.py`
- Test: `tests/test_ipc.py`

**Interfaces:**
- Produces: `IPCServer` (Unix domain socket listener with framing), `IPCClient` (sync & async request sender), `IDMDaemon` (service runner).

- [ ] **Step 1: Write failing test for IPC framing and communication**
Create `tests/test_ipc.py` testing connection, message framing, JSON request dispatching, error handling, and broadcast events.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_ipc.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Create `idm_ipc/` modules implementing robust 4-byte length-prefixed JSON protocol over `~/.config/idm-linux/idm.sock`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_ipc.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_ipc/ tests/test_ipc.py
git commit -m "feat(ipc): add unix domain socket IPC server, client, and daemon"
```

---

### Task 8: Native Messaging Host & Browser Manifest Installer

**Files:**
- Create: `idm_native_host/__init__.py`
- Create: `idm_native_host/host.py`
- Create: `scripts/install_native_host.py`
- Test: `tests/test_native_host.py`

**Interfaces:**
- Produces: Native messaging binary reading/writing 32-bit length-prefixed JSON on stdin/stdout, and `install_native_host.py` configuring manifests for Chrome, Chromium, Brave, Edge, and Firefox.

- [ ] **Step 1: Write failing test for native messaging host**
Create `tests/test_native_host.py` testing stdin/stdout binary framing and IPC forwarding.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_native_host.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Create `idm_native_host/host.py` and `scripts/install_native_host.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_native_host.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_native_host/ scripts/install_native_host.py tests/test_native_host.py
git commit -m "feat(native-host): create browser native messaging host and multi-browser installer"
```

---

### Task 9: Universal Browser Extension (Chrome/Edge/Brave MV3 & Firefox MV2/MV3)

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/manifest.firefox.json`
- Create: `extension/background/service_worker.js`
- Create: `extension/background/download_interceptor.js`
- Create: `extension/content/video_sniffer.js`
- Create: `extension/content/sniffer.css`
- Create: `extension/popup/popup.html`
- Create: `extension/popup/popup.js`
- Create: `extension/popup/popup.css`
- Create: `extension/icons/icon16.png`, `extension/icons/icon48.png`, `extension/icons/icon128.png`

**Interfaces:**
- Produces: Complete browser extension package ready to load in Chrome/Firefox with download interception, floating video capture button, context menus, and native host communication.

- [ ] **Step 1: Create extension manifest and background service worker**
Write `extension/manifest.json` (MV3) and `manifest.firefox.json` with permissions (`downloads`, `webRequest`, `nativeMessaging`, `contextMenus`, `storage`).

- [ ] **Step 2: Implement download interceptor**
Write `extension/background/download_interceptor.js` capturing browser downloads and extracting cookies/headers.

- [ ] **Step 3: Implement floating video sniffer panel**
Write `extension/content/video_sniffer.js` and `sniffer.css` detecting video/audio elements and rendering the floating IDM download panel with format options.

- [ ] **Step 4: Implement popup UI & icon assets**
Write `extension/popup/` UI for toggling interception and monitoring connection status, and generate clean icons.

- [ ] **Step 5: Commit**
Run:
```bash
git add extension/
git commit -m "feat(extension): build universal browser extension with download interceptor and video sniffer"
```

---

### Task 10: PyQt6 Desktop GUI - Theme, Dynamic Segment Visualizer & Main Widgets

**Files:**
- Create: `idm_gui/__init__.py`
- Create: `idm_gui/styles.py`
- Create: `idm_gui/widgets/__init__.py`
- Create: `idm_gui/widgets/segment_visualizer.py`
- Create: `idm_gui/widgets/category_tree.py`
- Create: `idm_gui/widgets/download_table.py`
- Create: `idm_gui/widgets/speed_graph.py`
- Test: `tests/test_gui_widgets.py`

**Interfaces:**
- Produces: `SegmentVisualizerWidget` (custom painted colored block segment progress bar), `CategoryTreeWidget`, `DownloadTableWidget`, `SpeedGraphWidget`, `IDMStyle` (IDM classic + modern light/dark palettes).

- [ ] **Step 1: Write unit tests for GUI widgets**
Create `tests/test_gui_widgets.py` verifying widget creation, segment visualizer data updating, and category filtering in headless offscreen Qt environment.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. QT_QPA_PLATFORM=offscreen /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_gui_widgets.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Implement `idm_gui/styles.py`, `segment_visualizer.py` with custom `QPainter` drawing real-time connection blocks, `category_tree.py`, `download_table.py`, and `speed_graph.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. QT_QPA_PLATFORM=offscreen /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_gui_widgets.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_gui/styles.py idm_gui/widgets/ tests/test_gui_widgets.py
git commit -m "feat(gui): implement dynamic segment visualizer, category tree, and download table widgets"
```

---

### Task 11: PyQt6 Desktop GUI - Dialogs

**Files:**
- Create: `idm_gui/dialogs/__init__.py`
- Create: `idm_gui/dialogs/download_info_dialog.py`
- Create: `idm_gui/dialogs/download_progress_dialog.py`
- Create: `idm_gui/dialogs/queue_scheduler_dialog.py`
- Create: `idm_gui/dialogs/options_dialog.py`
- Create: `idm_gui/dialogs/batch_download_dialog.py`
- Create: `idm_gui/dialogs/video_download_dialog.py`
- Test: `tests/test_gui_dialogs.py`

**Interfaces:**
- Produces: `DownloadInfoDialog` (intercept/add popup), `DownloadProgressDialog` (active download popup with segment bar, speed graph, logs), `QueueSchedulerDialog`, `OptionsDialog`, `BatchDownloadDialog`, `VideoDownloadDialog`.

- [ ] **Step 1: Write unit tests for dialogs**
Create `tests/test_gui_dialogs.py` testing instantiation, data binding, and action signals.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. QT_QPA_PLATFORM=offscreen /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_gui_dialogs.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Create all dialog classes under `idm_gui/dialogs/`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. QT_QPA_PLATFORM=offscreen /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_gui_dialogs.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_gui/dialogs/ tests/test_gui_dialogs.py
git commit -m "feat(gui): build IDM download info, progress, queue scheduler, and options dialogs"
```

---

### Task 12: PyQt6 Desktop GUI - Main Window, System Tray & Application Runner

**Files:**
- Create: `idm_gui/main_window.py`
- Create: `idm_gui/tray.py`
- Create: `idm_gui/app.py`
- Test: `tests/test_gui_main.py`

**Interfaces:**
- Produces: `MainWindow` (complete IDM main interface with menu bar, toolbar, splitters, status bar, IPC integration), `SystemTray` (tray icon, menu, notifications), `IDMApplication` (app lifecycle).

- [ ] **Step 1: Write test for MainWindow and App lifecycle**
Create `tests/test_gui_main.py` verifying window creation, menu triggers, and IPC signal connections.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. QT_QPA_PLATFORM=offscreen /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_gui_main.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Create `idm_gui/main_window.py`, `idm_gui/tray.py`, and `idm_gui/app.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. QT_QPA_PLATFORM=offscreen /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_gui_main.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_gui/main_window.py idm_gui/tray.py idm_gui/app.py tests/test_gui_main.py
git commit -m "feat(gui): complete IDM main window, toolbar, system tray, and app launcher"
```

---

### Task 13: CLI Tool & Linux Desktop Integration

**Files:**
- Create: `idm_cli/__init__.py`
- Create: `idm_cli/cli.py`
- Create: `scripts/idm-linux.desktop`
- Create: `scripts/install.sh`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `idm` CLI executable supporting `add`, `list`, `pause`, `resume`, `stop`, `delete`, `queue`, `status`, desktop entry file, and installation script.

- [ ] **Step 1: Write tests for CLI commands**
Create `tests/test_cli.py` testing argument parsing and IPC command dispatch.

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_cli.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Create `idm_cli/cli.py`, `scripts/idm-linux.desktop`, and `scripts/install.sh`.

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_cli.py`
Expected: PASS

- [ ] **Step 5: Commit**
Run:
```bash
git add idm_cli/ scripts/ tests/test_cli.py
git commit -m "feat(cli): add command line tool, desktop entry, and installer scripts"
```

---

### Task 14: End-to-End System Integration Tests & Verification

**Files:**
- Create: `tests/test_integration_e2e.py`

**Interfaces:**
- Consumes: All `idm_core`, `idm_ipc`, `idm_native_host`, `idm_cli` components.
- Validates: Full flow from native messaging JSON interception -> IPC socket dispatch -> multi-segmented download with dynamic chunk allocation -> pause/resume recovery -> file merge & SHA256 verification -> CLI and GUI status update.

- [ ] **Step 1: Write comprehensive end-to-end integration test suite**
Create `tests/test_integration_e2e.py` testing the full pipeline against an automated HTTP range test server with slow/flaky connection simulations.

- [ ] **Step 2: Run end-to-end integration test suite**
Run: `PYTHONPATH=/usr/lib/python3/dist-packages:. /run/media/parasaran/Dev/SDK/python/install/bin/python3 -m unittest tests/test_integration_e2e.py`
Expected: PASS

- [ ] **Step 3: Commit**
Run:
```bash
git add tests/test_integration_e2e.py
git commit -m "test(e2e): add complete end-to-end system integration tests"
```

---

### Task 15: Open Source Assets, Documentation & README

**Files:**
- Create: `README.md`
- Create: `LICENSE` (GPL-3.0)
- Create: `CONTRIBUTING.md`

**Interfaces:**
- Produces: High quality open-source repository documentation, architecture diagrams, installation instructions for Debian/Ubuntu, Arch, Fedora, openSUSE, browser loading guides, keyboard shortcuts, and CLI reference.

- [ ] **Step 1: Write LICENSE, CONTRIBUTING.md, and detailed README.md**
Write comprehensive documentation with ASCII architecture diagrams, feature breakdown, setup commands, and browser extension installation guides.

- [ ] **Step 2: Commit**
Run:
```bash
git add README.md LICENSE CONTRIBUTING.md
git commit -m "docs: add open source documentation, license, and comprehensive user guide"
```
