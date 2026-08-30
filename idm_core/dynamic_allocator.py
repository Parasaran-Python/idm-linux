"""
Dynamic Multi-Segment Allocation Engine (IDM-style Chunk Splitting)
"""

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Segment:
    index: int
    start_byte: int
    current_byte: int
    end_byte: int  # inclusive byte index, -1 for unknown length stream
    status: str = "queued"  # queued, downloading, completed, error, paused
    temp_path: str = ""
    worker_id: Optional[int] = None
    error_msg: str = ""

    @property
    def total_size(self) -> int:
        if self.end_byte < 0 or self.end_byte < self.start_byte:
            return -1
        return self.end_byte - self.start_byte + 1

    @property
    def downloaded_size(self) -> int:
        if self.current_byte < self.start_byte:
            return 0
        if self.end_byte >= 0 and self.current_byte > self.end_byte:
            return self.total_size
        return self.current_byte - self.start_byte

    @property
    def remaining_size(self) -> int:
        if self.end_byte < 0:
            return -1
        rem = self.end_byte - self.current_byte + 1
        return max(0, rem)

    @property
    def progress_pct(self) -> float:
        if self.total_size <= 0:
            return 100.0 if self.status == "completed" else 0.0
        return min(100.0, max(0.0, (self.downloaded_size / self.total_size) * 100.0))

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_byte": self.start_byte,
            "current_byte": self.current_byte,
            "end_byte": self.end_byte,
            "status": self.status,
            "temp_path": self.temp_path,
            "worker_id": self.worker_id,
            "error_msg": self.error_msg,
            "downloaded_bytes": self.downloaded_size,
            "total_bytes": self.total_size,
            "progress_pct": self.progress_pct,
        }


class DynamicAllocator:
    def __init__(
        self,
        total_bytes: int = 0,
        num_connections: int = 8,
        min_split_size: int = 2097152,  # 2 MB minimum remaining to split
        max_segments: int = 16,
        saved_segments: Optional[List[dict]] = None
    ):
        self.total_bytes = total_bytes
        self.num_connections = num_connections
        self.min_split_size = min_split_size
        self.max_segments = max_segments or max(num_connections, 16)
        self._segments: Dict[int, Segment] = {}
        self._lock = threading.RLock()

        if saved_segments:
            self._load_from_saved(saved_segments)
        else:
            self._initial_partition(total_bytes, num_connections)

    def _initial_partition(self, total_bytes: int, num_connections: int):
        """Split total bytes into initial continuous segment intervals."""
        with self._lock:
            self._segments.clear()
            if total_bytes <= 0:
                # Single chunk stream
                self._segments[0] = Segment(
                    index=0,
                    start_byte=0,
                    current_byte=0,
                    end_byte=-1,
                    status="queued"
                )
                return

            conn = max(1, min(num_connections, total_bytes, 32))
            chunk_size = total_bytes // conn
            start = 0
            for i in range(conn):
                if i == conn - 1:
                    end = total_bytes - 1
                else:
                    end = start + chunk_size - 1
                
                self._segments[i] = Segment(
                    index=i,
                    start_byte=start,
                    current_byte=start,
                    end_byte=end,
                    status="queued"
                )
                start = end + 1

    def _load_from_saved(self, saved_segments: List[dict]):
        """Reconstruct segments from persistence records."""
        with self._lock:
            self._segments.clear()
            for s in saved_segments:
                idx = s.get("index", s.get("segment_index", 0))
                status = s.get("status", "queued")
                if status == "downloading":
                    status = "queued"
                self._segments[idx] = Segment(
                    index=idx,
                    start_byte=s["start_byte"],
                    current_byte=s.get("current_byte", s["start_byte"]),
                    end_byte=s["end_byte"],
                    status=status,
                    temp_path=s.get("temp_path", "")
                )

    def request_subchunk_split(self, min_split_size: Optional[int] = None) -> Optional[Tuple[int, Segment]]:
        """
        Dynamic IDM Split: Find the active/queued segment with the largest remaining byte range.
        If it exceeds min_split_size, split its remaining range into two halves.
        """
        threshold = min_split_size if min_split_size is not None else self.min_split_size
        with self._lock:
            if len(self._segments) >= self.max_segments:
                return None

            candidate_idx = None
            max_remaining = 0

            for idx, seg in self._segments.items():
                if seg.status in ["downloading", "queued"] and seg.end_byte > 0:
                    remaining = seg.end_byte - seg.current_byte + 1
                    if remaining > max_remaining:
                        max_remaining = remaining
                        candidate_idx = idx

            if candidate_idx is None or max_remaining < threshold:
                return None

            source_seg = self._segments[candidate_idx]
            half_remaining = max_remaining // 2
            new_source_end = source_seg.current_byte + half_remaining - 1
            new_seg_start = new_source_end + 1
            original_end = source_seg.end_byte

            if new_seg_start > original_end:
                return None

            # Adjust source segment end byte
            source_seg.end_byte = new_source_end

            # Create new segment for the remaining half
            new_idx = len(self._segments)
            new_segment = Segment(
                index=new_idx,
                start_byte=new_seg_start,
                current_byte=new_seg_start,
                end_byte=original_end,
                status="queued"
            )
            self._segments[new_idx] = new_segment
            return (candidate_idx, new_segment)

    def update_progress(self, segment_index: int, downloaded_bytes_delta: int):
        """Advance progress of a specific segment."""
        with self._lock:
            if segment_index in self._segments:
                seg = self._segments[segment_index]
                seg.current_byte += downloaded_bytes_delta
                if seg.end_byte >= 0 and seg.current_byte > seg.end_byte + 1:
                    seg.current_byte = seg.end_byte + 1

    def set_current_byte(self, segment_index: int, current_byte: int):
        with self._lock:
            if segment_index in self._segments:
                self._segments[segment_index].current_byte = current_byte

    def set_segment_status(self, segment_index: int, status: str, worker_id: Optional[int] = None, error_msg: str = ""):
        with self._lock:
            if segment_index in self._segments:
                seg = self._segments[segment_index]
                seg.status = status
                if worker_id is not None:
                    seg.worker_id = worker_id
                if error_msg:
                    seg.error_msg = error_msg

    def mark_completed(self, segment_index: int):
        with self._lock:
            if segment_index in self._segments:
                seg = self._segments[segment_index]
                seg.status = "completed"
                if seg.end_byte >= 0:
                    seg.current_byte = seg.end_byte + 1

    def mark_error(self, segment_index: int, error_msg: str = ""):
        with self._lock:
            if segment_index in self._segments:
                self._segments[segment_index].status = "error"
                self._segments[segment_index].error_msg = error_msg

    def get_segment(self, index: int) -> Optional[Segment]:
        with self._lock:
            return self._segments.get(index)

    def get_segments(self) -> List[Segment]:
        with self._lock:
            return [self._segments[i] for i in sorted(self._segments.keys())]

    def get_total_downloaded(self) -> int:
        with self._lock:
            return sum(s.downloaded_size for s in self._segments.values())

    def is_complete(self) -> bool:
        with self._lock:
            if not self._segments:
                return False
            for seg in self._segments.values():
                if seg.status != "completed":
                    if seg.end_byte >= 0 and seg.current_byte > seg.end_byte:
                        continue
                    return False
            return True

    def to_dict_list(self) -> List[dict]:
        with self._lock:
            return [s.to_dict() for s in self.get_segments()]
