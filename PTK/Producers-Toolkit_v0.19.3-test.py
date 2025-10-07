# ============================================================
# Producer's Toolkit — Version 0.19.3-test
# ============================================================
# Based on your uploaded v0.19.2 baseline, with:
#   - Unified 12 pt font for all widgets
#   - Compact card layout (tighter spacing, subtle shadow)
#   - Last-used-directory tracking saved in settings.json
#   - Deep line-by-line comments
# ============================================================

from __future__ import annotations

import sys, os, json, tempfile
from datetime import datetime
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QFrame, QTableWidget,
    QTableWidgetItem, QMessageBox, QDialog, QTabWidget, QTextBrowser,
    QGraphicsDropShadowEffect
)

# optional QtPDF viewer
try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
    QT_PDF_AVAILABLE = True
except ImportError:
    QT_PDF_AVAILABLE = False

# ------------------------------------------------------------
# Visual constants
# ------------------------------------------------------------
CARD_BG = "#F5F5F5"        # light gray card background
CARD_RADIUS = 10
CARD_PADDING = 4           # compact internal padding
CARD_SHADOW_BLUR = 18
CARD_SHADOW_OFFSET = (0, 2)
TEXT_COLOR = "#202020"

# settings file for last-used-directory tracking
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".producers_toolkit_settings.json")


# ------------------------------------------------------------
# ProducersToolkit main window class
# ------------------------------------------------------------
class ProducersToolkit(QMainWindow):
    """Main application window."""

    def __init__(self):
        """Initialize the window and all persistent state."""
        super().__init__()

        # window title now includes version tag
        self.setWindowTitle("Producer's Toolkit — v0.19.3-test")
        self.resize(1200, 800)

        # >>> NEW: variable to remember the last directory used by file dialogs
        self.last_dir = self._load_last_directory()

        # build all UI widgets and layouts
        self._build_ui()

    # --------------------------------------------------------
    # >>> NEW: Load last-used directory from settings.json
    # --------------------------------------------------------
    def _load_last_directory(self) -> str:
        """Return the last directory path stored in SETTINGS_FILE or fallback."""
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("last_dir", os.path.expanduser("~/Documents"))
        except Exception as e:
            print(f"Warning: could not load settings ({e})")
        return os.path.expanduser("~/Documents")

    # --------------------------------------------------------
    # >>> NEW: Save last-used directory to settings.json
    # --------------------------------------------------------
    def _save_last_directory(self, path: str):
        """Write the given directory path to SETTINGS_FILE for persistence."""
        try:
            data = {"last_dir": path}
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: could not save settings ({e})")

    # --------------------------------------------------------
    # Helper: system UI font
    # --------------------------------------------------------
    def _system_ui_font(self, size: int = 12, bold: bool = False, italic: bool = False):
        """Return a platform-appropriate system font with given styling."""
        if sys.platform == "win32":
            family = "Segoe UI"
        elif sys.platform == "darwin":
            family = "San Francisco"
        else:
            family = "Ubuntu"
        font = QFont(family, size)
        font.setBold(bold)
        font.setItalic(italic)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font

    # --------------------------------------------------------
    # Helper: make a soft "card" container
    # --------------------------------------------------------
    def _make_card(self):
        """Create and return a QFrame styled as a rounded, shadowed card."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {CARD_BG};
                border-radius: {CARD_RADIUS}px;
                padding: {CARD_PADDING}px;
            }}
            """
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(CARD_SHADOW_BLUR)
        shadow.setOffset(*CARD_SHADOW_OFFSET)
        shadow.setColor(QColor(0, 0, 0, 60))
        frame.setGraphicsEffect(shadow)
        return frame

    # --------------------------------------------------------
    # Build all widgets and layout
    # --------------------------------------------------------
    def _build_ui(self):
        """Construct the full interface layout."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)  # tighter vertical spacing between cards

        # ----------------------------------------------------
        # Global control cards section
        # ----------------------------------------------------
        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        # 1️⃣ Card A: Timing Controls
        self.card_timing = self._make_card()
        timing_layout = QHBoxLayout(self.card_timing)
        top_row.addWidget(self.card_timing)

        lbl_start = QLabel("Start Time:")
        lbl_start.setFont(self._system_ui_font(12, bold=True))
        timing_layout.addWidget(lbl_start)

        self.start_time_input = QComboBox()
        self.start_time_input.setFont(self._system_ui_font(12))
        self.start_time_input.addItems([f"{h:02}:00" for h in range(0, 24)])
        self.start_time_input.setCurrentText("08:00")
        timing_layout.addWidget(self.start_time_input)

        lbl_lunch = QLabel("Lunch (hrs):")
        lbl_lunch.setFont(self._system_ui_font(12, bold=True))
        timing_layout.addWidget(lbl_lunch)

        self.lunch_fixed_spin = QSpinBox()
        self.lunch_fixed_spin.setFont(self._system_ui_font(12))
        self.lunch_fixed_spin.setRange(0, 12)
        self.lunch_fixed_spin.setValue(1)
        timing_layout.addWidget(self.lunch_fixed_spin)

        # 2️⃣ Card B: Calculation Controls (will continue in Part 2)
        self.card_calc = self._make_card()
        calc_layout = QHBoxLayout(self.card_calc)
        top_row.addWidget(self.card_calc)

        lbl_wpp = QLabel("Words per Page:")
        lbl_wpp.setFont(self._system_ui_font(12, bold=True))
        calc_layout.addWidget(lbl_wpp)

        self.wpp_spin = QSpinBox()
        self.wpp_spin.setFont(self._system_ui_font(12))
        self.wpp_spin.setRange(100, 400)
        self.wpp_spin.setValue(150)
        calc_layout.addWidget(self.wpp_spin)

        lbl_setup = QLabel("LX & Camera Setup (min):")
        lbl_setup.setFont(self._system_ui_font(12, bold=True))
        calc_layout.addWidget(lbl_setup)

        self.setup_minutes_spin = QSpinBox()
        self.setup_minutes_spin.setFont(self._system_ui_font(12))
        self.setup_minutes_spin.setRange(1, 60)
        self.setup_minutes_spin.setValue(5)
        calc_layout.addWidget(self.setup_minutes_spin)

        # continue with additional global controls in Part 2


# part 2 here  ↓
















        # ----------------------------------------------------
        # Finish building the Timing Card with Auto Lunch toggle
        # ----------------------------------------------------
        self.auto_lunch_toggle = QCheckBox("Auto Lunch Timing")
        self.auto_lunch_toggle.setFont(self._system_ui_font(12))
        self.auto_lunch_toggle.setChecked(True)  # default on (auto)
        timing_layout.addWidget(self.auto_lunch_toggle)

        # spacer to keep layout tidy
        timing_layout.addStretch()

    # --------------------------------------------------------
    # Insert or update lunch row (auto/fixed)
    # --------------------------------------------------------
    def _insert_or_update_lunch_row(self, start_time, total_minutes):
        """
        Create or update the lunch row depending on auto/fixed mode.
        The lunch appears visually between scenes, centered on the correct time.
        """
        lunch_duration = self.lunch_fixed_spin.value() * 60  # hours → minutes
        auto_mode = self.auto_lunch_toggle.isChecked()

        # Determine when lunch starts
        if auto_mode:
            lunch_start_minute = 6 * 60  # auto after ~6 hours
        else:
            lunch_start_minute = self.lunch_fixed_spin.value() * 60

        # Find where to insert it among scenes
        lunch_row_index = None
        running_time = 0
        for r in range(self.table.rowCount()):
            end_text = self.table.item(r, 6).text()
            if end_text == "—":
                continue
            try:
                end_time = datetime.strptime(end_text, "%H:%M")
                elapsed = (end_time - start_time).total_seconds() / 60
                running_time = elapsed
                if running_time >= lunch_start_minute:
                    lunch_row_index = r + 1
                    break
            except Exception:
                continue

        # default to middle or end if not found
        if lunch_row_index is None:
            lunch_row_index = self.table.rowCount() // 2

        # remove any existing lunch rows before reinserting
        for r in reversed(range(self.table.rowCount())):
            item = self.table.item(r, 0)
            if item and "LUNCH" in item.text().upper():
                self.table.removeRow(r)

        # insert a single merged lunch row
        self.table.insertRow(lunch_row_index)
        self.table.setSpan(lunch_row_index, 0, 1, self.table.columnCount())

        start_dt = start_time + timedelta(minutes=lunch_start_minute)
        end_dt = start_dt + timedelta(minutes=lunch_duration)
        text = f"LUNCH BREAK — {start_dt.strftime('%H:%M')} to {end_dt.strftime('%H:%M')}  ({lunch_duration:.0f} min)"
        item = QTableWidgetItem(text)
        item.setFont(self._system_ui_font(12, bold=True))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(lunch_row_index, 0, item)
        self.table.item(lunch_row_index, 0).setBackground(QColor("#FFD580"))

    # --------------------------------------------------------
    # Export handlers
    # --------------------------------------------------------
    def export_files(self):
        """Placeholder export for CSV/PDF."""
        QMessageBox.information(self, "Export", "Export logic placeholder")

    # --------------------------------------------------------
    # Badge-style helper (unchanged)
    # --------------------------------------------------------
    def _badge_style(self, bg_color):
        """Return CSS for a rounded badge."""
        return f"background-color:{bg_color};color:#000;border-radius:10px;padding:2px 8px;"

    # --------------------------------------------------------
    # Timestamp label updater
    # --------------------------------------------------------
    def _update_last_recalc_timestamp(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.last_recalc_label.setText(f"Last recalculated: {now}")

    # --------------------------------------------------------
    # Preview modal with QtPDF auto-load
    # --------------------------------------------------------
    def open_preview_modal(self):
        """Show multi-page preview for CSV and PDF exports."""
        tempdir = tempfile.gettempdir()
        csv_path = os.path.join(tempdir, "preview.csv")
        pdf_path = os.path.join(tempdir, "preview.pdf")

        dlg = QDialog(self)
        dlg.setWindowTitle("Preview — Producer's Toolkit")
        dlg.resize(900, 700)
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # CSV tab
        csv_tab = QWidget()
        csv_layout = QVBoxLayout(csv_tab)
        csv_browser = QTextBrowser()
        csv_browser.setFont(self._system_ui_font(12))
        csv_browser.setText("CSV preview placeholder")
        csv_layout.addWidget(csv_browser)
        tabs.addTab(csv_tab, "CSV Preview")

        # PDF tab
        pdf_tab = QWidget()
        pdf_layout = QVBoxLayout(pdf_tab)
        if QT_PDF_AVAILABLE:
            try:
                self._pdf_doc = QPdfDocument()
                self._pdf_doc.load(pdf_path)
                self._pdf_view = QPdfView()
                self._pdf_view.setDocument(self._pdf_doc)
                self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
                pdf_layout.addWidget(self._pdf_view)
            except Exception as e:
                pdf_layout.addWidget(QLabel(f"PDF preview error: {e}"))
        else:
            pdf_layout.addWidget(QLabel("QtPDF not installed — no live preview."))
        tabs.addTab(pdf_tab, "PDF Preview")

        # Buttons
        btns = QHBoxLayout()
        layout.addLayout(btns)
        btns.addStretch()
        open_btn = QPushButton("Open in Default App")
        open_btn.setFont(self._system_ui_font(12))
        btns.addWidget(open_btn)
        close_btn = QPushButton("Close Preview")
        close_btn.setFont(self._system_ui_font(12))
        btns.addWidget(close_btn)

        def _open_external():
            try:
                if sys.platform.startswith("win"):
                    os.startfile(pdf_path)
                elif sys.platform == "darwin":
                    os.system(f"open '{pdf_path}'")
                else:
                    os.system(f"xdg-open '{pdf_path}'")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open PDF: {e}")

        open_btn.clicked.connect(_open_external)
        close_btn.clicked.connect(dlg.close)
        dlg.exec()

# ------------------------------------------------------------
# Application entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProducersToolkit()
    window.show()
    sys.exit(app.exec())
# ------------------------------------------------------------
# END OF FILE
# ------------------------------------------------------------
