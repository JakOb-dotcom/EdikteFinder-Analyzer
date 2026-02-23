"""
EdikteFinder-Analyzer – Desktop Application (PyQt6)
Einstiegspunkt: python main.py
"""

import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QAbstractTableModel, QModelIndex
)
from PyQt6.QtGui import (
    QColor, QFont, QPalette, QBrush
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTabWidget,
    QTableView, QHeaderView, QFrame, QSplitter, QTextEdit,
    QScrollArea, QGroupBox, QFormLayout, QMessageBox,
    QFileDialog, QDialog, QDialogButtonBox, QCheckBox,
    QProgressBar, QToolBar, QStatusBar, QSizePolicy, QStackedWidget
)

import config
import storage
import ai_analyzer


# ══════════════════════════════════════════════════════════════
#  Styling
# ══════════════════════════════════════════════════════════════

DARK_STYLE = """
QMainWindow, QDialog {
    background: #0f1117;
}
QWidget {
    background: #0f1117;
    color: #e2e8f0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 9pt;
}
QTabWidget::pane {
    border: none;
    background: #0f1117;
}
QTabBar::tab {
    background: #1e293b;
    color: #94a3b8;
    padding: 8px 20px;
    border: none;
    border-right: 1px solid #0f1117;
    font-weight: 500;
}
QTabBar::tab:selected {
    background: #4f46e5;
    color: #ffffff;
}
QTabBar::tab:hover:!selected {
    background: #253347;
    color: #e2e8f0;
}
QGroupBox {
    border: 1px solid #1e293b;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px;
    font-weight: 600;
    color: #94a3b8;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QLineEdit, QComboBox, QTextEdit {
    background: #1e293b;
    border: 1px solid #2d3f55;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e2e8f0;
    selection-background-color: #4f46e5;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #6366f1;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background: #1e293b;
    border: 1px solid #2d3f55;
    selection-background-color: #4f46e5;
    color: #e2e8f0;
}
QPushButton {
    background: #1e293b;
    color: #e2e8f0;
    border: 1px solid #2d3f55;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
}
QPushButton:hover {
    background: #253347;
    border-color: #4f46e5;
}
QPushButton:pressed {
    background: #4f46e5;
}
QPushButton#btn_primary {
    background: #4f46e5;
    border: none;
    color: white;
    font-weight: 600;
}
QPushButton#btn_primary:hover {
    background: #4338ca;
}
QPushButton#btn_primary:pressed {
    background: #3730a3;
}
QPushButton#btn_danger {
    background: #7f1d1d;
    border: none;
    color: #fca5a5;
}
QPushButton#btn_danger:hover {
    background: #991b1b;
}
QPushButton#btn_success {
    background: #064e3b;
    border: none;
    color: #6ee7b7;
}
QPushButton#btn_success:hover {
    background: #065f46;
}
QTableView {
    background: #0f1117;
    alternate-background-color: #161b27;
    border: none;
    gridline-color: #1e293b;
    selection-background-color: #312e81;
    selection-color: #e0e7ff;
}
QHeaderView::section {
    background: #161b27;
    color: #64748b;
    border: none;
    border-bottom: 1px solid #1e293b;
    border-right: 1px solid #1e293b;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QScrollBar:vertical {
    background: #161b27;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #2d3f55;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #4f46e5;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #161b27;
    height: 8px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #2d3f55;
    border-radius: 4px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSplitter::handle {
    background: #1e293b;
    width: 2px;
}
QStatusBar {
    background: #161b27;
    border-top: 1px solid #1e293b;
    color: #64748b;
    font-size: 12px;
}
QProgressBar {
    background: #1e293b;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}
QProgressBar::chunk {
    background: #4f46e5;
    border-radius: 4px;
}
QLabel#label_kpi_value {
    font-size: 28px;
    font-weight: 700;
    color: #818cf8;
}
QLabel#label_section {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
}
QFrame#card {
    background: #161b27;
    border: 1px solid #1e293b;
    border-radius: 10px;
}
QFrame#divider {
    background: #1e293b;
    max-height: 1px;
}
"""


# ══════════════════════════════════════════════════════════════
#  Worker Thread (runs asyncio scraper / AI in background)
# ══════════════════════════════════════════════════════════════

class Worker(QThread):
    progress   = pyqtSignal(str)
    finished   = pyqtSignal(object)
    error      = pyqtSignal(str)

    def __init__(self, coro):
        super().__init__()
        self._coro = coro

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._coro)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            # Drain all remaining tasks (e.g. httpx AsyncClient cleanup)
            # before closing the loop to avoid "Event loop is closed" errors.
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()


# ══════════════════════════════════════════════════════════════
#  Table Model for Edikte
# ══════════════════════════════════════════════════════════════

COLUMNS = [
    ("", "selected"),
    ("Aktenzeichen", "aktenzeichen"),
    ("Gericht", "gericht"),
    ("Adresse", "adresse"),
    ("Kategorien", "kategorien"),
    ("Versteigerung", "versteigerung"),
    ("Mind. Gebot", "mindestgebot"),
    ("Schätzwert", "schätzwert"),
    ("Status", "status"),
    ("Score", "_score"),
    ("Empfehlung", "_empfehlung"),
]

STATUS_COLORS = {
    "scraped":    "#64748b",
    "downloaded": "#0284c7",
    "analyzed":   "#16a34a",
    "no_pdf":     "#b45309",
}

EMPFEHLUNG_COLORS = {
    "KAUFEN": "#16a34a",
    "PRÜFEN": "#d97706",
    "MEIDEN": "#dc2626",
}


class EdikteModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._edikte: list[dict] = []
        self._analyses: dict     = {}
        self._selected: set      = set()

    def load(self):
        self._edikte   = storage.load_all_edikte()
        self._analyses = storage.load_all_analyses()
        self._selected.clear()
        self.layoutChanged.emit()

    def rowCount(self, _=QModelIndex()): return len(self._edikte)
    def columnCount(self, _=QModelIndex()): return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][0]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        edikt = self._edikte[row]
        edikt_id = edikt.get("id", "")
        analysis = self._analyses.get(edikt_id, {})
        col_key = COLUMNS[col][1]

        if role == Qt.ItemDataRole.DisplayRole:
            if col_key == "selected":
                return None
            if col_key == "_score":
                s = analysis.get("investitions_score")
                return str(s) if s else "—"
            if col_key == "_empfehlung":
                return analysis.get("empfehlung", "—")
            return edikt.get(col_key, "") or ""

        if role == Qt.ItemDataRole.CheckStateRole and col == 0:
            return Qt.CheckState.Checked if edikt_id in self._selected else Qt.CheckState.Unchecked

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_key == "status":
                c = STATUS_COLORS.get(edikt.get("status", ""), "#64748b")
                return QBrush(QColor(c))
            if col_key == "_empfehlung":
                e = analysis.get("empfehlung", "")
                c = EMPFEHLUNG_COLORS.get(e, "#94a3b8")
                return QBrush(QColor(c))
            if col_key == "_score":
                s = analysis.get("investitions_score", 0) or 0
                if s >= 7:   c = "#16a34a"
                elif s >= 4: c = "#d97706"
                else:        c = "#dc2626"
                return QBrush(QColor(c))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_key in ("_score", "mindestgebot"):
                return Qt.AlignmentFlag.AlignCenter
        return None

    def flags(self, index):
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            base |= Qt.ItemFlag.ItemIsUserCheckable
        return base

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            edikt_id = self._edikte[index.row()].get("id", "")
            if value == Qt.CheckState.Checked.value:
                self._selected.add(edikt_id)
            else:
                self._selected.discard(edikt_id)
            self.dataChanged.emit(index, index)
            return True
        return False

    def edikt_at(self, row: int) -> dict:
        return self._edikte[row]

    def selected_ids(self) -> list[str]:
        return list(self._selected)

    def select_all(self, checked: bool):
        self._selected = {e.get("id", "") for e in self._edikte} if checked else set()
        self.layoutChanged.emit()


# ══════════════════════════════════════════════════════════════
#  Settings Dialog
# ══════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Einstellungen – KI-Provider & Optionen")
        self.setMinimumWidth(540)
        self.setMinimumHeight(660)
        s = config.load_settings()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Scrollable body ──────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # ── Aktiver KI-Provider ──────────────────────────────────────────────
        grp_prov = QGroupBox("Aktiver KI-Provider")
        form_prov = QFormLayout(grp_prov)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "anthropic", "gemini", "grok", "ollama"])
        self.provider_combo.setCurrentText(s.get("ai_provider", config.AI_PROVIDER))
        form_prov.addRow("Provider:", self.provider_combo)
        layout.addWidget(grp_prov)

        # ── OpenAI ───────────────────────────────────────────────────────────
        grp_oa = QGroupBox("OpenAI")
        form_oa = QFormLayout(grp_oa)
        self.oa_key = QLineEdit(s.get("openai_api_key", config.OPENAI_API_KEY))
        self.oa_key.setPlaceholderText("sk-...")
        self.oa_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.oa_model = QComboBox()
        self.oa_model.setEditable(True)
        self.oa_model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.oa_model.addItems(["gpt-4o-mini", "gpt-4o", "gpt-4o-2024-11-20", "gpt-4-turbo", "o1-mini", "o1"])
        self.oa_model.setCurrentText(s.get("openai_model", config.OPENAI_MODEL))
        form_oa.addRow("API Key:", self.oa_key)
        form_oa.addRow("Modell:", self.oa_model)
        layout.addWidget(grp_oa)

        # ── Anthropic ────────────────────────────────────────────────────────
        grp_an = QGroupBox("Anthropic")
        form_an = QFormLayout(grp_an)
        self.an_key = QLineEdit(s.get("anthropic_api_key", config.ANTHROPIC_API_KEY))
        self.an_key.setPlaceholderText("sk-ant-...")
        self.an_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.an_model = QComboBox()
        self.an_model.setEditable(True)
        self.an_model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.an_model.addItems(["claude-haiku-20240307", "claude-3-5-sonnet-20241022",
                                "claude-3-5-haiku-20241022", "claude-opus-4-5"])
        self.an_model.setCurrentText(s.get("anthropic_model", config.ANTHROPIC_MODEL))
        form_an.addRow("API Key:", self.an_key)
        form_an.addRow("Modell:", self.an_model)
        layout.addWidget(grp_an)

        # ── Gemini (Google) ──────────────────────────────────────────────────
        grp_ge = QGroupBox("Gemini (Google)")
        form_ge = QFormLayout(grp_ge)
        self.ge_key = QLineEdit(s.get("gemini_api_key", getattr(config, "GEMINI_API_KEY", "")))
        self.ge_key.setPlaceholderText("AIza...")
        self.ge_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ge_model = QComboBox()
        self.ge_model.setEditable(True)
        self.ge_model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.ge_model.addItems([
            "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-3-flash-preview",
            "gemini-2.5-pro-preview-05-06", "gemini-1.5-flash-latest", "gemini-1.5-pro-latest",
        ])
        self.ge_model.setCurrentText(s.get("gemini_model", getattr(config, "GEMINI_MODEL", "gemini-2.0-flash")))
        form_ge.addRow("API Key:", self.ge_key)
        form_ge.addRow("Modell:", self.ge_model)
        layout.addWidget(grp_ge)

        # ── Grok (xAI) ───────────────────────────────────────────────────────
        grp_gr = QGroupBox("Grok (xAI)")
        form_gr = QFormLayout(grp_gr)
        self.gr_key = QLineEdit(s.get("grok_api_key", getattr(config, "GROK_API_KEY", "")))
        self.gr_key.setPlaceholderText("xai-...")
        self.gr_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gr_model = QComboBox()
        self.gr_model.setEditable(True)
        self.gr_model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.gr_model.addItems(["grok-3-fast-beta", "grok-3-beta", "grok-2-latest", "grok-beta"])
        self.gr_model.setCurrentText(s.get("grok_model", getattr(config, "GROK_MODEL", "grok-3-fast-beta")))
        gr_hint = QLabel("OpenAI-kompatible API via api.x.ai  ·  Modellname frei eingebbar")
        gr_hint.setStyleSheet("color: #475569; font-size: 10px;")
        form_gr.addRow("API Key:", self.gr_key)
        form_gr.addRow("Modell:", self.gr_model)
        form_gr.addRow(gr_hint)
        layout.addWidget(grp_gr)

        # ── Ollama (Lokal) ────────────────────────────────────────────────────
        grp_ol = QGroupBox("Ollama (Lokal · Kostenlos)")
        form_ol = QFormLayout(grp_ol)
        self.ol_url = QLineEdit(s.get("ollama_base_url", config.OLLAMA_BASE_URL))
        self.ol_model = QLineEdit(s.get("ollama_model", config.OLLAMA_MODEL))
        self.ol_model.setPlaceholderText("z.B. llama3.2, mistral, qwen2.5:32b")
        form_ol.addRow("Server-URL:", self.ol_url)
        form_ol.addRow("Modell:", self.ol_model)
        layout.addWidget(grp_ol)

        # ── Kontext-Budget ────────────────────────────────────────────────────
        grp_tok = QGroupBox("Kontext-Budget (Zeichen)")
        form_tok = QFormLayout(grp_tok)
        self.max_chars = QLineEdit(str(s.get("max_context_chars", config.MAX_CONTEXT_CHARS)))
        form_tok.addRow("Max. Zeichen:", self.max_chars)
        lbl_hint = QLabel(
            "20–30-seitiges Gutachten ≈ 40.000 Zeichen  |  Cloud: kostenpflichtig  |  Ollama: kostenlos\n"
            "Empfehlung Cloud: 20.000–40.000  ·  Ollama: bis 80.000"
        )
        lbl_hint.setStyleSheet("color: #475569; font-size: 10px;")
        form_tok.addRow(lbl_hint)
        layout.addWidget(grp_tok)

        layout.addStretch()

        # ── Sticky button bar ─────────────────────────────────────────────────
        btn_bar = QWidget()
        btn_bar.setStyleSheet("background: #161b27; border-top: 1px solid #1e293b;")
        btn_bl = QHBoxLayout(btn_bar)
        btn_bl.setContentsMargins(20, 12, 20, 12)
        btn_save = QPushButton("  Speichern")
        btn_save.setObjectName("btn_primary")
        btn_save.setFixedHeight(36)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.setFixedHeight(36)
        btn_save.clicked.connect(self._save)
        btn_cancel.clicked.connect(self.reject)
        btn_bl.addStretch()
        btn_bl.addWidget(btn_cancel)
        btn_bl.addWidget(btn_save)
        root.addWidget(btn_bar)

    def _save(self):
        s = {
            "ai_provider":       self.provider_combo.currentText(),
            "openai_api_key":    self.oa_key.text().strip(),
            "openai_model":      self.oa_model.currentText().strip(),
            "anthropic_api_key": self.an_key.text().strip(),
            "anthropic_model":   self.an_model.currentText().strip(),
            "gemini_api_key":    self.ge_key.text().strip(),
            "gemini_model":      self.ge_model.currentText().strip(),
            "grok_api_key":      self.gr_key.text().strip(),
            "grok_model":        self.gr_model.currentText().strip(),
            "ollama_base_url":   self.ol_url.text().strip(),
            "ollama_model":      self.ol_model.text().strip(),
            "max_context_chars": int(self.max_chars.text().strip() or 40000),
        }
        config.save_settings(s)
        config.apply_settings()
        self.accept()


# ══════════════════════════════════════════════════════════════
#  Detail / Analysis Panel
# ══════════════════════════════════════════════════════════════

def _section(title: str) -> QLabel:
    lbl = QLabel(title.upper())
    lbl.setObjectName("label_section")
    lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 1px; margin-top: 8px;")
    return lbl


class DetailPanel(QWidget):
    request_download = pyqtSignal(str)  # edikt_id
    request_analyze  = pyqtSignal(str)  # edikt_id

    def __init__(self):
        super().__init__()
        self._edikt_id: Optional[str] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(4)

        # Title
        self.lbl_title = QLabel("Kein Edikt ausgewählt")
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #e2e8f0;")
        self.lbl_title.setWordWrap(True)
        layout.addWidget(self.lbl_title)

        divider = QFrame(); divider.setObjectName("divider"); divider.setFixedHeight(1)
        layout.addWidget(divider)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(4)
        self.content_layout.addStretch()
        scroll.setWidget(self.content)
        layout.addWidget(scroll, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        self.btn_download = QPushButton("⬇  Gutachten laden")
        self.btn_download.setObjectName("btn_primary")
        self.btn_download.clicked.connect(self._on_download_clicked)
        self.btn_analyze  = QPushButton("✦  KI-Analyse")
        self.btn_analyze.setObjectName("btn_success")
        self.btn_analyze.clicked.connect(self._on_analyze_clicked)
        btn_row.addWidget(self.btn_download)
        btn_row.addWidget(self.btn_analyze)
        layout.addLayout(btn_row)

    def _on_download_clicked(self):
        if self._edikt_id is not None:
            self.request_download.emit(self._edikt_id)

    def _on_analyze_clicked(self):
        if self._edikt_id is not None:
            self.request_analyze.emit(self._edikt_id)

    def _clear(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_edikt(self, edikt: dict):
        self._edikt_id = edikt.get("id")
        self._clear()
        cl = self.content_layout

        self.lbl_title.setText(edikt.get("titel") or edikt.get("aktenzeichen") or "Edikt")
        has_pdf = storage.has_pdf(self._edikt_id)
        analysis = storage.get_analysis(self._edikt_id)

        # Basic metadata
        cl.addWidget(_section("Grunddaten"))
        for label, key in [
            ("Aktenzeichen", "aktenzeichen"), ("Gericht", "gericht"),
            ("Kundmachung", "veroeffentlicht"), ("Versteigerung", "versteigerung"),
            ("Mindestgebot", "mindestgebot"), ("Schätzwert", "schätzwert"),
            ("Kategorie(n)", "kategorien"), ("Adresse", "adresse"),
            ("Objektgröße", "objektgröße"),
        ]:
            row = QHBoxLayout()
            lk = QLabel(label + ":")
            lk.setStyleSheet("color: #64748b; font-size: 12px; min-width: 110px;")
            lk.setFixedWidth(115)
            lv = QLabel(edikt.get(key, "") or "—")
            lv.setStyleSheet("color: #e2e8f0; font-size: 12px;")
            lv.setWordWrap(True)
            row.addWidget(lk)
            row.addWidget(lv, 1)
            w = QWidget(); w.setLayout(row)
            cl.addWidget(w)

        # PDF status
        pdf_lbl = QLabel("✓  PDF vorhanden" if has_pdf else "✗  Kein PDF heruntergeladen")
        pdf_lbl.setStyleSheet(f"color: {'#16a34a' if has_pdf else '#94a3b8'}; font-size: 12px; margin-top: 6px;")
        cl.addWidget(pdf_lbl)

        # Analysis
        if analysis:
            cl.addWidget(_section("KI-Analyse"))
            score = analysis.get("investitions_score", 0) or 0
            score_color = "#16a34a" if score >= 7 else "#d97706" if score >= 4 else "#dc2626"
            empf = analysis.get("empfehlung", "—")
            empf_color = EMPFEHLUNG_COLORS.get(empf, "#94a3b8")

            # Score badge row
            score_row = QHBoxLayout()
            score_lbl = QLabel(f"Score: {score}/10")
            score_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {score_color};")
            empf_lbl = QLabel(f"  {empf}")
            empf_lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {empf_color};")
            score_row.addWidget(score_lbl)
            score_row.addWidget(empf_lbl)
            score_row.addStretch()
            sw = QWidget(); sw.setLayout(score_row)
            cl.addWidget(sw)

            for label, key in [
                ("Objektart", "objekt_art"), ("Fläche", "flaeche"),
                ("Baujahr", "baujahr"), ("Zustand", "zustand"),
                ("Verkehrswert", "verkehrswert"), ("Lage", "lage_bewertung"),
                ("Risiko-Klasse", "risiko_klasse"), ("Rendite-Potenzial", "rendite_potenzial"),
                ("Marktlage", "marktlage"), ("Sanierungs-Kosten", "sanierungskosten_schaetzung"),
            ]:
                row = QHBoxLayout()
                lk = QLabel(label + ":")
                lk.setStyleSheet("color: #64748b; font-size: 12px; min-width: 110px;")
                lk.setFixedWidth(115)
                raw_val = analysis.get(key)
                val_str = str(raw_val) if (raw_val is not None and raw_val != "") else "—"
                # Color-code specific rating fields
                _RISK_COLORS = {"Sehr Niedrig": "#4ade80", "Niedrig": "#86efac", "Mittel": "#fbbf24", "Hoch": "#f97316", "Sehr Hoch": "#ef4444"}
                _REND_COLORS = {"Sehr Hoch": "#4ade80", "Hoch": "#86efac", "Mittel": "#fbbf24", "Niedrig": "#f97316", "Negativ": "#ef4444"}
                badge_color = None
                if key == "risiko_klasse":
                    badge_color = _RISK_COLORS.get(val_str)
                elif key == "rendite_potenzial":
                    badge_color = _REND_COLORS.get(val_str)
                lv = QLabel(val_str)
                if badge_color:
                    lv.setStyleSheet(f"color: {badge_color}; font-size: 12px; font-weight: 600;")
                else:
                    lv.setStyleSheet("color: #e2e8f0; font-size: 12px;")
                lv.setWordWrap(True)
                row.addWidget(lk)
                row.addWidget(lv, 1)
                w = QWidget(); w.setLayout(row)
                cl.addWidget(w)

            # Chancen
            chancen = analysis.get("chancen", [])
            if chancen:
                cl.addWidget(_section("Chancen"))
                for c in chancen:
                    lbl = QLabel(f"  ✓  {c}")
                    lbl.setStyleSheet("color: #6ee7b7; font-size: 12px;")
                    lbl.setWordWrap(True)
                    cl.addWidget(lbl)

            # Risiken
            risiken = analysis.get("risiken", [])
            if risiken:
                cl.addWidget(_section("Risiken"))
                for r in risiken:
                    lbl = QLabel(f"  ✗  {r}")
                    lbl.setStyleSheet("color: #fca5a5; font-size: 12px;")
                    lbl.setWordWrap(True)
                    cl.addWidget(lbl)

            # Zusammenfassung
            zf = analysis.get("zusammenfassung", "")
            if zf:
                cl.addWidget(_section("Zusammenfassung"))
                lbl = QLabel(zf)
                lbl.setWordWrap(True)
                lbl.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.5;")
                cl.addWidget(lbl)

            # Token info
            tok = analysis.get("tokens_used", 0)
            if tok:
                lbl_tok = QLabel(f"Token-Verbrauch: {tok:,}  |  Provider: {analysis.get('provider','')} / {analysis.get('model','')}")
                lbl_tok.setStyleSheet("color: #475569; font-size: 10px; margin-top: 8px;")
                cl.addWidget(lbl_tok)

        cl.addStretch()


# ══════════════════════════════════════════════════════════════
#  Overview Tab
# ══════════════════════════════════════════════════════════════

class OverviewTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self.kpi_total    = self._kpi_card("Einträge", "0", "#818cf8")
        self.kpi_analyzed = self._kpi_card("Analysiert", "0", "#34d399")
        self.kpi_kaufen   = self._kpi_card("KAUFEN", "0", "#4ade80")
        self.kpi_avg      = self._kpi_card("Ø Score", "—", "#fbbf24")
        self.kpi_pdf      = self._kpi_card("Mit PDF", "0", "#60a5fa")
        for kpi in [self.kpi_total, self.kpi_analyzed, self.kpi_kaufen, self.kpi_avg, self.kpi_pdf]:
            kpi_row.addWidget(kpi)
        layout.addLayout(kpi_row)

        # Refresh button
        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("⟳  Aktualisieren")
        btn_refresh.setObjectName("btn_primary")
        btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Overview table
        cols = ["Aktenzeichen", "Gericht", "Adresse", "Versteigerung",
                "Mindestgebot", "Objektart", "Fläche", "Baujahr",
                "Zustand", "Verkehrswert", "Score", "Risiko", "Rendite",
                "Empfehlung", "Zusammenfassung"]
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.overview_model = OverviewModel(cols)
        self.table.setModel(self.overview_model)
        layout.addWidget(self.table, 1)

    def _kpi_card(self, label: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedHeight(80)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 10, 16, 10)
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {color};")
        lbl_label = QLabel(label)
        lbl_label.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 600; letter-spacing: 0.5px;")
        cl.addWidget(lbl_val)
        cl.addWidget(lbl_label)
        card._value_label = lbl_val
        return card

    def refresh(self):
        edikte   = storage.load_all_edikte()
        analyses = storage.load_all_analyses()
        stats    = storage.get_stats()

        self.kpi_total._value_label.setText(str(stats["total_edikte"]))
        self.kpi_analyzed._value_label.setText(str(stats["total_analyses"]))
        self.kpi_kaufen._value_label.setText(str(stats["empfehlungen"].get("KAUFEN", 0)))
        self.kpi_avg._value_label.setText(str(stats["avg_score"]) if stats["avg_score"] else "—")
        self.kpi_pdf._value_label.setText(str(stats["with_pdf"]))

        rows = []
        for e in edikte:
            eid = e.get("id", "")
            a   = analyses.get(eid, {})
            chancen = a.get("chancen", [])
            risiken = a.get("risiken", [])
            rows.append([
                e.get("aktenzeichen", ""),
                e.get("gericht", ""),
                e.get("adresse", ""),
                e.get("versteigerung", ""),
                e.get("mindestgebot", ""),
                a.get("objekt_art", "—"),
                a.get("flaeche", "—"),
                a.get("baujahr", "—"),
                a.get("zustand", "—"),
                a.get("verkehrswert", "—"),
                str(a.get("investitions_score", "—")),
                a.get("risiko_klasse", "—"),
                a.get("rendite_potenzial", "—"),
                a.get("empfehlung", "—"),
                a.get("zusammenfassung", "—"),
            ])
        self.overview_model.set_rows(rows)


class OverviewModel(QAbstractTableModel):
    def __init__(self, cols: list[str]):
        super().__init__()
        self._cols = cols
        self._rows: list[list] = []

    def set_rows(self, rows):
        self._rows = rows
        self.layoutChanged.emit()

    def rowCount(self, _=QModelIndex()): return len(self._rows)
    def columnCount(self, _=QModelIndex()): return len(self._cols)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._cols[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        val = self._rows[index.row()][index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return val
        if role == Qt.ItemDataRole.ForegroundRole:
            col_name = self._cols[index.column()]
            if col_name == "Empfehlung":
                return QBrush(QColor(EMPFEHLUNG_COLORS.get(val, "#94a3b8")))
            if col_name == "Score":
                try:
                    s = float(val)
                    c = "#16a34a" if s >= 7 else "#d97706" if s >= 4 else "#dc2626"
                    return QBrush(QColor(c))
                except Exception:
                    pass
            if col_name == "Risiko":
                mapping = {
                    "Sehr Niedrig": "#16a34a", "Niedrig": "#4ade80",
                    "Mittel": "#d97706", "Hoch": "#f97316", "Sehr Hoch": "#dc2626",
                }
                return QBrush(QColor(mapping.get(val, "#94a3b8")))
            if col_name == "Rendite":
                mapping = {
                    "Sehr Hoch": "#16a34a", "Hoch": "#4ade80",
                    "Mittel": "#d97706", "Niedrig": "#f97316", "Negativ": "#dc2626",
                }
                return QBrush(QColor(mapping.get(val, "#94a3b8")))
        return None


# ══════════════════════════════════════════════════════════════
#  Main Window
# ══════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EdikteFinder Analyzer")
        self.resize(1400, 860)
        self._workers: list[Worker] = []
        self._build_ui()
        self._load_table()

    def _build_ui(self):
        # ── Toolbar ──────────────────────────────────────────
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setStyleSheet("QToolBar { background: #161b27; border-bottom: 1px solid #1e293b; padding: 4px 8px; spacing: 6px; }")
        self.addToolBar(tb)

        lbl_brand = QLabel("  ⚖  EdikteFinder <b style='color:#818cf8'>Analyzer</b>  ")
        lbl_brand.setStyleSheet("font-size: 15px; color: #e2e8f0; padding-right: 12px; border-right: 1px solid #1e293b;")
        tb.addWidget(lbl_brand)

        sp = QWidget(); sp.setFixedWidth(8)
        tb.addWidget(sp)

        self.btn_settings = QPushButton("⚙  Einstellungen")
        self.btn_settings.clicked.connect(self._open_settings)
        tb.addWidget(self.btn_settings)

        sp2 = QWidget(); sp2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(sp2)

        self.lbl_provider = QLabel()
        self._update_provider_label()
        self.lbl_provider.setStyleSheet("color: #64748b; font-size: 12px; padding-right: 8px;")
        tb.addWidget(self.lbl_provider)

        # ── Tabs ──────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)

        # Tab 1: Suche & Ergebnisse
        self.search_tab = QWidget()
        self.tabs.addTab(self.search_tab, "🔍  Suche & Ergebnisse")
        self._build_search_tab()

        # Tab 2: Übersicht
        self.overview_tab = OverviewTab()
        self.tabs.addTab(self.overview_tab, "📊  Investitions-Übersicht")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        # ── Status Bar ────────────────────────────────────────
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Bereit.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(160)
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)
        self.status.addPermanentWidget(self.progress_bar)

    def _build_search_tab(self):
        layout = QHBoxLayout(self.search_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # ── LEFT: Search Panel ────────────────────────────────
        left = QWidget()
        left.setFixedWidth(290)
        left.setStyleSheet("background: #161b27; border-right: 1px solid #1e293b;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 16, 16, 16)
        ll.setSpacing(10)

        lbl_title = QLabel("SUCHOPTIONEN")
        lbl_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        ll.addWidget(lbl_title)

        # Mode selector
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Einfache Suche", "Aktenzeichen", "Erweiterte Suche"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        ll.addWidget(self.mode_combo)

        # Stacked forms
        self.form_stack = QStackedWidget()
        ll.addWidget(self.form_stack)

        # Form: Einfach
        f_einfach = QWidget()
        fl = QFormLayout(f_einfach)
        fl.setSpacing(8)
        self.f_kategorie  = QComboBox(); self.f_kategorie.addItems(["", "Eigenheim", "Eigentumswohnung", "Gewerbeimmobilie", "Grundstück", "Landwirtschaft", "Sonstige"]); self.f_kategorie.setPlaceholderText("Alle Kategorien")
        self.f_ort        = QLineEdit(); self.f_ort.setPlaceholderText("z.B. Wien, Graz …")
        self.f_plz        = QLineEdit(); self.f_plz.setPlaceholderText("z.B. 1010")
        self.f_bundesland = QComboBox(); self.f_bundesland.addItems(["", "Wien", "Niederösterreich", "Oberösterreich", "Steiermark", "Tirol", "Salzburg", "Kärnten", "Vorarlberg", "Burgenland"])
        self.f_seit       = QComboBox(); self.f_seit.addItems(["", "Heute", "Gestern", "Letzte 7 Tage", "Letzte 14 Tage", "Letzte 30 Tage"])
        fl.addRow("Kategorie:", self.f_kategorie)
        fl.addRow("Ort:", self.f_ort)
        fl.addRow("PLZ:", self.f_plz)
        fl.addRow("Bundesland:", self.f_bundesland)
        fl.addRow("Seit:", self.f_seit)
        self.form_stack.addWidget(f_einfach)

        # Form: Aktenzeichen
        f_az = QWidget()
        fl_az = QFormLayout(f_az)
        fl_az.setSpacing(8)
        self.f_aktenzeichen = QLineEdit(); self.f_aktenzeichen.setPlaceholderText("z.B. 3 E 456/23w")
        self.f_gericht_az   = QComboBox(); self.f_gericht_az.addItems(["", "BG Döbling", "BG Favoriten", "BG Floridsdorf", "BG Graz-West", "BG Innsbruck", "BG Klagenfurt", "BG Linz", "BG Salzburg"])
        fl_az.addRow("Aktenzeichen:", self.f_aktenzeichen)
        fl_az.addRow("Gericht:", self.f_gericht_az)
        self.form_stack.addWidget(f_az)

        # Form: Erweitert
        f_erw = QWidget()
        fl_e = QFormLayout(f_erw)
        fl_e.setSpacing(8)
        self.e_kategorie  = QComboBox(); self.e_kategorie.addItems(["", "Eigenheim", "Eigentumswohnung", "Gewerbeimmobilie", "Grundstück", "Landwirtschaft"])
        self.e_ort        = QLineEdit(); self.e_ort.setPlaceholderText("Ort")
        self.e_plz        = QLineEdit(); self.e_plz.setPlaceholderText("PLZ")
        self.e_bundesland = QComboBox(); self.e_bundesland.addItems(["", "Wien", "Niederösterreich", "Oberösterreich", "Steiermark", "Tirol", "Salzburg", "Kärnten", "Vorarlberg", "Burgenland"])
        self.e_gericht    = QComboBox(); self.e_gericht.addItems(["", "BG Döbling", "BG Favoriten", "BG Floridsdorf", "BG Graz-West", "BG Innsbruck", "BG Klagenfurt", "BG Linz", "BG Salzburg"])
        self.e_seit       = QComboBox(); self.e_seit.addItems(["", "Heute", "Gestern", "Letzte 7 Tage", "Letzte 30 Tage"])
        self.e_freitext   = QLineEdit(); self.e_freitext.setPlaceholderText("Freitext-Stichwort")
        fl_e.addRow("Kategorie:", self.e_kategorie)
        fl_e.addRow("Ort:", self.e_ort)
        fl_e.addRow("PLZ:", self.e_plz)
        fl_e.addRow("Bundesland:", self.e_bundesland)
        fl_e.addRow("Gericht:", self.e_gericht)
        fl_e.addRow("Seit:", self.e_seit)
        fl_e.addRow("Freitext:", self.e_freitext)
        self.form_stack.addWidget(f_erw)

        self.btn_search = QPushButton("🔍  Suchen")
        self.btn_search.setObjectName("btn_primary")
        self.btn_search.setFixedHeight(36)
        self.btn_search.clicked.connect(self._do_search)
        ll.addWidget(self.btn_search)

        ll.addSpacing(12)

        # Bulk actions section
        lbl_bulk = QLabel("MASSENAKTIONEN")
        lbl_bulk.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        ll.addWidget(lbl_bulk)

        self.btn_select_all = QPushButton("Alle auswählen")
        self.btn_select_all.clicked.connect(self._select_all)
        ll.addWidget(self.btn_select_all)

        self.btn_bulk_download = QPushButton("⬇  Gutachten laden (Auswahl)")
        self.btn_bulk_download.clicked.connect(self._bulk_download)
        ll.addWidget(self.btn_bulk_download)

        self.btn_bulk_analyze = QPushButton("✦  KI-Analyse (Auswahl)")
        self.btn_bulk_analyze.setObjectName("btn_success")
        self.btn_bulk_analyze.clicked.connect(self._bulk_analyze)
        ll.addWidget(self.btn_bulk_analyze)

        ll.addStretch()

        # ── MIDDLE: Results Table ─────────────────────────────
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        self.lbl_count = QLabel(" 0 Einträge")
        self.lbl_count.setStyleSheet("color: #64748b; font-size: 12px; padding: 8px 12px; background: #161b27; border-bottom: 1px solid #1e293b;")
        ml.addWidget(self.lbl_count)

        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.edikt_model = EdikteModel()
        self.table.setModel(self.edikt_model)
        self.table.clicked.connect(self._on_row_clicked)
        self.table.setColumnWidth(0, 36)
        ml.addWidget(self.table, 1)

        # ── RIGHT: Detail Panel ───────────────────────────────
        self.detail_panel = DetailPanel()
        self.detail_panel.setMinimumWidth(300)
        self.detail_panel.request_download.connect(self._download_single)
        self.detail_panel.request_analyze.connect(self._analyze_single)

        splitter.addWidget(left)
        splitter.addWidget(mid)
        splitter.addWidget(self.detail_panel)
        splitter.setSizes([290, 760, 340])

    # ── Helpers ────────────────────────────────────────────────

    def _update_provider_label(self):
        self.lbl_provider.setText(
            f"KI: {config.AI_PROVIDER.upper()}  ·  {getattr(config, config.AI_PROVIDER.upper() + '_MODEL', '—')}"
            if hasattr(config, config.AI_PROVIDER.upper() + '_MODEL')
            else f"KI: {config.AI_PROVIDER.upper()}"
        )

    def _load_table(self):
        self.edikt_model.load()
        count = self.edikt_model.rowCount()
        self.lbl_count.setText(f" {count} Einträge")

    def _set_busy(self, busy: bool, msg: str = ""):
        self.progress_bar.setVisible(busy)
        self.btn_search.setEnabled(not busy)
        if msg:
            self.status.showMessage(msg)

    def _on_mode_changed(self, idx: int):
        self.form_stack.setCurrentIndex(idx)

    def _on_tab_changed(self, idx: int):
        if idx == 1:
            self.overview_tab.refresh()

    def _on_row_clicked(self, index):
        row = index.row()
        edikt = self.edikt_model.edikt_at(row)
        self.detail_panel.show_edikt(edikt)

    def _select_all(self):
        all_selected = len(self.edikt_model.selected_ids()) == self.edikt_model.rowCount()
        self.edikt_model.select_all(not all_selected)

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._update_provider_label()

    # ── Search ─────────────────────────────────────────────────

    def _do_search(self):
        mode_map = {0: "einfach", 1: "aktenzeichen", 2: "erweitert"}
        mode = mode_map[self.mode_combo.currentIndex()]

        params = {"mode": mode}
        if mode == "einfach":
            params.update({
                "kategorie":  self.f_kategorie.currentText(),
                "ort":        self.f_ort.text().strip(),
                "plz":        self.f_plz.text().strip(),
                "bundesland": self.f_bundesland.currentText(),
                "seit":       self.f_seit.currentText(),
            })
        elif mode == "aktenzeichen":
            params.update({
                "aktenzeichen": self.f_aktenzeichen.text().strip(),
                "gericht":      self.f_gericht_az.currentText(),
            })
        else:
            params.update({
                "kategorie":  self.e_kategorie.currentText(),
                "ort":        self.e_ort.text().strip(),
                "plz":        self.e_plz.text().strip(),
                "bundesland": self.e_bundesland.currentText(),
                "gericht":    self.e_gericht.currentText(),
                "seit":       self.e_seit.currentText(),
                "freitext":   self.e_freitext.text().strip(),
            })

        self._set_busy(True, "Suche läuft – Detail-Seiten werden nachgeladen, bitte warten …")

        async def _run():
            from scraper import EdikteScraper
            async with EdikteScraper() as sc:
                return await sc.search(params)

        w = Worker(_run())
        w.finished.connect(self._on_search_done)
        w.error.connect(self._on_error)
        w.finished.connect(lambda _: self._workers.remove(w) if w in self._workers else None)
        w.error.connect(lambda _: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _on_search_done(self, results: list):
        ids = storage.save_edikte_bulk(results)
        self._load_table()
        self._set_busy(False, f"✓  {len(results)} Ergebnisse gefunden und gespeichert.")

    # ── Download ───────────────────────────────────────────────

    def _download_single(self, edikt_id: str):
        self._do_download([edikt_id])

    def _bulk_download(self):
        ids = self.edikt_model.selected_ids()
        if not ids:
            self.status.showMessage("Keine Einträge ausgewählt.")
            return
        self._do_download(ids)

    def _do_download(self, edikt_ids: list[str]):
        self._set_busy(True, f"Lade {len(edikt_ids)} Gutachten herunter …")

        async def _run():
            from scraper import EdikteScraper
            results = []
            async with EdikteScraper() as sc:
                for eid in edikt_ids:
                    edikt = storage.get_edikt(eid)
                    if not edikt:
                        continue
                    pdf_path = await sc.download_gutachten(edikt["detail_url"], eid)
                    if pdf_path:
                        pdf_text = ai_analyzer.extract_pdf_text(Path(pdf_path))
                        storage.update_edikt_field(eid, status="downloaded",
                                                   pdf_text_preview=pdf_text[:500])
                        results.append(eid)
            return results

        w = Worker(_run())
        w.finished.connect(lambda ids: self._on_download_done(ids))
        w.error.connect(self._on_error)
        w.finished.connect(lambda _: self._workers.remove(w) if w in self._workers else None)
        w.error.connect(lambda _: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _on_download_done(self, ids: list):
        self._load_table()
        self._set_busy(False, f"✓  {len(ids)} Gutachten heruntergeladen.")

    # ── Analyze ────────────────────────────────────────────────

    def _analyze_single(self, edikt_id: str):
        self._do_analyze([edikt_id])

    def _bulk_analyze(self):
        ids = self.edikt_model.selected_ids()
        if not ids:
            self.status.showMessage("Keine Einträge ausgewählt.")
            return
        self._do_analyze(ids)

    def _do_analyze(self, edikt_ids: list[str]):
        self._set_busy(True, f"KI-Analyse startet für {len(edikt_ids)} Einträge …")

        async def _run():
            done = 0
            for eid in edikt_ids:
                edikt = storage.get_edikt(eid)
                if not edikt:
                    continue
                pdf_path = storage.pdf_path_for(eid)
                if pdf_path.exists():
                    text = ai_analyzer.extract_pdf_text(pdf_path)
                else:
                    # Analyse nur auf Metadaten
                    text = " ".join(filter(None, [
                        edikt.get("titel", ""), edikt.get("beschreibung", ""),
                        edikt.get("adresse", ""),
                    ]))
                try:
                    result = await ai_analyzer.analyze(text, edikt)
                    storage.save_analysis(eid, result)
                    storage.update_edikt_field(eid, status="analyzed")
                    done += 1
                except Exception as e:
                    storage.update_edikt_field(eid, status="analyze_error")
            return done

        w = Worker(_run())
        w.finished.connect(lambda n: self._on_analyze_done(n))
        w.error.connect(self._on_error)
        w.finished.connect(lambda _: self._workers.remove(w) if w in self._workers else None)
        w.error.connect(lambda _: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w)
        w.start()

    def _on_analyze_done(self, count: int):
        self._load_table()
        self._set_busy(False, f"✓  {count} Analysen abgeschlossen.")

    # ── Error ──────────────────────────────────────────────────

    def _on_error(self, msg: str):
        self._set_busy(False)
        self.status.showMessage(f"⚠  Fehler: {msg}")
        QMessageBox.critical(self, "Fehler", msg)


# ══════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EdikteFinder Analyzer")
    app.setStyleSheet(DARK_STYLE)

    # Font via stylesheet – avoids QFont DPI-warning on some Windows setups
    pass

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
