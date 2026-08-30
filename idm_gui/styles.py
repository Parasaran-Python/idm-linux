"""
IDM Linux Desktop GUI Stylesheets & Visual Themes
"""

IDM_DARK_THEME = """
QMainWindow, QDialog {
    background-color: #1e2430;
    color: #e2e8f0;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: #e2e8f0;
}

QMenuBar {
    background-color: #1a202c;
    color: #e2e8f0;
    border-bottom: 1px solid #2d3748;
    padding: 2px 6px;
}

QMenuBar::item {
    background: transparent;
    padding: 4px 8px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #2b6cb0;
    color: #ffffff;
}

QMenu {
    background-color: #1a202c;
    color: #e2e8f0;
    border: 1px solid #4a5568;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #2b6cb0;
    color: #ffffff;
}

QToolBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d3748, stop:1 #1a202c);
    border-bottom: 1px solid #4a5568;
    spacing: 6px;
    padding: 6px;
}

QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 6px 10px;
    color: #e2e8f0;
    font-weight: 500;
}

QToolButton:hover {
    background-color: #2b6cb0;
    border: 1px solid #4299e1;
    color: #ffffff;
}

QToolButton:pressed {
    background-color: #1a365d;
}

QTreeWidget {
    background-color: #171d26;
    border: 1px solid #2d3748;
    border-radius: 6px;
    padding: 4px;
    color: #cbd5e0;
}

QTreeWidget::item {
    padding: 6px 4px;
    border-radius: 4px;
}

QTreeWidget::item:hover {
    background-color: #2d3748;
}

QTreeWidget::item:selected {
    background-color: #2b6cb0;
    color: #ffffff;
    font-weight: bold;
}

QTableWidget {
    background-color: #171d26;
    border: 1px solid #2d3748;
    border-radius: 6px;
    gridline-color: #2d3748;
    selection-background-color: #2b6cb0;
    selection-color: #ffffff;
    color: #e2e8f0;
}

QHeaderView::section {
    background-color: #1a202c;
    color: #a0aec0;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #2d3748;
    border-bottom: 1px solid #2d3748;
    font-weight: 600;
}

QProgressBar {
    background-color: #2d3748;
    border: 1px solid #4a5568;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3182ce, stop:1 #38a169);
    border-radius: 3px;
}

QPushButton {
    background-color: #2b6cb0;
    border: 1px solid #4299e1;
    border-radius: 5px;
    color: #ffffff;
    font-weight: 600;
    padding: 7px 16px;
    min-height: 18px;
}

QPushButton:hover {
    background-color: #3182ce;
}

QPushButton:pressed {
    background-color: #1a365d;
}

QPushButton:disabled {
    background-color: #4a5568;
    border-color: #718096;
    color: #a0aec0;
}

QLineEdit {
    background-color: #171d26;
    border: 1px solid #4a5568;
    border-radius: 5px;
    padding: 6px 10px;
    color: #edf2f7;
    selection-background-color: #2b6cb0;
}

QLineEdit:focus {
    border: 1px solid #63b3ed;
}

QTabWidget::pane {
    border: 1px solid #2d3748;
    border-radius: 6px;
    background-color: #171d26;
}

QTabBar::tab {
    background-color: #1a202c;
    color: #a0aec0;
    padding: 8px 16px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #2b6cb0;
    color: #ffffff;
    font-weight: bold;
}

QStatusBar {
    background-color: #1a202c;
    color: #a0aec0;
    border-top: 1px solid #2d3748;
}
"""

IDM_SEGMENT_COLORS = [
    "#3182ce", # Blue
    "#38a169", # Green
    "#dd6b20", # Orange
    "#805ad5", # Purple
    "#d69e2e", # Gold
    "#e53e3e", # Red
    "#319795", # Teal
    "#d53f8c", # Pink
    "#4299e1", # Light Blue
    "#48bb78", # Light Green
    "#ed8936", # Light Orange
    "#9f7aea", # Light Purple
    "#ecc94b", # Yellow
    "#f56565", # Light Red
    "#38b2ac", # Cyan
    "#ed64a6", # Magenta
]
