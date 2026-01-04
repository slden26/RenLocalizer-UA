"""Dialog for choosing how to run UnRen."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt

from src.utils.config import ConfigManager


class UnRenModeDialog(QDialog):
    """Simple selector dialog for automatic vs manual UnRen runs."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.selected_mode: str | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        texts = self.config_manager.get_ui_text("unren_mode_dialog") or {}
        self.setWindowTitle(texts.get("title", "UnRen"))
        self.setModal(True)
        self.resize(420, 360)

        layout = QVBoxLayout(self)

        description = QLabel(texts.get("description", ""))
        description.setWordWrap(True)
        description.setObjectName("unren-mode-description")
        layout.addWidget(description)

        auto_data = texts.get("automatic", {})
        layout.addWidget(
            self._build_mode_box(
                title=auto_data.get("title", "Automatic"),
                details=auto_data.get("details", []),
                button_label=auto_data.get("button", "Run Automatically"),
                mode="automatic",
            )
        )

        manual_data = texts.get("manual", {})
        layout.addWidget(
            self._build_mode_box(
                title=manual_data.get("title", "Manual"),
                details=manual_data.get("details", []),
                button_label=manual_data.get("button", "Run Manually"),
                mode="manual",
            )
        )

        manual_hint = QLabel(texts.get("manual_hint", ""))
        manual_hint.setWordWrap(True)
        manual_hint.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        manual_hint.setObjectName("unren-mode-hint")
        layout.addWidget(manual_hint)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _build_mode_box(
        self,
        title: str,
        details: list[str],
        button_label: str,
        mode: str,
    ) -> QGroupBox:
        box = QGroupBox(title)
        box_layout = QVBoxLayout(box)

        if details:
            bullets = "".join(f"<li>{text}</li>" for text in details)
            label = QLabel(f"<ul>{bullets}</ul>")
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            box_layout.addWidget(label)

        button_row = QHBoxLayout()
        button_row.addStretch()

        button = QPushButton(button_label)
        button.setProperty("mode", mode)
        button.clicked.connect(lambda _=False, value=mode: self._select_mode(value))
        button_row.addWidget(button)
        box_layout.addLayout(button_row)

        return box

    def _select_mode(self, mode: str) -> None:
        """Store the chosen mode and close the dialog immediately."""
        self.selected_mode = mode
        super().accept()
