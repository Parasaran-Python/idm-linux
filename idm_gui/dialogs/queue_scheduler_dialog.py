"""
Queue Manager & Scheduler Settings Dialog
"""

from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)


class QueueSchedulerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scheduler & Queue Settings")
        self.setMinimumWidth(480)
        self.setMinimumHeight(380)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Tab 1: Schedule Tab
        sched_tab = QWidget()
        sched_layout = QVBoxLayout(sched_tab)

        time_box = QGroupBox("Schedule Timers")
        time_form = QFormLayout(time_box)

        self.start_check = QCheckBox("Start download at:")
        self.start_time_edit = QTimeEdit(QTime.currentTime())
        time_form.addRow(self.start_check, self.start_time_edit)

        self.stop_check = QCheckBox("Stop download at:")
        self.stop_time_edit = QTimeEdit(QTime.currentTime().addSecs(3600))
        time_form.addRow(self.stop_check, self.stop_time_edit)

        sched_layout.addWidget(time_box)

        limits_box = QGroupBox("Concurrency & Retries")
        limits_form = QFormLayout(limits_box)

        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setValue(1)
        limits_form.addRow("Max active downloads:", self.concurrent_spin)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 50)
        self.retries_spin.setValue(10)
        limits_form.addRow("Retry on connection failure:", self.retries_spin)

        sched_layout.addWidget(limits_box)
        sched_layout.addStretch()
        tabs.addTab(sched_tab, "⏰ Schedule")

        # Tab 2: Post-completion Actions
        post_tab = QWidget()
        post_layout = QVBoxLayout(post_tab)

        act_box = QGroupBox("Actions on Queue Completion")
        act_form = QFormLayout(act_box)

        self.post_action_combo = QComboBox()
        self.post_action_combo.addItems([
            "None (Keep IDM open)",
            "Show Desktop Notification",
            "Turn off computer (Poweroff)",
            "Sleep / Suspend computer",
            "Exit IDM"
        ])
        act_form.addRow("When queue finishes:", self.post_action_combo)

        post_layout.addWidget(act_box)
        post_layout.addStretch()
        tabs.addTab(post_tab, "🔌 Power & Notifications")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("Close")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)
