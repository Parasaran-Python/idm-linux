"""
Real-Time Download Speed Graph Widget for IDM Linux
Renders live bandwidth transfer curve with gradient fill.
"""

from collections import deque
from typing import Optional
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget
from idm_gui.widgets.download_table import format_speed


class SpeedGraphWidget(QWidget):
    def __init__(self, max_samples: int = 60, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.max_samples = max_samples
        self.samples = deque(maxlen=max_samples)
        self.setMinimumHeight(70)
        self.setMaximumHeight(120)

    def add_speed_sample(self, speed_bps: float):
        self.samples.append(float(speed_bps))
        self.update()

    def clear(self):
        self.samples.clear()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(350, 90)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())

        # Background
        bg_rect = QRectF(0, 0, w, h)
        painter.setBrush(QColor("#171d26"))
        painter.setPen(QPen(QColor("#2d3748"), 1))
        painter.drawRoundedRect(bg_rect, 4, 4)

        if not self.samples:
            painter.setPen(QColor("#718096"))
            painter.setFont(QFont("sans-serif", 9))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, "Waiting for speed samples...")
            painter.end()
            return

        max_speed = max(max(self.samples), 1024.0)

        # Draw grid lines
        painter.setPen(QPen(QColor("#2d3748"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(0, int(h * 0.25), int(w), int(h * 0.25))
        painter.drawLine(0, int(h * 0.50), int(w), int(h * 0.50))
        painter.drawLine(0, int(h * 0.75), int(w), int(h * 0.75))

        # Speed labels
        painter.setPen(QColor("#a0aec0"))
        painter.setFont(QFont("sans-serif", 8))
        painter.drawText(6, 14, format_speed(max_speed))
        painter.drawText(6, int(h * 0.55), format_speed(max_speed / 2))

        # Construct path
        points = []
        n = len(self.samples)
        step_x = w / (self.max_samples - 1) if self.max_samples > 1 else w
        start_x = w - (n - 1) * step_x

        for i, s in enumerate(self.samples):
            px = start_x + i * step_x
            py = h - 6.0 - (s / max_speed) * (h - 16.0)
            points.append(QPointF(px, py))

        if points:
            path = QPainterPath()
            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)

            # Fill gradient area
            fill_path = QPainterPath(path)
            fill_path.lineTo(points[-1].x(), h - 2)
            fill_path.lineTo(points[0].x(), h - 2)
            fill_path.closeSubpath()

            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0.0, QColor(49, 130, 206, 140))
            grad.setColorAt(1.0, QColor(49, 130, 206, 15))
            painter.fillPath(fill_path, grad)

            # Draw curve line
            painter.setPen(QPen(QColor("#4299e1"), 2.0))
            painter.drawPath(path)

        painter.end()
