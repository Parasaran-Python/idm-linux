"""
Formatting utilities for human-readable byte sizes, transfer speeds, and durations.
"""


def format_bytes(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(num_bytes)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024.0
        i += 1
    return f"{val:.2f} {units[i]}"


def format_speed(bps: float) -> str:
    if bps <= 0:
        return "0 KB/s"
    return f"{format_bytes(int(bps))}/s"


def format_time(seconds: int) -> str:
    if seconds <= 0:
        return "--:--:--"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
