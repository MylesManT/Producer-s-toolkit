# ------------------------------------------------------------
# Producers-Toolkit_v0.20.4b-release.py
# ------------------------------------------------------------
# Version: v0.20.4b-release
#
# Requirements:
#      Python 3.12+
#      PyQt6 (core)
#      PyQt6-QtPdf, PyQt6-QtPdfWidgets (optional but recommended for PDF preview)
#      reportlab (for PDF export)
#
# ------------------------------------------------------------

# ------------------------
# Standard library imports
# ------------------------
import sys
import os
import json
import re
import csv
import tempfile
import uuid
from datetime import timedelta, datetime

# ------------------------
# PyQt6 imports: widgets, core, gui
# ------------------------
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLabel, QSpinBox, QCheckBox,
    QMessageBox, QFileDialog, QGraphicsOpacityEffect, QGraphicsDropShadowEffect,
    QFrame, QDialog, QTabWidget, QTextBrowser
)
from PyQt6.QtCore import Qt, QPropertyAnimation
from PyQt6.QtGui import QBrush, QColor, QFont

# ------------------------
# Optional QtPDF imports
# ------------------------
try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
    QT_PDF_AVAILABLE = True
except Exception:
    QT_PDF_AVAILABLE = False

# ------------------------
# reportlab imports for PDF export
# ------------------------
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ------------------------
# Defaults and UI constants
# ------------------------
DEFAULTS = {
    "words_per_page": 150,
    "setup_minutes": 5,
    "setups_int": 3,
    "setups_ext": 5,
    "default_move_duration": 10,
    "default_lunch_duration": 60,
    "default_start_time": "08:00"
}

FADE_DURATION_MS = 500
CARD_BG = "#f8f9fb"
CARD_PADDING = 6
CARD_RADIUS = 6
CARD_SHADOW_BLUR = 12
CARD_SHADOW_OFFSET = (0, 3)
SETTINGS_FILE = "settings.json"

# ------------------------------------------------------------
# Main application window class
# ------------------------------------------------------------
class ProducersToolkit(QMainWindow):
    """
    Main application window for Producer's Toolkit v0.20.4b-release.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Producer's Toolkit v0.20.4b-release")
        self.resize(1400, 900)

        # Internal application state
        self.scenes = []
        self.current_fountain_path = ""
        self.words_per_page = DEFAULTS["words_per_page"]
        self.setup_minutes = DEFAULTS["setup_minutes"]

        # Build the UI components and layout
        self._build_ui()

        # Load settings from disk if present
        self._load_settings()

    # --------------------------------------------------------
    # Cross-platform system UI font helper with antialiasing
    # --------------------------------------------------------
    def _system_ui_font(self, size=12, bold=False, italic=False):
        platform = sys.platform
        if platform.startswith("win"):
            family = "Segoe UI"
        elif platform == "darwin":
            family = ".AppleSystemUIFont"
        else:
            family = "Noto Sans"

        font = QFont(family, size)
        if bold:
            font.setBold(True)
        if italic:
            font.setItalic(True)

        try:
            font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        except Exception:
            pass

        return font
    
    # --------------------------------------------------------
    # Helper: create a card-styled QFrame with drop shadow
    # --------------------------------------------------------
    def _make_card(self):
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
    # UI builder: constructs and arranges all widgets
    # --------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)

        # Top row - Timing card
        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        label_font = self._system_ui_font(12, bold=True)

        self.card_timing = self._make_card()
        timing_layout = QHBoxLayout(self.card_timing)
        top_row.addWidget(self.card_timing)

        lbl_start = QLabel("Start Time:")
        lbl_start.setFont(label_font)
        timing_layout.addWidget(lbl_start)
        self.start_time_input = QComboBox()
        self.start_time_input.setFont(self._system_ui_font(12))
        times = [f"{h:02}:{m:02}" for h in range(24) for m in (0, 15, 30, 45)]
        self.start_time_input.addItems(times)
        self.start_time_input.setCurrentText(DEFAULTS["default_start_time"])
        self.start_time_input.view().setMinimumWidth(100)
        timing_layout.addWidget(self.start_time_input)
        timing_layout.addStretch()

        # Mid row - Moves and lunch controls
        mid_row = QHBoxLayout()
        layout.addLayout(mid_row)
        
        self.card_moves = self._make_card()
        moves_layout = QHBoxLayout(self.card_moves)
        mid_row.addWidget(self.card_moves)
        
        lbl_lunch = QLabel("Lunch Duration (min):")
        lbl_lunch.setFont(label_font)
        moves_layout.addWidget(lbl_lunch)
        self.lunch_duration_input = QComboBox()
        self.lunch_duration_input.setFont(self._system_ui_font(12))
        self.lunch_duration_input.addItems([str(i) for i in range(0, 181)])
        self.lunch_duration_input.setCurrentText(str(DEFAULTS["default_lunch_duration"]))
        self.lunch_duration_input.view().setMinimumWidth(80)
        moves_layout.addWidget(self.lunch_duration_input)

        # Lunch mode toggle
        self.auto_lunch_toggle = QCheckBox("Auto Lunch Timing")
        self.auto_lunch_toggle.setFont(self._system_ui_font(12))
        self.auto_lunch_toggle.setChecked(True)
        self.auto_lunch_toggle.stateChanged.connect(self.lunch_mode_changed)
        moves_layout.addWidget(self.auto_lunch_toggle)

        # Fixed lunch hours
        lbl_fixed = QLabel("Fixed after (hours):")
        lbl_fixed.setFont(label_font)
        moves_layout.addWidget(lbl_fixed)
        self.lunch_fixed_spin = QSpinBox()
        self.lunch_fixed_spin.setRange(1, 12)
        self.lunch_fixed_spin.setValue(6)
        self.lunch_fixed_spin.setFont(self._system_ui_font(12))
        self.lunch_fixed_spin.valueChanged.connect(self.lunch_fixed_hours_changed)
        moves_layout.addWidget(self.lunch_fixed_spin)

        moves_layout.addSpacing(20)

        # Company moves
        lbl_moves = QLabel("Company moves:")
        lbl_moves.setFont(label_font)
        moves_layout.addWidget(lbl_moves)
        self.company_moves_input = QComboBox()
        self.company_moves_input.addItems([str(i) for i in range(0, 21)])
        self.company_moves_input.setFont(self._system_ui_font(12))
        self.company_moves_input.view().setMinimumWidth(60)
        moves_layout.addWidget(self.company_moves_input)

        lbl_move_dur = QLabel("Company Move Duration (min):")
        lbl_move_dur.setFont(label_font)
        moves_layout.addWidget(lbl_move_dur)
        self.move_duration_input = QComboBox()
        self.move_duration_input.setFont(self._system_ui_font(12))
        self.move_duration_input.addItems([str(i) for i in range(0, 121)])
        self.move_duration_input.setCurrentText(str(DEFAULTS["default_move_duration"]))
        self.move_duration_input.view().setMinimumWidth(80)
        moves_layout.addWidget(self.move_duration_input)

        self.include_moves_lunch_toggle = QCheckBox("Calculate with Moves && Lunch")
        self.include_moves_lunch_toggle.setFont(self._system_ui_font(12))
        self.include_moves_lunch_toggle.setChecked(True)
        moves_layout.addWidget(self.include_moves_lunch_toggle)
        moves_layout.addStretch()

        # Calculation card
        self.card_calc = self._make_card()
        calc_layout = QHBoxLayout(self.card_calc)
        top_row.addWidget(self.card_calc)

        # Custom WPP toggle
        self.custom_wpp_toggle = QCheckBox("Use Custom WPP")
        self.custom_wpp_toggle.setFont(label_font)
        self.custom_wpp_toggle.stateChanged.connect(self.toggle_custom_wpp_changed)
        calc_layout.addWidget(self.custom_wpp_toggle)

        lbl_wpp = QLabel("Words per Page:")
        lbl_wpp.setFont(label_font)
        calc_layout.addWidget(lbl_wpp)
        self.wpp_spin = QSpinBox()
        self.wpp_spin.setFont(self._system_ui_font(12))
        self.wpp_spin.setRange(100, 250)
        self.wpp_spin.setValue(150)
        self.wpp_spin.setEnabled(False)
        self.wpp_spin.valueChanged.connect(self.wpp_value_changed)
        calc_layout.addWidget(self.wpp_spin)

        lbl_setup = QLabel("LX & Camera Setup (min):")
        lbl_setup.setFont(label_font)
        calc_layout.addWidget(lbl_setup)
        self.setup_minutes_spin = QSpinBox()
        self.setup_minutes_spin.setFont(self._system_ui_font(12))
        self.setup_minutes_spin.setRange(1, 60)
        self.setup_minutes_spin.setValue(5)
        self.setup_minutes_spin.valueChanged.connect(self.setup_minutes_changed)
        calc_layout.addWidget(self.setup_minutes_spin)

        # Lock setups toggle
        self.lock_setups_toggle = QCheckBox("Lock Default Setups (INT=3, EXT=5)")
        self.lock_setups_toggle.setFont(label_font)
        self.lock_setups_toggle.stateChanged.connect(self.toggle_default_setups_lock)
        calc_layout.addWidget(self.lock_setups_toggle)

        # Actions card
        self.card_actions = self._make_card()
        act_layout = QHBoxLayout(self.card_actions)
        top_row.addWidget(self.card_actions)

        self.btn_load = QPushButton("Load Screenplay (.fountain) File")
        self.btn_load.setFont(self._system_ui_font(12, bold=True))
        self.btn_load.clicked.connect(self.load_fountain_file)
        act_layout.addWidget(self.btn_load)

        self.btn_recalc = QPushButton("Recalculate Schedule")
        self.btn_recalc.setFont(self._system_ui_font(12, bold=True))
        self.btn_recalc.clicked.connect(self._recalculate_and_feedback)
        act_layout.addWidget(self.btn_recalc)

        # Main table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Scene Heading", "Actions", "Dialogue",
            "Length (pages+1/8s)", "Length (MM:SS)",
            "Camera Setups (Count)", "Shooting Time (HH:MM:SS)"
        ])
        self.table.setFont(self._system_ui_font(12))
        # Enable automatic column resizing to fit content
        self.table.horizontalHeader().setStretchLastSection(True)
        from PyQt6.QtWidgets import QHeaderView
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        # Bottom row
        bottom_row = QHBoxLayout()
        layout.addLayout(bottom_row)
        
        self.last_recalc_label = QLabel("Last recalculated: --:--:--")
        self.last_recalc_label.setFont(self._system_ui_font(12, italic=True))
        bottom_row.addWidget(self.last_recalc_label)
        bottom_row.addStretch()

        # Preview and Export controls in bottom right
        #self.btn_preview = QPushButton("Preview")
        #self.btn_preview.setFont(self._system_ui_font(12, bold=True))
        #self.btn_preview.clicked.connect(self.open_preview_modal)
        #bottom_row.addWidget(self.btn_preview)

        self.export_dropdown = QComboBox()
        self.export_dropdown.addItems(["Export CSV", "Export PDF", "Export Both"])
        self.export_dropdown.setFont(self._system_ui_font(12))
        self.export_dropdown.view().setMinimumWidth(150)
        bottom_row.addWidget(self.export_dropdown)

        self.btn_export = QPushButton("Export")
        self.btn_export.setFont(self._system_ui_font(12, bold=True))
        self.btn_export.clicked.connect(self._export_with_save_warning)
        bottom_row.addWidget(self.btn_export)

    # ------------------------
    # SETTINGS: load saved preferences
    # ------------------------
    def _load_settings(self):
        if not os.path.exists(SETTINGS_FILE):
            return

        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)

            if s.get("custom_wpp", False):
                self.custom_wpp_toggle.setChecked(True)
                try:
                    val = int(s.get("words_per_page", DEFAULTS["words_per_page"]))
                except Exception:
                    val = DEFAULTS["words_per_page"]
                self.wpp_spin.setValue(val)
                self.wpp_spin.setEnabled(True)
                self.words_per_page = val
            else:
                self.custom_wpp_toggle.setChecked(False)
                self.wpp_spin.setEnabled(False)
                self.words_per_page = DEFAULTS["words_per_page"]

            if "setup_minutes" in s:
                try:
                    sm = int(s["setup_minutes"])
                except Exception:
                    sm = DEFAULTS["setup_minutes"]
                self.setup_minutes = sm
                self.setup_minutes_spin.setValue(sm)

            if "lunch_auto" in s:
                try:
                    self.auto_lunch_toggle.setChecked(bool(s["lunch_auto"]))
                except Exception:
                    self.auto_lunch_toggle.setChecked(True)

            if "lunch_fixed_hours" in s:
                try:
                    self.lunch_fixed_spin.setValue(int(s["lunch_fixed_hours"]))
                except Exception:
                    self.lunch_fixed_spin.setValue(6)

            if "lock_setups" in s:
                try:
                    self.lock_setups_toggle.setChecked(bool(s["lock_setups"]))
                except Exception:
                    self.lock_setups_toggle.setChecked(False)

        except Exception:
            return

    # ------------------------
    # SETTINGS: save preferences
    # ------------------------
    def _save_settings(self):
        try:
            data = {
                "custom_wpp": bool(self.custom_wpp_toggle.isChecked()),
                "words_per_page": int(self.wpp_spin.value()) if self.custom_wpp_toggle.isChecked() else DEFAULTS["words_per_page"],
                "setup_minutes": int(self.setup_minutes_spin.value()),
                "lunch_auto": bool(self.auto_lunch_toggle.isChecked()),
                "lunch_fixed_hours": int(self.lunch_fixed_spin.value()),
                "lock_setups": bool(self.lock_setups_toggle.isChecked())
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    # ------------------------
    # Words-per-page helper
    # ------------------------
    def get_current_wpp(self):
        if self.custom_wpp_toggle.isChecked():
            return int(self.wpp_spin.value())
        return int(DEFAULTS["words_per_page"])

    # ------------------------
    # WPP toggle change handler
    # ------------------------
    def toggle_custom_wpp_changed(self, state):
        if state:
            self.wpp_spin.setEnabled(True)
            self.words_per_page = int(self.wpp_spin.value())
        else:
            self.wpp_spin.setEnabled(False)
            self.words_per_page = DEFAULTS["words_per_page"]
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # WPP spinbox value handler
    # ------------------------
    def wpp_value_changed(self, val):
        try:
            self.words_per_page = int(val)
        except Exception:
            self.words_per_page = DEFAULTS["words_per_page"]
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Setup minutes change handler
    # ------------------------
    def setup_minutes_changed(self, val):
        try:
            self.setup_minutes = int(val)
        except Exception:
            self.setup_minutes = DEFAULTS["setup_minutes"]
        self.recalculate_schedule()

    # ------------------------
    # Lock default setups toggle handler
    # ------------------------
    def toggle_default_setups_lock(self, state):
        lock_on = bool(state)
        for r in range(self.table.rowCount()):
            widget = self.table.cellWidget(r, 5)
            if widget is not None:
                try:
                    if lock_on:
                        item = self.table.item(r, 0)
                        heading_text = item.text() if item else ""
                        if heading_text.upper().startswith("INT"):
                            widget.setCurrentText(str(DEFAULTS["setups_int"]))
                        else:
                            widget.setCurrentText(str(DEFAULTS["setups_ext"]))
                        widget.setEnabled(False)
                    else:
                        widget.setEnabled(True)
                except Exception:
                    continue
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Lunch mode changed handler
    # ------------------------
    def lunch_mode_changed(self, state):
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Fixed lunch hours changed handler
    # ------------------------
    def lunch_fixed_hours_changed(self, val):
        if not self.auto_lunch_toggle.isChecked():
            self.trigger_recalc_with_row_fades()

    # ------------------------
    # Load a Fountain file and populate table
    # ------------------------
    def load_fountain_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Fountain", "", "Fountain Files (*.fountain)")
        if not file_path:
            return

        self.current_fountain_path = file_path

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Could not read file: {e}")
            return

        self.scenes = self.parse_fountain(content)
        self.populate_table()

        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

    # ------------------------
    # Simple Fountain parser
    # ------------------------
    def parse_fountain(self, content):
        scenes = []
        current = None
        for line in content.splitlines():
            stripped = line.strip()
            if re.match(r"^(INT\.|EXT\.)", stripped, re.I):
                if current:
                    scenes.append(current)
                current = {"heading": stripped, "content": []}
            elif current is not None:
                current["content"].append(stripped)
        if current:
            scenes.append(current)
        return scenes

    # ------------------------
    # Scene page-length & mm:ss calculation
    # ------------------------
    def calculate_scene_length(self, scene_text):
        words = len(re.findall(r"\w+", " ".join(scene_text)))
        wpp = self.get_current_wpp()
        pages = (words / wpp) if wpp > 0 else 0.0
        full = int(pages)
        eighths = int(round((pages - full) * 8))
        if eighths == 8:
            full += 1
            eighths = 0
        if full == 0 and eighths > 0:
            page_str = f"{eighths}/8"
        elif eighths > 0:
            page_str = f"{full} {eighths}/8"
        else:
            page_str = f"{full}"
        seconds = int(round(pages * 60))
        mm, ss = divmod(seconds, 60)
        mmss = f"{mm:02}:{ss:02}"
        return page_str, mmss

    # ------------------------
    # Compute shooting time for a row
    # ------------------------
    def compute_scene_time(self, row):
        setups_widget = self.table.cellWidget(row, 5)
        length_item = self.table.item(row, 4)
        if setups_widget is None or length_item is None:
            return 0

        try:
            setups_val = int(setups_widget.currentText())
        except Exception:
            setups_val = 0

        try:
            mm, ss = map(int, length_item.text().split(":"))
        except Exception:
            mm, ss = 0, 0

        base_minutes = mm + ss / 60.0
        total_minutes = base_minutes + setups_val * self.setup_minutes
        return int(round(total_minutes * 60))

    # ------------------------
    # Handler when per-row setups combo changes
    # ------------------------
    def update_scene_row_for_box(self, box):
        idx = self.table.indexAt(box.pos())
        row = idx.row()
        if row == -1:
            for r in range(self.table.rowCount()):
                if self.table.cellWidget(r, 5) is box:
                    row = r
                    break
        if row == -1:
            return

        secs = self.compute_scene_time(row)
        self.table.setItem(row, 6, QTableWidgetItem(str(timedelta(seconds=secs))))
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Remove summary rows
    # ------------------------
    def remove_summary_rows(self):
        for r in reversed(range(self.table.rowCount())):
            item = self.table.item(r, 0)
            if item is None:
                continue
            text = item.text()
            if any(text.startswith(prefix) for prefix in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                self.table.removeRow(r)

    # ------------------------
    # Animated recalculation
    # ------------------------
    def trigger_recalc_with_row_fades(self):
        self.remove_summary_rows()
        total, wrap, lunch_start, insert_index = self.calculate_schedule()

        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=True)

        self.insert_total_row(total, animate=True)
        self.insert_wrap_row(wrap, animate=True)
        self.update_row_numbers()
        self._update_last_recalc_timestamp()

    # ------------------------
    # Fast recalculation (no animation)
    # ------------------------
    def recalculate_schedule(self):
        self.remove_summary_rows()
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)
        self.update_row_numbers()
        self._update_last_recalc_timestamp()

    # ------------------------
    # Calculate schedule algorithm
    # ------------------------
    def calculate_schedule(self):
        total_scene_seconds = 0
        durations = []
        for i in range(len(self.scenes)):
            secs = self.compute_scene_time(i)
            durations.append(secs)
            total_scene_seconds += secs

        lunch_min = int(self.lunch_duration_input.currentText())
        lunch_dur = lunch_min * 60
        move_min = int(self.move_duration_input.currentText())
        move_count = int(self.company_moves_input.currentText())
        include = self.include_moves_lunch_toggle.isChecked()

        lunch_start = None
        insert_index = None

        start_dt = datetime.strptime(self.start_time_input.currentText(), "%H:%M")

        if include:
            if self.auto_lunch_toggle.isChecked():
                midpoint = total_scene_seconds // 2
                running = 0
                for i, secs in enumerate(durations):
                    running += secs
                    if running >= midpoint:
                        insert_index = i + 1
                        lunch_start = start_dt + timedelta(seconds=running)
                        break
                if insert_index is None:
                    insert_index = len(durations)
                    lunch_start = start_dt
            else:
                fixed_hours = int(self.lunch_fixed_spin.value())
                fixed_seconds = fixed_hours * 3600
                running = 0
                for i, secs in enumerate(durations):
                    running += secs
                    if running >= fixed_seconds:
                        insert_index = i + 1
                        lunch_start = start_dt + timedelta(seconds=running)
                        break
                if insert_index is None:
                    insert_index = len(durations)
                    lunch_start = start_dt + timedelta(seconds=fixed_seconds)

        total_seconds = total_scene_seconds
        if include:
            total_seconds += lunch_dur + (move_min * 60 * move_count)

        wrap_dt = start_dt + timedelta(seconds=total_seconds)
        return total_scene_seconds, wrap_dt.strftime("%H:%M"), lunch_start, insert_index

    # ------------------------
    # Populate the table
    # ------------------------
    def populate_table(self):
        self.table.clearSpans()
        self.table.clear()
        self.remove_summary_rows()

        headers = [
            "Scene Heading", "Actions", "Dialogue",
            "Length (pages+1/8s)", "Length (MM:SS)",
            "Camera Setups (Count)", "Shooting Time (HH:MM:SS)"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.scenes))

        for i, sc in enumerate(self.scenes):
            heading = sc["heading"]
            page_len, mmss = self.calculate_scene_length(sc["content"])

            setups_box = QComboBox()
            setups_box.addItems([str(n) for n in range(1, 21)])
            setups_box.view().setMinimumWidth(60)
            if heading.upper().startswith("INT"):
                setups_box.setCurrentText(str(DEFAULTS["setups_int"]))
            else:
                setups_box.setCurrentText(str(DEFAULTS["setups_ext"]))

            setups_box.currentTextChanged.connect(lambda t, box=setups_box: self.update_scene_row_for_box(box))

            self.table.setItem(i, 0, QTableWidgetItem(heading))
            self.table.setItem(i, 3, QTableWidgetItem(page_len))
            self.table.setItem(i, 4, QTableWidgetItem(mmss))
            self.table.setCellWidget(i, 5, setups_box)
            self.table.setItem(i, 6, QTableWidgetItem(str(timedelta(seconds=self.compute_scene_time(i)))))

        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)

        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

        self.update_row_numbers()
        self._update_last_recalc_timestamp()

    # ------------------------
    # Helper: create centered item
    # ------------------------
    def make_centered_item(self, text, color):
        item = QTableWidgetItem(text)
        item.setBackground(QBrush(QColor(color)))
        item.setFont(self._system_ui_font(12, bold=True))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    # ------------------------
    # Row fade animation
    # ------------------------
    def animate_row(self, row):
        overlay = QWidget(self.table.viewport())
        rect = self.table.visualRect(self.table.model().index(row, 0))
        overlay.setGeometry(0, rect.y(), self.table.viewport().width(), rect.height())
        eff = QGraphicsOpacityEffect()
        overlay.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", overlay)
        anim.setDuration(FADE_DURATION_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(overlay.deleteLater)
        overlay.show()
        anim.start()

    # ------------------------
    # Insert lunch row
    # ------------------------
    def insert_lunch_row(self, row_index, lunch_start_dt, lunch_minutes, animate=True):
        self.table.insertRow(row_index)
        text = f"LUNCH — Starts at {lunch_start_dt.strftime('%H:%M')} ({str(timedelta(minutes=lunch_minutes))})"
        item = self.make_centered_item(text, "orange")
        self.table.setItem(row_index, 0, item)
        self.table.setSpan(row_index, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row_index)

    # ------------------------
    # Insert total row
    # ------------------------
    def insert_total_row(self, total_seconds, animate=True):
        row = self.table.rowCount()
        self.table.insertRow(row)
        text = f"TOTAL SHOOT LENGTH — {str(timedelta(seconds=total_seconds))}"
        item = self.make_centered_item(text, "lightgreen")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row)

    # ------------------------
    # Insert wrap row
    # ------------------------
    def insert_wrap_row(self, wrap_str, animate=True):
        row = self.table.rowCount()
        self.table.insertRow(row)
        text = f"ESTIMATED WRAP — {wrap_str}"
        item = self.make_centered_item(text, "lightblue")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row)

    # ------------------------
    # Update row numbering
    # ------------------------
    def update_row_numbers(self):
        for r in range(self.table.rowCount()):
            if not self.table.verticalHeaderItem(r):
                self.table.setVerticalHeaderItem(r, QTableWidgetItem())
            header_item = self.table.verticalHeaderItem(r)
            first_item = self.table.item(r, 0)
            if first_item and any(first_item.text().startswith(p) for p in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                header_item.setText("")
            else:
                header_item.setText(str(r + 1))

    # ------------------------
    # Gather table data
    # ------------------------
    def get_table_data(self):
        headers = []
        for i in range(self.table.columnCount()):
            h = self.table.horizontalHeaderItem(i)
            headers.append(h.text() if h else "")
        data = [headers]

        for r in range(self.table.rowCount()):
            rowd = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item:
                    rowd.append(item.text())
                else:
                    widget = self.table.cellWidget(r, c)
                    if widget:
                        if hasattr(widget, "currentText"):
                            rowd.append(widget.currentText())
                        elif hasattr(widget, "text"):
                            rowd.append(widget.text())
                        else:
                            rowd.append("")
                    else:
                        rowd.append("")
            data.append(rowd)
        return data

    # ------------------------
    # Low-level export writer
    # ------------------------
    def _write_exports(self, csv_path, pdf_path, choice="Export Both"):
        data = self.get_table_data()
        csv_written = None
        pdf_written = None

        if choice in ("Export CSV", "Export Both"):
            try:
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerows(data)
                csv_written = csv_path
            except Exception:
                csv_written = None

        if choice in ("Export PDF", "Export Both"):
            try:
                styles = getSampleStyleSheet()
                styles.add(ParagraphStyle(name="Center12", alignment=1, fontSize=12, leading=15))
                formatted = [[Paragraph(cell, styles["Center12"]) for cell in row] for row in data]
                table = Table(formatted)
                ts = TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ])
                for r, row in enumerate(data):
                    if row[0].startswith("LUNCH"):
                        ts.add("BACKGROUND", (0, r), (-1, r), colors.orange)
                        ts.add("SPAN", (0, r), (-1, r))
                    elif row[0].startswith("TOTAL SHOOT LENGTH"):
                        ts.add("BACKGROUND", (0, r), (-1, r), colors.lightgreen)
                        ts.add("SPAN", (0, r), (-1, r))
                    elif row[0].startswith("ESTIMATED WRAP"):
                        ts.add("BACKGROUND", (0, r), (-1, r), colors.lightblue)
                        ts.add("SPAN", (0, r), (-1, r))
                table.setStyle(ts)
                SimpleDocTemplate(pdf_path, pagesize=letter).build([table])
                pdf_written = pdf_path
            except Exception:
                pdf_written = None

        return csv_written, pdf_written

    # ------------------------
    # Export flow
    # ------------------------
    def export_file(self):
        if not self.current_fountain_path:
            QMessageBox.warning(self, "No File", "Load a Fountain file first.")
            return None, None

        base = os.path.dirname(self.current_fountain_path)
        name = os.path.splitext(os.path.basename(self.current_fountain_path))[0]
        csv_path = os.path.join(base, f"breakdown_{name}.csv")
        pdf_path = os.path.join(base, f"breakdown_{name}.pdf")

        choice = self.export_dropdown.currentText()

        csv_written, pdf_written = self._write_exports(csv_path, pdf_path, choice=choice)

        if csv_written:
            QMessageBox.information(self, "Export Complete", f"CSV exported to: {csv_written}")
        if pdf_written:
            QMessageBox.information(self, "Export Complete", f"PDF exported to: {pdf_written}")
        if not csv_written and not pdf_written:
            QMessageBox.critical(self, "Export Error", "No files could be exported (check permissions).")

        return csv_written, pdf_written

    # ------------------------
    # Export wrapper with save warning
    # ------------------------
    def _export_with_save_warning(self):
        reply = QMessageBox.question(
            self,
            "Export and Save Preferences",
            "Exporting will also save your preferences to settings.json. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        self._save_settings()
        self.export_file()
        self._update_last_recalc_timestamp()

    # ------------------------
    # Recalculate wrapper with feedback
    # ------------------------
    def _recalculate_and_feedback(self):
        self.trigger_recalc_with_row_fades()
        QMessageBox.information(self, "Recalculated", "Schedule successfully updated.")

    # ------------------------
    # Update last recalculated timestamp
    # ------------------------
    def _update_last_recalc_timestamp(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.last_recalc_label.setText(f"Last recalculated: {now}")

    # ------------------------
    # Preview modal with QtPDF
    # ------------------------
    def open_preview_modal(self):
        tempdir = tempfile.gettempdir()
        csv_path = os.path.join(tempdir, "preview.csv")
        pdf_path = os.path.join(tempdir, "preview.pdf")

        self._write_exports(csv_path, pdf_path, choice="Export Both")

        dlg = QDialog(self)
        dlg.setWindowTitle("Preview — Producer's Toolkit")
        dlg.resize(900, 700)
        dlg.setModal(True)

        layout = QVBoxLayout(dlg)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # CSV preview tab
        csv_tab = QWidget()
        csv_layout = QVBoxLayout(csv_tab)
        csv_browser = QTextBrowser()
        csv_browser.setFont(self._system_ui_font(11))
        try:
            with open(csv_path, encoding="utf-8") as f:
                csv_browser.setText(f.read())
        except Exception as e:
            csv_browser.setText(f"Could not load CSV preview: {e}")
        csv_layout.addWidget(csv_browser)
        tabs.addTab(csv_tab, "CSV Preview")

        # PDF preview tab
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
                fallback = QLabel(f"PDF Preview unavailable: {e}")
                fallback.setFont(self._system_ui_font(12))
                pdf_layout.addWidget(fallback)
        else:
            fallback = QLabel(
                "QtPDF module not available.\n"
                "Install PyQt6-QtPdf and PyQt6-QtPdfWidgets for live PDF preview."
            )
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setFont(self._system_ui_font(12, italic=True))
            pdf_layout.addWidget(fallback)

        tabs.addTab(pdf_tab, "PDF Preview")

        # Bottom buttons
        btn_row = QHBoxLayout()
        layout.addLayout(btn_row)
        btn_row.addStretch()

        open_btn = QPushButton("Open in Default App")
        open_btn.setFont(self._system_ui_font(12))
        btn_row.addWidget(open_btn)

        close_btn = QPushButton("Close Preview")
        close_btn.setFont(self._system_ui_font(12))
        btn_row.addWidget(close_btn)

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
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    window = ProducersToolkit()
    window.show()
    sys.exit(app.exec())
# ------------------------------------------------------------#
# END OF FILE
# ------------------------------------------------------------#