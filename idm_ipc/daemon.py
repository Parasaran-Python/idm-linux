"""
Background Daemon Service for IDM Linux
"""

import argparse
import os
import signal
import sys
import time
from idm_core.config import Config
from idm_core.engine import DownloadEngine
from idm_ipc.socket_server import IPCServer


class IDMDaemon:
    def __init__(self, config: Config):
        self.config = config
        self.engine = DownloadEngine(self.config)
        self.server = IPCServer(self.engine, self.config.socket_path)
        self._running = False

    def start(self):
        """Start background engine and IPC socket listener."""
        self._running = True
        self.server.start()
        print(f"[IDM Daemon] Running on {self.config.socket_path} (PID: {os.getpid()})")

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        while self._running:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                break

        self.stop()

    def stop(self):
        """Stop daemon and cleanup."""
        self._running = False
        print("[IDM Daemon] Stopping...")
        self.server.stop()
        self.engine.shutdown()
        print("[IDM Daemon] Stopped.")

    def _handle_signal(self, signum, frame):
        self._running = False


def main():
    parser = argparse.ArgumentParser(description="PV-IDM Background Daemon")
    parser.add_argument("--config-dir", help="Custom configuration directory")
    args = parser.parse_args()

    config = Config()
    if args.config_dir:
        config = Config(config_dir=args.config_dir)

    daemon = IDMDaemon(config)
    daemon.start()


if __name__ == "__main__":
    main()
