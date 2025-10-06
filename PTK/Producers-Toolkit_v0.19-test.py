# ------------------------------------------------------------
# ProducersToolkit_v0_19_test.py
# ------------------------------------------------------------
# v0.19-test
#
# - Builds on v0.18.4-pre features (badges, compact cards, persistent settings saved on export,
#   last-recalculated, recalc/export fixes, Preview modal).
# - Preview modal now auto-loads a real PDF preview using QtPDF (QPdfDocument + QPdfView)
#   if PyQt6.QtPdf / PyQt6.QtPdfWidgets are available.
# - Falls back to the previous HTML/text-based PDF preview if QtPDF is not available.
# - Single-file PyQt6 application, heavily commented for clarity.
# ------------------------------------------------------------

# ------------------------
# Standard library imports
# ------------------------
import sys                                   # system argv and exit
import os                                    # file path handling
import json                                  # settings persistence
import re                                    # simple fountain parsing
import csv                                   # CSV export
import tempfile                              # temporary files for preview
from datetime import timedelta, datetime    # time arithmetic and formatting

# ------------------------
# PyQt6 imports (widgets, core, gui)
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
# We try to import QPdfDocument and QPdfView; if unavailable, set a flag and fallback to HTML preview.
try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
    QT_PDF_AVAILABLE = True
except Exception:
    # QtPDF modules not available in this environment
    QT_PDF_AVAILABLE = False

# ------------------------
# ReportLab imports for PDF export generation
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

FADE_DURATION_MS = 500              # per-row fade animation duration (ms)
CARD_BG = "#f8f9fb"                 # card background color
CARD_PADDING = 6                    # card padding (px)
CARD_RADIUS = 6                     # card corner radius (px)
CARD_SHADOW_BLUR = 12               # shadow blur radius (px)
CARD_SHADOW_OFFSET = (0, 3)         # shadow x,y offset
SETTINGS_FILE = "settings.json"     # preferences file (same dir as script)

# ------------------------------------------------------------
# Main application window
# ------------------------------------------------------------
class ProducersToolkit(QMainWindow):
    """Main window for Producer's Toolkit v0.19-test (QtPDF preview)."""

    def __init__(self):
        # Initialize base QMainWindow
        super().__init__()

        # Window title and size
        self.setWindowTitle("Producer's Toolkit  v0.19-test")
        self.resize(1400, 900)

        # Internal state variables
        self.scenes = []                     # parsed scenes will be stored here
        self.current_fountain_path = ""      # path to loaded fountain file
        self.words_per_page = DEFAULTS["words_per_page"]
        self.setup_minutes = DEFAULTS["setup_minutes"]

        # Build the UI components
        self._build_ui()

        # Load preferences if settings.json exists (applies to controls)
        self._load_settings()

    # ------------------------
    # Build main UI layout and widgets
    # ------------------------
    def _build_ui(self):
        """
        Construct the full UI:
         - Top bar (Load + badges)
         - Three compact cards (Timing, Calculation, Lunch placement)
         - Main table for scenes
         - Bottom row: last recalculated + Preview + Export controls
        """

        # Central widget + vertical layout (holds everything)
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)

        # ------------------------
        # Top row: Load button (left) and badges (right)
        # ------------------------
        top_row = QHBoxLayout()
        self.main_layout.addLayout(top_row)

        # Load Fountain File button
        self.load_btn = QPushButton("Load Fountain File")
        self.load_btn.setFont(QFont("Helvetica", 12))
        self.load_btn.clicked.connect(self.load_fountain_file)
        top_row.addWidget(self.load_btn)  # placed on left

        # Spacer pushes badges to the right
        top_row.addStretch()

        # Badges layout to contain small pill labels
        badges_layout = QHBoxLayout()

        # Lunch Mode badge (shows Auto or Fixed)
        self.badge_lunch = QLabel("Auto Lunch Mode")  # initial default text
        self.badge_lunch.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        self.badge_lunch.setContentsMargins(8, 4, 8, 4)
        # default green background for Auto
        self.badge_lunch.setStyleSheet(self._badge_style("#C8E6C9"))
        badges_layout.addWidget(self.badge_lunch)

        # Setup time badge (neutral gray)
        self.badge_setup = QLabel(f"Setup Time: {self.setup_minutes} min")
        self.badge_setup.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        self.badge_setup.setContentsMargins(8, 4, 8, 4)
        self.badge_setup.setStyleSheet(self._badge_style("#E0E0E0"))
        badges_layout.addWidget(self.badge_setup)

        # Add badges to top row (right side)
        top_row.addLayout(badges_layout)

        # tiny spacing under top row
        self.main_layout.addSpacing(8)

        # ------------------------
        # Card A: Timing inputs
        # ------------------------
        self.card_timing = self._make_card()
        self.main_layout.addWidget(self.card_timing)
        timing_layout = QHBoxLayout(self.card_timing)

        # Label font 12pt bold for readability
        label_font = QFont("Helvetica", 12, QFont.Weight.Bold)

        # Company moves input (0..20)
        lbl_moves = QLabel("Company moves:")
        lbl_moves.setFont(label_font)
        timing_layout.addWidget(lbl_moves)
        self.company_moves_input = QComboBox()
        self.company_moves_input.addItems([str(i) for i in range(0, 21)])
        self.company_moves_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.company_moves_input)

        # Move duration (mins)
        lbl_move_dur = QLabel("Move duration (min):")
        lbl_move_dur.setFont(label_font)
        timing_layout.addWidget(lbl_move_dur)
        self.move_duration_input = QComboBox()
        self.move_duration_input.addItems([str(i) for i in range(0, 121)])
        self.move_duration_input.setCurrentText(str(DEFAULTS["default_move_duration"]))
        self.move_duration_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.move_duration_input)

        # Lunch duration (mins)
        lbl_lunch_dur = QLabel("Lunch duration (min):")
        lbl_lunch_dur.setFont(label_font)
        timing_layout.addWidget(lbl_lunch_dur)
        self.lunch_duration_input = QComboBox()
        self.lunch_duration_input.addItems([str(i) for i in range(0, 181)])
        self.lunch_duration_input.setCurrentText(str(DEFAULTS["default_lunch_duration"]))
        self.lunch_duration_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.lunch_duration_input)

        # Start time (24-hr, 15-min intervals)
        lbl_start = QLabel("Start time:")
        lbl_start.setFont(label_font)
        timing_layout.addWidget(lbl_start)
        self.start_time_input = QComboBox()
        times = [f"{h:02}:{m:02}" for h in range(24) for m in (0, 15, 30, 45)]
        self.start_time_input.addItems(times)
        self.start_time_input.setCurrentText(DEFAULTS["default_start_time"])
        self.start_time_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.start_time_input)

        # Include moves & lunch toggle
        self.include_moves_lunch_toggle = QCheckBox("Include moves & lunch in totals?")
        self.include_moves_lunch_toggle.setFont(label_font)
        self.include_moves_lunch_toggle.setChecked(True)
        timing_layout.addWidget(self.include_moves_lunch_toggle)

        # push to the left to keep row compact
        timing_layout.addStretch()
        self.main_layout.addSpacing(6)  # small spacing below card A

        # ------------------------
        # Card B: Calculation controls
        # ------------------------
        self.card_calc = self._make_card()
        self.main_layout.addWidget(self.card_calc)
        calc_layout = QHBoxLayout(self.card_calc)

        # Custom WPP toggle
        self.custom_wpp_toggle = QCheckBox("Use Custom Words Per Page")
        self.custom_wpp_toggle.setFont(label_font)
        self.custom_wpp_toggle.stateChanged.connect(self.toggle_custom_wpp_changed)
        calc_layout.addWidget(self.custom_wpp_toggle)

        # Words-per-page spinbox (100..250)
        lbl_wpp = QLabel("Words Per Page:")
        lbl_wpp.setFont(label_font)
        calc_layout.addWidget(lbl_wpp)
        self.wpp_spin = QSpinBox()
        self.wpp_spin.setRange(100, 250)
        self.wpp_spin.setValue(DEFAULTS["words_per_page"])
        self.wpp_spin.setEnabled(False)
        self.wpp_spin.setFont(QFont("Helvetica", 12))
        self.wpp_spin.valueChanged.connect(self.wpp_value_changed)
        calc_layout.addWidget(self.wpp_spin)

        # LX & Camera Setup Time label (single ampersand) + spinbox (1..30)
        lbl_setup = QLabel("LX & Camera Setup Time (min):")
        lbl_setup.setFont(label_font)
        calc_layout.addWidget(lbl_setup)
        self.setup_minutes_spin = QSpinBox()
        self.setup_minutes_spin.setRange(1, 30)
        self.setup_minutes_spin.setValue(self.setup_minutes)
        self.setup_minutes_spin.setFont(QFont("Helvetica", 12))
        # Auto-recalc (no animation) when minutes-per-setup changes
        self.setup_minutes_spin.valueChanged.connect(self.setup_minutes_changed)
        calc_layout.addWidget(self.setup_minutes_spin)

        # Lock default setups toggle
        self.lock_setups_toggle = QCheckBox("Use and Lock Default Number of Setups (INT=3, EXT=5)")
        self.lock_setups_toggle.setFont(label_font)
        self.lock_setups_toggle.stateChanged.connect(self.toggle_default_setups_lock)
        calc_layout.addWidget(self.lock_setups_toggle)

        calc_layout.addStretch()  # push recalc to right

        # Recalculate button (now always triggers and gives feedback)
        self.recalc_button = QPushButton("Recalculate Schedule")
        self.recalc_button.setFont(QFont("Helvetica", 12))
        # This connects to wrapper that runs recalc and shows a messagebox confirming completion
        self.recalc_button.clicked.connect(self._recalculate_and_feedback)
        calc_layout.addWidget(self.recalc_button)

        # tiny spacing below
        self.main_layout.addSpacing(6)

        # ------------------------
        # Card C: Lunch placement controls
        # ------------------------
        self.card_lunch = self._make_card()
        self.main_layout.addWidget(self.card_lunch)
        lunch_layout = QHBoxLayout(self.card_lunch)

        self.lunch_auto_toggle = QCheckBox("Lunch Placement Mode: Auto (midpoint when checked)")
        self.lunch_auto_toggle.setFont(label_font)
        self.lunch_auto_toggle.setChecked(True)
        self.lunch_auto_toggle.stateChanged.connect(self.lunch_mode_changed)
        lunch_layout.addWidget(self.lunch_auto_toggle)

        lbl_fixed = QLabel("Fixed after (hours):")
        lbl_fixed.setFont(label_font)
        lunch_layout.addWidget(lbl_fixed)
        self.lunch_fixed_spin = QSpinBox()
        self.lunch_fixed_spin.setRange(1, 12)
        self.lunch_fixed_spin.setValue(6)
        self.lunch_fixed_spin.setFont(QFont("Helvetica", 12))
        self.lunch_fixed_spin.valueChanged.connect(self.lunch_fixed_hours_changed)
        lunch_layout.addWidget(self.lunch_fixed_spin)

        lunch_layout.addStretch()
        self.main_layout.addSpacing(10)

        # ------------------------
        # Main table widget (scene rows and summary rows)
        # ------------------------
        self.table = QTableWidget()
        self.main_layout.addWidget(self.table)

        # ------------------------
        # Bottom row: Last recalculated status, Preview, Export
        # ------------------------
        bottom_row = QHBoxLayout()
        self.main_layout.addLayout(bottom_row)

        bottom_row.addStretch()  # push items to the right

        # Last recalculated label (updates whenever schedule is recalculated)
        self.last_recalc_label = QLabel("Last recalculated: Never")
        font = QFont("Helvetica", 10)
        font.setItalic(True)
        self.last_recalc_label.setFont(font)

        self.last_recalc_label.setStyleSheet("color: #666666;")
        bottom_row.addWidget(self.last_recalc_label)

        # small spacing
        bottom_row.addSpacing(12)

        # Preview button (opens modal with CSV + PDF tabs)
        self.preview_button = QPushButton("Preview")
        self.preview_button.setFont(QFont("Helvetica", 12))
        # Auto-load PDF preview when modal opens per v0.19-test requirements
        self.preview_button.clicked.connect(self.open_preview_modal)
        bottom_row.addWidget(self.preview_button)

        # Export dropdown and button
        self.export_dropdown = QComboBox()
        self.export_dropdown.addItems(["Export CSV", "Export PDF", "Export Both"])
        self.export_dropdown.setFont(QFont("Helvetica", 12))
        bottom_row.addWidget(self.export_dropdown)

        self.export_button = QPushButton("Export")
        self.export_button.setFont(QFont("Helvetica", 12))
        # Export wrapper warns user that preferences will be saved and then performs export + save
        self.export_button.clicked.connect(self._export_with_save_warning)
        bottom_row.addWidget(self.export_button)

    # ------------------------
    # Small helper to create a card-like QFrame with shadow-only styling
    # ------------------------
    def _make_card(self):
        """
        Build a QFrame styled as a compact card (rounded, drop shadow, background).
        Returns the frame.
        """
        frame = QFrame()
        frame.setStyleSheet(f"background-color: {CARD_BG}; border-radius: {CARD_RADIUS}px; padding:{CARD_PADDING}px;")
        shadow = QGraphicsDropShadowEffect(frame)
        shadow.setBlurRadius(CARD_SHADOW_BLUR)
        shadow.setOffset(*CARD_SHADOW_OFFSET)
        shadow.setColor(QColor(0, 0, 0, 60))
        frame.setGraphicsEffect(shadow)
        return frame

    # ------------------------
    # Helper: CSS for badges (rounded pill look)
    # ------------------------
    def _badge_style(self, bg_hex):
        """
        Return a stylesheet string to style QLabel as a small rounded badge.
        """
        return (
            f"background-color: {bg_hex}; color: #000000; border-radius: 12px; "
            "padding-left: 8px; padding-right: 8px;"
        )

    # ------------------------
    # SETTINGS: load saved preferences from SETTINGS_FILE
    # ------------------------
    def _load_settings(self):
        """
        Load preferences from settings.json if present. Apply to controls.
        Safe: ignores parse errors and continues with defaults.
        """
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    s = json.load(f)
                # apply saved values with sensible fallbacks
                if "words_per_page" in s:
                    self.words_per_page = int(s["words_per_page"])
                    self.wpp_spin.setValue(self.words_per_page)
                    if s.get("custom_wpp", False):
                        self.custom_wpp_toggle.setChecked(True)
                        self.wpp_spin.setEnabled(True)
                if "setup_minutes" in s:
                    self.setup_minutes = int(s["setup_minutes"])
                    self.setup_minutes_spin.setValue(self.setup_minutes)
                if "lunch_auto" in s:
                    self.lunch_auto_toggle.setChecked(bool(s["lunch_auto"]))
                if "lunch_fixed_hours" in s:
                    self.lunch_fixed_spin.setValue(int(s["lunch_fixed_hours"]))
                if "lock_setups" in s:
                    self.lock_setups_toggle.setChecked(bool(s["lock_setups"]))
                # reflect loaded preferences in badges
                self._update_badges()
            except Exception:
                # on any error, ignore and keep defaults
                pass

    # ------------------------
    # SETTINGS: write preferences to SETTINGS_FILE (called when user confirms export)
    # ------------------------
    def _save_settings(self):
        """
        Serialize current preferences to settings.json. Called on export after confirmation.
        """
        s = {
            "words_per_page": int(self.wpp_spin.value()) if self.custom_wpp_toggle.isChecked() else DEFAULTS["words_per_page"],
            "custom_wpp": bool(self.custom_wpp_toggle.isChecked()),
            "setup_minutes": int(self.setup_minutes_spin.value()),
            "lunch_auto": bool(self.lunch_auto_toggle.isChecked()),
            "lunch_fixed_hours": int(self.lunch_fixed_spin.value()),
            "lock_setups": bool(self.lock_setups_toggle.isChecked())
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(s, f, indent=2)
        except Exception:
            # ignore write errors silently (don't block export)
            pass

    # ------------------------
    # Badge updater: instantly reflect lunch mode and setup minutes
    # ------------------------
    def _update_badges(self):
        """
        Update the two badges immediately whenever relevant state changes.
        """
        if self.lunch_auto_toggle.isChecked():
            self.badge_lunch.setText("Auto Lunch Mode")
            self.badge_lunch.setStyleSheet(self._badge_style("#C8E6C9"))  # green
        else:
            self.badge_lunch.setText("Fixed Lunch Mode")
            self.badge_lunch.setStyleSheet(self._badge_style("#BBDEFB"))  # blue
        self.badge_setup.setText(f"Setup Time: {self.setup_minutes} min")
        self.badge_setup.setStyleSheet(self._badge_style("#E0E0E0"))

    # ------------------------
    # Words-per-page helper respecting toggle
    # ------------------------
    def get_current_wpp(self):
        if self.custom_wpp_toggle.isChecked():
            return int(self.wpp_spin.value())
        return int(DEFAULTS["words_per_page"])

    # ------------------------
    # Custom WPP toggle handler
    # ------------------------
    def toggle_custom_wpp_changed(self, state):
        """
        Enable or disable the WPP spin control based on the checkbox state,
        update stored value, and trigger animated recalc to show changes.
        """
        if state:
            self.wpp_spin.setEnabled(True)
            self.words_per_page = int(self.wpp_spin.value())
        else:
            self.wpp_spin.setEnabled(False)
            self.words_per_page = DEFAULTS["words_per_page"]
        # update badges and animate recalculation
        self._update_badges()
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # WPP spin change handler
    # ------------------------
    def wpp_value_changed(self, val):
        """
        Update internal WPP and animate recalc so user sees updated durations.
        """
        self.words_per_page = int(val)
        self._update_badges()
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Minutes-per-setup changed (auto recalc without animation)
    # ------------------------
    def setup_minutes_changed(self, val):
        """
        Update minutes-per-setup and run a fast (non-animated) recalculation for responsiveness.
        """
        self.setup_minutes = int(val)
        self._update_badges()
        self.recalculate_schedule()

    # ------------------------
    # Lock default setups toggle handler (applies defaults and toggles editable state)
    # ------------------------
    def toggle_default_setups_lock(self, state):
        """
        When turned on, iterate all rows and set their setups combo to default (INT/EXT),
        then disable the widgets (visible but locked). When turned off, re-enable.
        """
        lock_on = bool(state)
        for r in range(self.table.rowCount()):
            widget = self.table.cellWidget(r, 5)  # setups combos expected at column 5
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
                    # robust: skip any widget that causes errors
                    continue
        # animate the recalculation so the summary rows reflect the new values
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Lunch mode toggle handler
    # ------------------------
    def lunch_mode_changed(self, state):
        """
        Update badges and animate recalculation when the lunch placement mode is toggled.
        """
        self._update_badges()
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Fixed hours spin handler
    # ------------------------
    def lunch_fixed_hours_changed(self, val):
        """
        If the lunch mode is fixed (Auto unchecked), changing the fixed hour triggers
        an animated recalc to show updated insertion and times.
        """
        if not self.lunch_auto_toggle.isChecked():
            self.trigger_recalc_with_row_fades()

    # ------------------------
    # Load Fountain file from disk, parse, and populate table
    # ------------------------
    def load_fountain_file(self):
        """
        Launch file dialog to choose a .fountain file, parse it and populate the table.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Fountain", "", "Fountain Files (*.fountain)")
        if not file_path:
            return
        self.current_fountain_path = file_path
        # read UTF-8 file contents
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        # parse into scenes
        self.scenes = self.parse_fountain(content)
        # populate the table widgets/rows
        self.populate_table()
        # if lock was on previously, re-apply it to the new rows
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)
        # update badges
        self._update_badges()

    # ------------------------
    # Simple Fountain parser splitting on INT./EXT. headings
    # ------------------------
    def parse_fountain(self, content):
        """
        Parse the simplest form of Fountain: lines that start with INT. or EXT. are scene headings.
        Returns a list of dicts: {"heading": str, "content": [lines...]}
        """
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
    # Convert a scene's text to pages + mm:ss using active WPP
    # ------------------------
    def calculate_scene_length(self, scene_text):
        """
        Count words, compute pages as words/WPP, convert to pages + eighths and mm:ss estimate.
        Returns: (page_str, mmss)
        """
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
        seconds = int(round(pages * 60))  # approx 1 page = 60 sec
        mm, ss = divmod(seconds, 60)
        mmss = f"{mm:02}:{ss:02}"
        return page_str, mmss

    # ------------------------
    # Compute shooting time in seconds for a given scene row using self.setup_minutes
    # ------------------------
    def compute_scene_time(self, row):
        """
        Read the setups combo in column 5 and the MM:SS in column 4, add setups penalty,
        return total seconds as int. Robust with fallbacks.
        """
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
    # Handler when a per-row setups combo changes
    # ------------------------
    def update_scene_row_for_box(self, box):
        """
        Determine the row of the changed combo (robustly), update the Shooting Time column
        for that row, and animate recalc for summary rows.
        """
        idx = self.table.indexAt(box.pos())
        row = idx.row()
        # fallback: scan rows looking for the widget
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
    # Remove summary rows (LUNCH, TOTAL, ESTIMATED WRAP)
    # ------------------------
    def remove_summary_rows(self):
        """
        Walk backwards through rows and remove any row whose first cell starts with
        a known summary prefix. Iterating backwards avoids index shifts.
        """
        for r in reversed(range(self.table.rowCount())):
            item = self.table.item(r, 0)
            if item is None:
                continue
            text = item.text()
            if any(text.startswith(prefix) for prefix in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                self.table.removeRow(r)

    # ------------------------
    # Animated per-row recalc (triggered by Recalculate and other visible events)
    # ------------------------
    def trigger_recalc_with_row_fades(self):
        """
        Remove old summary rows, recompute schedule, insert summaries with per-row fade animations,
        update numbering and the last-recalc timestamp.
        """
        self.remove_summary_rows()
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=True)
        self.insert_total_row(total, animate=True)
        self.insert_wrap_row(wrap, animate=True)
        self.update_row_numbers()
        self._update_last_recalc_timestamp()

    # ------------------------
    # Fast (non-animated) recalculation for UI spins and quick changes
    # ------------------------
    def recalculate_schedule(self):
        """
        Remove previous summaries and insert new ones without animation for speed.
        """
        self.remove_summary_rows()
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)
        self.update_row_numbers()
        self._update_last_recalc_timestamp()

    # ------------------------
    # Update last recalculated timestamp label (bottom-right)
    # ------------------------
    def _update_last_recalc_timestamp(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.last_recalc_label.setText(f"Last recalculated: {now}")

    # ------------------------
    # Scheduling logic: compute total scene seconds, wrap time, lunch start & insert index
    # (includes fixed-mode bug fix: ensure lunch inserted after last scene if fixed time beyond total)
    # ------------------------
    def calculate_schedule(self):
        """
        Return tuple:
          (total_scene_seconds:int, wrap_time_str:"HH:MM", lunch_start:datetime|None, insert_index:int|None)
        """
        total_scene_seconds = 0
        durations = []
        for i in range(len(self.scenes)):
            s = self.compute_scene_time(i)
            durations.append(s)
            total_scene_seconds += s

        # read GUI extras
        lunch_min = int(self.lunch_duration_input.currentText())
        lunch_dur = lunch_min * 60
        move_min = int(self.move_duration_input.currentText()) * 60
        move_count = int(self.company_moves_input.currentText())
        include = self.include_moves_lunch_toggle.isChecked()

        lunch_start = None
        insert_index = None
        start_dt = datetime.strptime(self.start_time_input.currentText(), "%H:%M")

        if include:
            if self.lunch_auto_toggle.isChecked():
                # Auto midpoint: place after first scene where running >= midpoint
                midpoint = total_scene_seconds // 2
                running = 0
                for i, secs in enumerate(durations):
                    running += secs
                    if running >= midpoint:
                        insert_index = i + 1
                        lunch_start = start_dt + timedelta(seconds=running)
                        break
                # fallback when no durations or empty script
                if insert_index is None:
                    insert_index = len(durations)
                    lunch_start = start_dt
            else:
                # Fixed-after-X-hours: place after first scene where running >= fixed_seconds
                fixed_hours = int(self.lunch_fixed_spin.value())
                fixed_seconds = fixed_hours * 3600
                running = 0
                for i, secs in enumerate(durations):
                    running += secs
                    if running >= fixed_seconds:
                        insert_index = i + 1
                        lunch_start = start_dt + timedelta(seconds=running)
                        break
                # If fixed_seconds beyond total duration of scenes, place after last scene
                if insert_index is None:
                    insert_index = len(durations)
                    lunch_start = start_dt + timedelta(seconds=fixed_seconds)

        # compute total seconds including extras if included
        total_seconds = total_scene_seconds
        if include:
            total_seconds += lunch_dur + (move_min * move_count)

        wrap_dt = start_dt + timedelta(seconds=total_seconds)
        return total_scene_seconds, wrap_dt.strftime("%H:%M"), lunch_start, insert_index

    # ------------------------
    # Populate table rows for scenes and initial (non-animated) summaries
    # ------------------------
    def populate_table(self):
        """
        Clear table and repopulate with scene rows, setups combos, and summary rows.
        """
        self.table.clearSpans()
        self.table.clear()
        self.remove_summary_rows()

        # define human-friendly headers (Camera Setups header preserved)
        headers = [
            "Scene Heading", "Actions", "Dialogue",
            "Length (pages+1/8s)", "Length (MM:SS)",
            "Camera Setups (Count)", "Shooting Time (HH:MM:SS)"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.scenes))

        # populate each scene row
        for i, sc in enumerate(self.scenes):
            heading = sc["heading"]
            page_len, mmss = self.calculate_scene_length(sc["content"])

            # setups combo (1..20)
            setups_box = QComboBox()
            setups_box.addItems([str(n) for n in range(1, 21)])
            # default INT/EXT
            if heading.upper().startswith("INT"):
                setups_box.setCurrentText(str(DEFAULTS["setups_int"]))
            else:
                setups_box.setCurrentText(str(DEFAULTS["setups_ext"]))
            # connect robust handler referencing the widget itself
            setups_box.currentTextChanged.connect(lambda t, box=setups_box: self.update_scene_row_for_box(box))

            # place data into table
            self.table.setItem(i, 0, QTableWidgetItem(heading))
            self.table.setItem(i, 3, QTableWidgetItem(page_len))
            self.table.setItem(i, 4, QTableWidgetItem(mmss))
            self.table.setCellWidget(i, 5, setups_box)
            self.table.setItem(i, 6, QTableWidgetItem(str(timedelta(seconds=self.compute_scene_time(i)))))

        # insert initial summaries (non-animated for load)
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)

        # if lock is on, enforce it now
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

        # update badges and numbering
        self._update_badges()
        self.update_row_numbers()
        # update last recalculated timestamp
        self._update_last_recalc_timestamp()

    # ------------------------
    # Create a centered, bold 12pt QTableWidgetItem with background color (for summary rows)
    # ------------------------
    def make_centered_item(self, text, color):
        item = QTableWidgetItem(text)
        item.setBackground(QBrush(QColor(color)))
        item.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    # ------------------------
    # Per-row overlay fade animation
    # ------------------------
    def animate_row(self, row):
        """
        Visual overlay that fades in across a specific row to draw attention to newly inserted rows.
        """
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
    # Insert summary rows: lunch, total, wrap (optionally animate)
    # ------------------------
    def insert_lunch_row(self, row_index, lunch_start_dt, lunch_minutes, animate=True):
        self.table.insertRow(row_index)
        text = f"LUNCH — Starts at {lunch_start_dt.strftime('%H:%M')} ({str(timedelta(minutes=lunch_minutes))})"
        item = self.make_centered_item(text, "orange")
        self.table.setItem(row_index, 0, item)
        # span across all columns to create single merged-like cell
        self.table.setSpan(row_index, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row_index)

    def insert_total_row(self, total_seconds, animate=True):
        row = self.table.rowCount()
        self.table.insertRow(row)
        text = f"TOTAL SHOOT LENGTH — {str(timedelta(seconds=total_seconds))}"
        item = self.make_centered_item(text, "lightgreen")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row)

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
    # Update vertical header numbers (only number scene rows)
    # ------------------------
    def update_row_numbers(self):
        for r in range(self.table.rowCount()):
            if not self.table.verticalHeaderItem(r):
                self.table.setVerticalHeaderItem(r, QTableWidgetItem())
            header_item = self.table.verticalHeaderItem(r)
            first_item = self.table.item(r, 0)
            # summary rows should have empty vertical header (no number)
            if first_item and any(first_item.text().startswith(p) for p in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                header_item.setText("")
            else:
                header_item.setText(str(r + 1))

    # ------------------------
    # Gather table data (headers + rows) for exports & preview
    # ------------------------
    def get_table_data(self):
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
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
    # Export helper that writes CSV/PDF to specified paths silently (returns paths)
    # Used by both the export flow and the Preview modal (for temp files).
    # ------------------------
    def _write_exports(self, csv_path, pdf_path, choice="Export Both"):
        """
        Write CSV and/or PDF to the provided paths according to choice.
        Returns (csv_written_path_or_None, pdf_written_path_or_None)
        This function is silent (no messageboxes) so Preview can call it.
        """
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
    # Export function used by main export flow (shows message boxes)
    # ------------------------
    def export_file(self):
        """
        Export to files located next to the loaded fountain file.
        This function will show message boxes on success/failure and return paths.
        """
        if not self.current_fountain_path:
            QMessageBox.warning(self, "No File", "Load a Fountain file first.")
            return None, None

        base = os.path.dirname(self.current_fountain_path)
        name = os.path.splitext(os.path.basename(self.current_fountain_path))[0]
        csv_path = os.path.join(base, f"breakdown_{name}.csv")
        pdf_path = os.path.join(base, f"breakdown_{name}.pdf")
        choice = self.export_dropdown.currentText()

        csv_written, pdf_written = self._write_exports(csv_path, pdf_path, choice=choice)

        # show user feedback
        if csv_written:
            QMessageBox.information(self, "Export Complete", f"CSV exported to: {csv_written}")
        if pdf_written:
            QMessageBox.information(self, "Export Complete", f"PDF exported to: {pdf_written}")
        if not csv_written and not pdf_written:
            QMessageBox.critical(self, "Export Error", "No files could be exported (check permissions).")

        return csv_written, pdf_written

    # ------------------------
    # Export wrapper that warns user preferences will be saved, then saves and exports
    # ------------------------
    def _export_with_save_warning(self):
        """
        Ask the user to confirm that export will save preferences to settings.json.
        On Yes: save settings, perform export, update badges/timestamp.
        """
        reply = QMessageBox.question(
            self,
            "Export and Save Preferences",
            "Exporting will also save your preferences to settings.json. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return
        # Save preferences
        self._save_settings()
        # Perform export
        csv_path, pdf_path = self.export_file()
        # Update badges and timestamp (preferences persisted)
        self._update_badges()
        self._update_last_recalc_timestamp()

    # ------------------------
    # Recalculate wrapper that triggers animation and gives feedback
    # ------------------------
    def _recalculate_and_feedback(self):
        """
        Run animated recalculation and show a confirmation dialog to the user.
        """
        self.trigger_recalc_with_row_fades()
        QMessageBox.information(self, "Recalculated", "Schedule successfully updated.")

    # ------------------------
    # Preview modal dialog (auto-load PDF preview via QtPDF if available)
    # ------------------------
    def open_preview_modal(self):
        """
        Create a modal dialog with:
         - CSV Preview tab (QTableWidget)
         - PDF Preview tab (QPdfView if available; else HTML/QTextBrowser fallback)
        The PDF is generated into a temporary directory and loaded automatically.
        """
        # create a temporary directory for preview artifacts
        tempdir = tempfile.mkdtemp(prefix="producertoolkit_preview_")
        csv_path = os.path.join(tempdir, "preview.csv")
        pdf_path = os.path.join(tempdir, "preview.pdf")

        # write preview files silently (don't save preferences here)
        choice = "Export Both"
        csv_written, pdf_written = self._write_exports(csv_path, pdf_path, choice=choice)

        # Build modal dialog
        dlg = QDialog(self)
        dlg.setWindowTitle("Preview (CSV & PDF)")
        dlg.resize(1100, 750)
        dlg_layout = QVBoxLayout(dlg)

        # Tabs for CSV and PDF preview
        tabs = QTabWidget()
        dlg_layout.addWidget(tabs)

        # --- CSV Preview tab: build QTableWidget snapshot from CSV
        data = self.get_table_data()
        csv_table = QTableWidget()
        if data:
            headers = data[0]
            rows = data[1:]
            csv_table.setColumnCount(len(headers))
            csv_table.setRowCount(len(rows))
            csv_table.setHorizontalHeaderLabels(headers)
            for r, row in enumerate(rows):
                for c, cell in enumerate(row):
                    csv_table.setItem(r, c, QTableWidgetItem(cell))
            csv_table.resizeColumnsToContents()
        tabs.addTab(csv_table, "CSV Preview")

        # --- PDF Preview tab: use QtPDF if available (QPdfDocument + QPdfView), auto-load
        if QT_PDF_AVAILABLE and pdf_written:
            # create QPdfDocument and load the generated PDF file
            pdf_doc = QPdfDocument(dlg)
            load_status = pdf_doc.load(pdf_written)
            # QPdfView widget renders the document (interactive, zoomable)
            pdf_view = QPdfView(dlg)
            pdf_view.setDocument(pdf_doc)
            # Add the view into the tab (auto-loads the document)
            tabs.addTab(pdf_view, "PDF Preview (QtPDF)")
        else:
            # Fallback: render a scrollable HTML representation of the PDF content
            # This is less faithful than a real renderer, but still useful for inspection.
            pdf_browser = QTextBrowser()
            # Use the CSV-style HTML paging fallback (25 rows per page heuristic)
            rows_per_page = 25
            rows = data[1:] if len(data) > 1 else []
            total_pages = max(1, (len(rows) + rows_per_page - 1) // rows_per_page)
            html_parts = []
            for p in range(total_pages):
                start = p * rows_per_page
                end = start + rows_per_page
                page_rows = rows[start:end]
                html_parts.append(f"<h3>Page {p+1}</h3>")
                html_parts.append("<table border='1' cellpadding='6' cellspacing='0' width='100%'>")
                # header row
                html_parts.append("<tr>")
                for h in data[0]:
                    html_parts.append(f"<th>{h}</th>")
                html_parts.append("</tr>")
                # data rows
                for row in page_rows:
                    html_parts.append("<tr>")
                    for cell in row:
                        html_parts.append(f"<td>{cell}</td>")
                    html_parts.append("</tr>")
                html_parts.append("</table>")
                html_parts.append("<div style='height:12px'></div>")
            pdf_browser.setHtml("\n".join(html_parts))
            tabs.addTab(pdf_browser, "PDF Preview (Fallback)")

        # Bottom row for actions: Open in default app + Close
        bottom = QHBoxLayout()
        dlg_layout.addLayout(bottom)
        bottom.addStretch()

        def open_exported():
            # Prefer OS-opening the PDF if it exists, otherwise the CSV
            target = pdf_written if pdf_written and os.path.exists(pdf_written) else csv_written if csv_written and os.path.exists(csv_written) else None
            if not target:
                QMessageBox.warning(dlg, "Open Error", "No preview file available to open.")
                return
            try:
                if sys.platform.startswith("win"):
                    os.startfile(target)
                elif sys.platform.startswith("darwin"):
                    os.system(f"open '{target}'")
                else:
                    os.system(f"xdg-open '{target}' &")
            except Exception as e:
                QMessageBox.warning(dlg, "Open Error", f"Could not open file: {e}")

        open_btn = QPushButton("Open in Default App")
        open_btn.setFont(QFont("Helvetica", 12))
        open_btn.clicked.connect(open_exported)
        bottom.addWidget(open_btn)

        close_btn = QPushButton("Close")
        close_btn.setFont(QFont("Helvetica", 12))
        close_btn.clicked.connect(dlg.accept)
        bottom.addWidget(close_btn)

        # Show modal dialog; auto-load already performed by QPdfDocument/QPdfView if available
        dlg.exec()

    # ------------------------
    # Remaining methods reused from previous implementations (populate_table etc.)
    # ------------------------
    # They are already implemented above (calculate_scene_length, compute_scene_time, update_scene_row_for_box,
    # remove_summary_rows, trigger_recalc_with_row_fades, recalculate_schedule, insert_lunch_row, insert_total_row,
    # insert_wrap_row, update_row_numbers, get_table_data). For clarity, these methods are fully defined earlier
    # in the class. No extra changes required here.

# ------------------------------------------------------------
# Application entrypoint
# ------------------------------------------------------------
if __name__ == "__main__":
    # create Qt application and show main window
    app = QApplication(sys.argv)
    window = ProducersToolkit()
    window.show()
    # start Qt event loop
    sys.exit(app.exec())
