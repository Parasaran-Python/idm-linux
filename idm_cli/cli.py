"""
Command-Line Interface for IDM Linux
Provides full terminal control over downloads, queues, and background daemon.
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Optional
from idm_core.formatters import format_bytes, format_speed, format_time
from idm_ipc.socket_client import IPCClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idm",
        description="IDM Linux - Internet Download Manager Command Line Tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # 1. Add
    add_parser = subparsers.add_parser("add", help="Add a new download URL")
    add_parser.add_argument("url", help="Download URL")
    add_parser.add_argument("-o", "--output", help="Destination file path")
    add_parser.add_argument("-c", "--connections", type=int, default=8, help="Number of concurrent segments (1-32)")
    add_parser.add_argument("--category", help="Category name (Compressed, Video, Music, Documents, Programs)")
    add_parser.add_argument("--later", action="store_true", help="Add to queue without starting immediately")

    # 2. List
    list_parser = subparsers.add_parser("list", help="List downloads")
    list_parser.add_argument("--category", help="Filter by category")
    list_parser.add_argument("--status", help="Filter by status (downloading, paused, completed, queued, error)")
    list_parser.add_argument("--search", help="Search keyword")

    # 3. Pause
    pause_parser = subparsers.add_parser("pause", help="Pause an active download")
    pause_parser.add_argument("download_id", help="Download ID (e.g. dl-8f92a1)")

    # 4. Resume
    resume_parser = subparsers.add_parser("resume", help="Resume a paused download")
    resume_parser.add_argument("download_id", help="Download ID")

    # 5. Stop
    stop_parser = subparsers.add_parser("stop", help="Stop an active download")
    stop_parser.add_argument("download_id", help="Download ID")

    # 6. Delete
    del_parser = subparsers.add_parser("delete", help="Delete a download")
    del_parser.add_argument("download_id", help="Download ID")
    del_parser.add_argument("--files", action="store_true", help="Also delete downloaded file from disk")

    # 7. Queue
    q_parser = subparsers.add_parser("queue", help="Manage download queues")
    q_parser.add_argument("action", choices=["start", "stop", "status"], help="Queue action")
    q_parser.add_argument("name", nargs="?", default="main", help="Queue name (default: main)")

    # 8. Status
    subparsers.add_parser("status", help="Check IDM daemon and download status")

    # 9. Native Host / Browser Registration
    browser_parser = subparsers.add_parser(
        "install-native-host",
        aliases=["register-browser"],
        help="Register browser native messaging host for Chrome, Edge, and Firefox",
    )
    browser_parser.add_argument(
        "-b", "--binary-path",
        help="Explicit path to idm-native-host executable",
    )
    browser_parser.add_argument(
        "--chrome-id",
        action="append",
        dest="chrome_ids",
        help="Additional Chrome/Chromium extension ID to allow",
    )
    browser_parser.add_argument(
        "-u", "--uninstall",
        action="store_true",
        help="Unregister browser native messaging host",
    )

    return parser


def run_cli_command(args: argparse.Namespace, client: Optional[IPCClient] = None) -> int:
    ipc = client or IPCClient()

    if not args.command or args.command == "status":
        if not ipc.is_server_running():
            print("IDM Linux Status: Offline (Daemon is not currently running)")
            return 1
        res = ipc.ping()
        print(f"IDM Linux Status: Online ({res.get('app', 'IDM Linux')} v{res.get('version', '1.0.0')})")
        return 0

    if args.command == "add":
        payload = {
            "action": "add_download",
            "url": args.url,
            "save_path": args.output,
            "connections": args.connections,
            "category": args.category,
            "start_immediately": not args.later
        }
        res = ipc.send_request(payload)
        if res.get("status") == "ok":
            dl_id = res.get("download_id")
            action_str = "added (queued)" if args.later else "started"
            print(f"[OK] Download {action_str} successfully! ID: {dl_id}")
            return 0
        else:
            print(f"[Error] Failed to add download: {res.get('error')}")
            return 1

    elif args.command == "list":
        payload = {
            "action": "list_downloads",
            "category": args.category,
            "status": args.status,
            "search": args.search
        }
        res = ipc.send_request(payload)
        if res.get("status") == "ok":
            dls = res.get("downloads", [])
            if not dls:
                print("No downloads found.")
                return 0
            
            print(f"{'ID':<16} {'STATUS':<12} {'SIZE':<12} {'PROGRESS':<10} {'SPEED':<12} {'FILE NAME'}")
            print("-" * 80)
            for d in dls:
                dl_id = d.get("id", "")
                status = d.get("status", "").capitalize()
                total = d.get("total_bytes", 0)
                downloaded = d.get("downloaded_bytes", 0)
                pct = f"{int(downloaded / total * 100)}%" if total > 0 else "0%"
                speed = format_speed(d.get("speed", 0)) if status.lower() == "downloading" else "--"
                fname = d.get("filename", "")
                print(f"{dl_id:<16} {status:<12} {format_bytes(total):<12} {pct:<10} {speed:<12} {fname}")
            return 0
        else:
            print(f"[Error] Failed to list downloads: {res.get('error')}")
            return 1

    elif args.command == "pause" or args.command == "stop":
        res = ipc.send_request({"action": "pause_download", "download_id": args.download_id})
        if res.get("status") == "ok":
            print(f"[OK] Paused download {args.download_id}")
            return 0
        print(f"[Error] {res.get('error')}")
        return 1

    elif args.command == "resume":
        res = ipc.send_request({"action": "resume_download", "download_id": args.download_id})
        if res.get("status") == "ok":
            print(f"[OK] Resumed download {args.download_id}")
            return 0
        print(f"[Error] {res.get('error')}")
        return 1

    elif args.command == "delete":
        res = ipc.send_request({
            "action": "delete_download",
            "download_id": args.download_id,
            "delete_files": args.files
        })
        if res.get("status") == "ok":
            print(f"[OK] Deleted download {args.download_id}")
            return 0
        print(f"[Error] {res.get('error')}")
        return 1

    elif args.command == "queue":
        action = "start_queue" if args.action == "start" else "stop_queue"
        res = ipc.send_request({"action": action, "queue_id": args.name})
        if res.get("status") == "ok":
            print(f"[OK] Queue '{args.name}' {args.action}ed.")
            return 0
        print(f"[Error] {res.get('error')}")
        return 1

    elif args.command in ["install-native-host", "register-browser"]:
        from idm_core.platform import register_native_messaging_host, unregister_native_messaging_host
        if getattr(args, "uninstall", False):
            res = unregister_native_messaging_host()
            print(f"[OK] Native messaging host unregistered from {len(res.get('targets', []))} targets.")
            return 0
        else:
            try:
                res = register_native_messaging_host(
                    binary_path=getattr(args, "binary_path", None),
                    additional_chrome_ids=getattr(args, "chrome_ids", None),
                )
                print("[OK] Native messaging host registered successfully!")
                print(f"Manifest: {res.get('manifest_path')}")
                for t in res.get("targets", []):
                    print(f" - {t}")
                return 0
            except Exception as e:
                print(f"[Error] Failed to register native messaging host: {e}")
                return 1

    return 0


def main():
    parser = build_parser()
    args = parser.parse_args()
    code = run_cli_command(args)
    sys.exit(code)


if __name__ == "__main__":
    main()
