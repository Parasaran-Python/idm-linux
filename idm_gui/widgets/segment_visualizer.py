"""
Iconic IDM Dynamic Segment Progress Bar Visualizer Widget
Renders real-time color-coded dynamic connection chunks using QPainter.
"""

from typing import Dict, List, Optional
from PyQt6.QtCore import QPoint, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QToolTip, QWidget
from idm_gui.styles import IDM_SEGMENT_COLORS


class SegmentVisualizerWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.segments: List[dict] = []
        self.total_bytes: int = 0
        self.setMinimumHeight(28)
        self.setMaximumHeight(40)
        self.setMouseTracking(True)

    def set_segments(self, segments: List[dict], total_bytes: int = 0):
        """Update segments data and trigger visual repaint."""
        self.segments = sorted(segments, key=lambda s: s.get("start_byte", 0))
        self.total_bytes = total_bytes
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(350, 32)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        # Outer background
        bg_rect = QRectF(0, 0, w, h)
        painter.setBrush(QColor("#171d26"))
        painter.setPen(QPen(QColor("#4a5568"), 1.5))
        painter.drawRoundedRect(bg_rect, 4, 4)

        if not self.segments or self.total_bytes <= 0:
            # Empty or streaming mode placeholder
            painter.setPen(QColor("#718096"))
            painter.setFont(QFont("sans-serif", 9))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, "Connecting / Allocating segments...")
            painter.end()
            return

        # Render each segment chunk
        inner_w = w - 4
        inner_h = h - 4
        x_offset = 2.0
        y_offset = 2.0

        for i, seg in enumerate(self.segments):
            start = seg.get("start_byte", 0)
            end = seg.get("end_byte", 0)
            curr = seg.get("current_byte", start)
            status = seg.get("status", "queued")

            if end < start:
                continue

            seg_len = end - start + 1
            dl_len = max(0, min(curr - start, seg_len))
            if status == "completed":
                dl_len = seg_len

            # Fraction of total file
            seg_x = x_offset + (start / self.total_bytes) * inner_w
            seg_w = (seg_len / self.total_bytes) * inner_w
            dl_w = (dl_len / seg_len) * seg_w if seg_len > 0 else 0

            color_hex = IDM_SEGMENT_COLORS[i % len(IDM_SEGMENT_COLORS)]
            base_color = QColor(color_hex)

            # Segment boundary background slot (unfilled portion)
            slot_rect = QRectF(seg_x, y_offset, seg_w, inner_h)
            dim_slot_color = QColor(base_color.red(), base_color.green(), base_color.blue(), 45)
            painter.setBrush(dim_slot_color)
            painter.setPen(QPen(QColor("#2d3748"), 0.5))
            painter.drawRect(slot_rect)

            # Downloaded progress fill block
            if dl_w > 0:
                fill_rect = QRectF(seg_x, y_offset, dl_w, inner_h)
                grad = QLinearGradient(seg_x, y_offset, seg_x, y_offset + inner_h)
                grad.setColorAt(0.0, base_color.lighter(130))
                grad.setColorAt(0.5, base_color)
                grad.setColorAt(1.0, base_color.darker(120))
                
                painter.setBrush(grad)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(fill_rect)

            # Segment divider line
            painter.setPen(QPen(QColor("#1a202c"), 1.0))
            painter.drawLine(int(seg_x + seg_w), int(y_offset), int(seg_x + seg_w), int(y_offset + inner_h))

        painter.end()

    def mouseMoveEvent(self, event):
        """Show hover tooltip with details about the hovered segment."""
        if not self.segments or self.total_bytes <= 0:
            return

        w = float(self.width() - 4)
        pos_x = event.position().x() - 2
        hover_byte = int((pos_x / w) * self.total_bytes) if w > 0 else 0

        for i, seg in enumerate(self.segments):
            start = seg.get("start_byte", 0)
            end = seg.get("end_byte", 0)
            curr = seg.get("current_byte", start)
            if start <= hover_byte <= end:
                dl_bytes = max(0, curr - start)
                total = end - start + 1
                pct = (dl_bytes / total * 100) if total > 0 else 0
                text = (
                    f"Segment #{i + 1}\n"
                    f"Range: {start:,} - {end:,} ({total:,} bytes)\n"
                    f"Downloaded: {dl_bytes:,} bytes ({pct:.1f}%)\n"
                    f"Status: {seg.get('status', 'queued').capitalize()}"
                )
                QToolTip.showText(event.globalPosition().toPoint(), text, self)
                return

        QToolTip.hideText()
