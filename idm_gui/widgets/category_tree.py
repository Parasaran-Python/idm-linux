"""
IDM Category Sidebar Navigation Tree Widget
"""

from typing import Dict, Optional
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem


class CategoryTreeWidget(QTreeWidget):
    category_selected = pyqtSignal(str)
    queue_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self._category_items: Dict[str, QTreeWidgetItem] = {}
        self._setup_tree()
        self.itemClicked.connect(self._on_item_clicked)

    def _setup_tree(self):
        self.clear()

        # Root: Categories
        self.root_categories = QTreeWidgetItem(self, ["📁 Categories"])
        self.root_categories.setExpanded(True)

        categories_def = [
            ("All Downloads", "🌐 All Downloads"),
            ("Unfinished", "⏳ Unfinished"),
            ("Finished", "✅ Finished"),
            ("Compressed", "📦 Compressed"),
            ("Documents", "📄 Documents"),
            ("Music", "🎵 Music"),
            ("Programs", "⚙️ Programs"),
            ("Video", "🎬 Video"),
        ]

        for key, label in categories_def:
            item = QTreeWidgetItem(self.root_categories, [label])
            item.setData(0, 100, key)
            self._category_items[key] = item

        # Root: Queues
        self.root_queues = QTreeWidgetItem(self, ["📋 Queues"])
        self.root_queues.setExpanded(True)

        self.main_queue_item = QTreeWidgetItem(self.root_queues, ["Main Download Queue"])
        self.main_queue_item.setData(0, 101, "main")

        # Select "All Downloads" initially
        if "All Downloads" in self._category_items:
            self.setCurrentItem(self._category_items["All Downloads"])

    def update_counts(self, counts: Dict[str, int]):
        """Update badge numbers in category tree."""
        for key, count in counts.items():
            if key in self._category_items:
                item = self._category_items[key]
                base_name = item.text(0).split(" (")[0]
                if count > 0:
                    item.setText(0, f"{base_name} ({count})")
                else:
                    item.setText(0, base_name)

    def select_category(self, category_name: str):
        if category_name in self._category_items:
            item = self._category_items[category_name]
            self.setCurrentItem(item)
            self.category_selected.emit(category_name)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        cat_key = item.data(0, 100)
        if cat_key:
            self.category_selected.emit(cat_key)
            return

        queue_key = item.data(0, 101)
        if queue_key:
            self.queue_selected.emit(queue_key)
            return
