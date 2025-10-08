# ------------------------------------------------------------
# Producers-Toolkit_v0.19.1-test.py  (PART 1 of 3)
# ------------------------------------------------------------
# Version: v0.19.1-test
#
# Notes:
#  - This file is intentionally split into 3 parts for safe copy-paste.
#  - Part 1 contains:
#      * File header and metadata
#      * Imports
#      * Constants & defaults
#      * Main window class declaration start
#      * Cross-platform font helper with antialiasing
#      * UI construction method (_build_ui) up through cards and main controls
#
#  - Part 2 will contain scheduling logic, recalculation functions, table population, and export helpers.
#  - Part 3 will contain the preview modal (QtPDF integration), entry point, and any remaining utilities.
#
#  - Requirements:
#      Python 3.12+
#      PyQt6 (core)
#      PyQt6-QtPdf, PyQt6-QtPdfWidgets (optional but recommended for PDF preview)
#      reportlab (for PDF export)
#
# ------------------------------------------------------------

# ------------------------
# Standard library imports
# ------------------------
import sys                    # for argv and exit
import os                     # for file and path ops
import json                   # to persist settings to a JSON file
import re                     # simple regex for fountain parsing
import csv                    # CSV export
import uuid
import tempfile               # temporary directories for preview artifacts
from datetime import timedelta, datetime  # time arithmetic and formatting

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
# We attempt to import QtPDF modules. If they're unavailable, we'll fall back to the HTML text preview in the modal.
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
    "words_per_page": 150,            # default words per page (WPP)
    "setup_minutes": 5,               # default minutes per setup
    "setups_int": 3,                  # default setups for INT scenes
    "setups_ext": 5,                  # default setups for EXT scenes
    "default_move_duration": 10,      # default company move duration (minutes)
    "default_lunch_duration": 60,     # default lunch duration (minutes)
    "default_start_time": "08:00"     # default day start time (HH:MM)
}

FADE_DURATION_MS = 500               # row fade animation duration in milliseconds
CARD_BG = "#f8f9fb"                  # card background color (pale gray)
CARD_PADDING = 6                     # padding inside card frames (px)
CARD_RADIUS = 6                      # corner radius for card frames (px)
CARD_SHADOW_BLUR = 12                # drop shadow blur radius
CARD_SHADOW_OFFSET = (0, 3)          # drop shadow x,y offset
SETTINGS_FILE = "settings.json"      # settings filename (saved in same directory)

# ------------------------------------------------------------
# Main application window class
# ------------------------------------------------------------
class ProducersToolkit(QMainWindow):
    """
    Main application window for Producer's Toolkit v0.19.1-test.

    Structure:
      - Top bar: Load Fountain button + status badges (Lunch Mode, Setup Time)
      - Global controls area: 3 card-like frames (Timing, Calculation, Lunch Placement)
      - Main table: scene rows + summary rows
      - Bottom bar: Last recalculated timestamp + Preview + Export controls

    Important: UI construction is in _build_ui(). The scheduling and export logic is in Parts 2 & 3.
    """

    def __init__(self):
        """
        Initialize the main window, internal state, build UI and load saved settings.
        """
        # Initialize the base QMainWindow
        super().__init__()

        # Set window title and default size
        self.setWindowTitle("Producer's Toolkit  v0.19.1-test")
        self.resize(1400, 900)

        # Internal application state
        self.scenes = []                        # will hold parsed scenes (list of dicts)
        self.current_fountain_path = ""         # last loaded fountain filepath
        self.words_per_page = DEFAULTS["words_per_page"]
        self.setup_minutes = DEFAULTS["setup_minutes"]

        # Build the UI components and layout
        self._build_ui()

        # Load settings from disk if present; applies control values
        self._load_settings()

    # --------------------------------------------------------
    # Cross-platform system UI font helper with antialiasing
    # --------------------------------------------------------
    def _system_ui_font(self, size=12, bold=False, italic=False):
        """
        Return a QFont configured to use a native system UI font depending on the platform.

        - Windows -> Segoe UI
        - macOS   -> .AppleSystemUIFont (San Francisco)
        - Linux   -> Noto Sans (fallback to DejaVu/Ubuntu if not present)

        The font is configured with PreferAntialias style strategy for smoother rendering.
        Arguments:
          size (int): point size to use
          bold (bool): make the font bold
          italic (bool): make the font italic
        Returns:
          QFont instance
        """
        # minimal platform detection using sys.platform
        platform = sys.platform

        # Choose font family name appropriate for the platform
        if platform.startswith("win"):
            family = "Segoe UI"                 # native Windows UI font
        elif platform == "darwin":
            family = ".AppleSystemUIFont"       # native macOS system font
        else:
            # On many modern Linux distros Noto Sans is available; fall back to DejaVu Sans if needed
            # Note: Qt will fall back to available fonts if the specified one is not found.
            family = "Noto Sans"

        # Create the QFont with the selected family and size
        font = QFont(family, size)

        # Apply weight/style flags as requested
        if bold:
            font.setBold(True)
        if italic:
            font.setItalic(True)

        # Prefer antialiasing/clear-type style strategy for smoother rendering
        try:
            # QFont.StyleStrategy.PreferAntialias exists in PyQt6
            font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        except Exception:
            # If anything goes wrong, ignore (font will still render)
            pass

        return font
    
        # --------------------------------------------------------
    # Helper: create a card-styled QFrame with drop shadow
    # --------------------------------------------------------
    def _make_card(self):
        """
        Create and return a QFrame styled to appear as a soft 'card' container.

        Visual details:
          - Pale gray background (CARD_BG constant)
          - Rounded corners (CARD_RADIUS)
          - Subtle drop shadow (CARD_SHADOW_BLUR, CARD_SHADOW_OFFSET)
          - Internal layout padding (CARD_PADDING)
        """
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

        # Create a drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(CARD_SHADOW_BLUR)
        shadow.setOffset(*CARD_SHADOW_OFFSET)
        shadow.setColor(QColor(0, 0, 0, 60))  # light black translucent shadow
        frame.setGraphicsEffect(shadow)

        return frame


    # ===== PART 2: UI build, load/recalc logic =====

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)
        top_row = QHBoxLayout()
        layout.addLayout(top_row)

        mid_row = QHBoxLayout()
        layout.addLayout(mid_row)
        
        
        label_font = self._system_ui_font(12, bold=True)
        combo_view_font = self._system_ui_font(8, bold=False)

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

        
        self.card_moves = self._make_card()
        moves_layout = QHBoxLayout(self.card_moves)
        mid_row.addWidget(self.card_moves)
        
        lbl_lunch = QLabel("Lunch Duration (hrs):")
        lbl_lunch.setFont(self._system_ui_font(12, bold=True))
        moves_layout.addWidget(lbl_lunch)
        self.lunch_duration_input = QSpinBox()
        self.lunch_duration_input.setFont(self._system_ui_font(12))
        self.lunch_duration_input.setRange(0, 12)
        self.lunch_duration_input.setValue(1)
        moves_layout.addWidget(self.lunch_duration_input)
        self.auto_lunch_toggle = QCheckBox("Auto Lunch Timing")
        self.auto_lunch_toggle.setFont(self._system_ui_font(12))
        self.auto_lunch_toggle.setChecked(True)
        moves_layout.addWidget(self.auto_lunch_toggle)
        moves_layout.addStretch
                # Company moves label + combo
        lbl_moves = QLabel("Company moves:")
        lbl_moves.setFont(label_font)
        moves_layout.addWidget(lbl_moves)
        self.company_moves_input = QComboBox()
        self.company_moves_input.addItems([str(i) for i in range(0, 21)])  # 0..20
        self.company_moves_input.setFont(self._system_ui_font(12))
        moves_layout.addWidget(self.company_moves_input)

        lbl_moves = QLabel("Company Move Duration (mins):")
        lbl_moves.setFont(self._system_ui_font(12, bold=True))
        moves_layout.addWidget(lbl_moves)
        self.move_duration_input = QSpinBox()
        self.move_duration_input.setFont(self._system_ui_font(12))
        self.move_duration_input.setRange(0, 12)
        self.move_duration_input.setValue(1)
        moves_layout.addWidget(self.move_duration_input)

        self.include_moves_lunch_toggle = QCheckBox("Calculate with Moves && Lunch")
        self.include_moves_lunch_toggle.setFont(self._system_ui_font(12))
        self.include_moves_lunch_toggle.setChecked(True)
        moves_layout.addWidget(self.include_moves_lunch_toggle)
        moves_layout.addStretch()









        

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

        self.card_actions = self._make_card()
        act_layout = QHBoxLayout(self.card_actions)
        top_row.addWidget(self.card_actions)
        self.btn_load = QPushButton("Load Fountain")
        self.btn_load.setFont(self._system_ui_font(12, bold=True))
        self.btn_load.clicked.connect(self.load_fountain_file)
        act_layout.addWidget(self.btn_load)
        self.btn_recalc = QPushButton("Recalculate Schedule")
        self.btn_recalc.setFont(self._system_ui_font(12, bold=True))
        self.btn_recalc.clicked.connect(self.recalculate_schedule)
        act_layout.addWidget(self.btn_recalc)
        self.btn_export = QPushButton("Export")
        self.btn_export.setFont(self._system_ui_font(12, bold=True))
        self.btn_export.clicked.connect(self.export_file)
        act_layout.addWidget(self.btn_export)
        self.btn_preview = QPushButton("Preview")
        self.btn_preview.setFont(self._system_ui_font(12, bold=True))
        self.btn_preview.clicked.connect(self.open_preview_modal)
        act_layout.addWidget(self.btn_preview)


        

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Scene #", "Slugline", "Page Count", "Setups", "Length", "Start", "End"])
        self.table.setFont(self._system_ui_font(12))
        layout.addWidget(self.table)
        bottom_row = QHBoxLayout()
        layout.addLayout(bottom_row)
        self.last_recalc_label = QLabel("Last recalculated: --:--:--")
        self.last_recalc_label.setFont(self._system_ui_font(12, italic=True))
        bottom_row.addWidget(self.last_recalc_label)
        bottom_row.addStretch()
# End of Part 1
# ------------------------------------------------------------
# When you're ready, ask for Part 2 (scheduling, recalc, export helpers, table population).
# Then ask for Part 3 (Preview modal QtPDF integration + entry point).
# ------------------------------------------------------------
# ------------------------------------------------------------
# Producers-Toolkit_v0.19.1-test.py  (PART 2 of 3)
# ------------------------------------------------------------
# This part contains:
#   - settings persistence helpers (_load_settings and _save_settings)
#   - badge updates and WPP helpers
#   - core scheduling algorithms (calculate_schedule, compute_scene_time)
#   - table population (populate_table) and row update handlers
#   - summary row insertion / removal and animations
#   - export helpers (_write_exports, export_file) and export wrapper
#   - recalc wrappers and feedback dialogs
# ------------------------------------------------------------

    # ------------------------
    # SETTINGS: load saved preferences from SETTINGS_FILE
    # ------------------------
    def _load_settings(self):
        """
        Load saved preferences from 'settings.json' and apply them to controls.
        This method will be called at startup (after UI construction).
        Safe: if the file is absent or malformed, defaults are used.
        """
        # if the settings file does not exist, do nothing
        if not os.path.exists(SETTINGS_FILE):
            return

        try:
            # open and parse JSON
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                s = json.load(f)

            # words per page (if custom was used)
            if s.get("custom_wpp", False):
                # enable custom toggle and set spinbox
                self.custom_wpp_toggle.setChecked(True)
                # set the spinbox, guard with min/max
                try:
                    val = int(s.get("words_per_page", DEFAULTS["words_per_page"]))
                except Exception:
                    val = DEFAULTS["words_per_page"]
                self.wpp_spin.setValue(val)
                self.wpp_spin.setEnabled(True)
                self.words_per_page = val
            else:
                # ensure the spinbox is disabled if custom not used
                self.custom_wpp_toggle.setChecked(False)
                self.wpp_spin.setEnabled(False)
                self.words_per_page = DEFAULTS["words_per_page"]

            # setup minutes
            if "setup_minutes" in s:
                try:
                    sm = int(s["setup_minutes"])
                except Exception:
                    sm = DEFAULTS["setup_minutes"]
                self.setup_minutes = sm
                self.setup_minutes_spin.setValue(sm)

            # lunch mode (auto/fixed)
            if "lunch_auto" in s:
                try:
                    self.lunch_auto_toggle.setChecked(bool(s["lunch_auto"]))
                except Exception:
                    self.lunch_auto_toggle.setChecked(True)

            # fixed lunch hours
            if "lunch_fixed_hours" in s:
                try:
                    self.lunch_duration_input.setValue(int(s["lunch_fixed_hours"]))
                except Exception:
                    self.lunch_duration_input.setValue(6)

            # lock setups state
            if "lock_setups" in s:
                try:
                    self.lock_setups_toggle.setChecked(bool(s["lock_setups"]))
                except Exception:
                    self.lock_setups_toggle.setChecked(False)

            # reflect changes visually
            self._update_badges()
        except Exception:
            # if anything goes wrong reading the file, ignore and keep defaults
            return

    # ------------------------
    # SETTINGS: save preferences to SETTINGS_FILE
    # ------------------------
    def _save_settings(self):
        """
        Save the current user preferences to 'settings.json'.
        This is invoked when the user confirms Export (as per the UX decision).
        """
        try:
            data = {
                "custom_wpp": bool(self.custom_wpp_toggle.isChecked()),
                "words_per_page": int(self.wpp_spin.value()) if self.custom_wpp_toggle.isChecked() else DEFAULTS["words_per_page"],
                "setup_minutes": int(self.setup_minutes_spin.value()),
                "lunch_auto": bool(self.lunch_auto_toggle.isChecked()),
                "lunch_fixed_hours": int(self.lunch_duration_input.value()),
                "lock_setups": bool(self.lock_setups_toggle.isChecked())
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # silently ignore save errors (don't block the export flow)
            pass

    # ------------------------
    # Update the badges (Lunch Mode, Setup Time) instantly
    # ------------------------
    def _update_badges(self):
        """
        Update the two small badges in the top-right to reflect current state.
        Called whenever lunch mode or setup minutes change, or on load.
        """
        # lunch badge: green for Auto, blue for Fixed
        if self.lunch_auto_toggle.isChecked():
            self.badge_lunch.setText("Auto Lunch Mode")
            self.badge_lunch.setStyleSheet(self._badge_style("#C8E6C9"))
        else:
            self.badge_lunch.setText("Fixed Lunch Mode")
            self.badge_lunch.setStyleSheet(self._badge_style("#BBDEFB"))

        # setup badge: neutral gray showing minutes value
        self.badge_setup.setText(f"Setup Time: {self.setup_minutes} min")
        self.badge_setup.setStyleSheet(self._badge_style("#E0E0E0"))

    # ------------------------
    
    # ------------------------
    # Minutes-per-setup change handler (fast recalc)
    # ------------------------
    def setup_minutes_changed(self, val):
        """
        When the LX & Camera Setup Time spinbox changes:
         - update internal state
         - update badges
         - run fast non-animated recalculation for responsiveness
        """
        try:
            self.setup_minutes = int(val)
        except Exception:
            self.setup_minutes = DEFAULTS["setup_minutes"]
        self._update_badges()
        # quick recalculation without animation
        self.recalculate_schedule()

    # ------------------------
    # Lock default setups toggle handler
    # ------------------------
    def toggle_default_setups_lock(self, state):
        """
        When locking default setups, enforce defaults (INT/EXT) across all rows and disable
        per-row combo boxes (visible but read-only). When unlocked, re-enable combos.
        """
        lock_on = bool(state)
        # iterate all table rows and apply change to column 5 (setups combo)
        for r in range(self.table.rowCount()):
            widget = self.table.cellWidget(r, 5)
            if widget is not None:
                try:
                    if lock_on:
                        # determine if row is INT or EXT by heading
                        item = self.table.item(r, 0)
                        heading_text = item.text() if item else ""
                        if heading_text.upper().startswith("INT"):
                            widget.setCurrentText(str(DEFAULTS["setups_int"]))
                        else:
                            widget.setCurrentText(str(DEFAULTS["setups_ext"]))
                        widget.setEnabled(False)  # visible but locked
                    else:
                        widget.setEnabled(True)   # re-enable for user edits
                except Exception:
                    continue
        # animate the recalculation so the summary rows reflect new values
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Lunch mode changed handler
    # ------------------------
    def lunch_mode_changed(self, state):
        """
        When the Lunch Placement Mode checkbox changes (Auto <-> Fixed), update badges and
        re-run animated recalculation to reflect new insertion behavior.
        """
        self._update_badges()
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Fixed lunch hours changed handler
    # ------------------------
    def lunch_fixed_hours_changed(self, val):
        """
        If user adjusts the fixed lunch hours and Fixed mode is active, recalculate
        so the lunch position updates immediately.
        """
        if not self.lunch_auto_toggle.isChecked():
            self.trigger_recalc_with_row_fades()

    # ------------------------
    # Load a Fountain file and populate table
    # ------------------------
    def load_fountain_file(self):
        """
        Open a file dialog for a .fountain file, read it, parse scenes, and populate the table.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Fountain", "", "Fountain Files (*.fountain)")
        if not file_path:
            return

        # store path for export default location
        self.current_fountain_path = file_path

        # read file content (assume UTF-8)
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Could not read file: {e}")
            return

        # parse fountain content into scene list
        self.scenes = self.parse_fountain(content)

        # populate the table UI with scenes
        self.populate_table()

        # if lock_setups was on earlier, reapply lock to new rows
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

        # update badges
        self._update_badges()

    # ------------------------
    # Simple Fountain parser (INT./EXT. headings)
    # ------------------------
    def parse_fountain(self, content):
        """
        Very small Fountain parser:
         - lines starting with INT. or EXT. are considered scene headings
         - following lines up to the next heading are the scene content
        Returns: list of {'heading': str, 'content': [lines]}
        """
        scenes = []
        current = None
        for line in content.splitlines():
            stripped = line.strip()
            # detect heading (case-insensitive)
            if re.match(r"^(INT\.|EXT\.)", stripped, re.I):
                # push previous scene if present
                if current:
                    scenes.append(current)
                # start new scene
                current = {"heading": stripped, "content": []}
            elif current is not None:
                # accumulate content lines for current scene
                current["content"].append(stripped)
        # push final scene
        if current:
            scenes.append(current)
        return scenes

    # ------------------------
    # Scene page-length & mm:ss calculation
    # ------------------------
    def calculate_scene_length(self, scene_text):
        """
        Given a list of strings (scene content), calculate:
          - page representation (e.g., "1 3/8" or "2")
          - estimated MM:SS shooting length based on pages * 60 sec/page
        Returns: (page_str, mmss_str)
        """
        # count words in the scene content
        words = len(re.findall(r"\w+", " ".join(scene_text)))
        # effective words per page
        wpp = DEFAULTS["words_per_page"]
        # compute fractional pages
        pages = (words / wpp) if wpp > 0 else 0.0
        full = int(pages)
        # compute eighths of a page
        eighths = int(round((pages - full) * 8))
        # carry if rounding gave 8 eighths
        if eighths == 8:
            full += 1
            eighths = 0
        # format page string
        if full == 0 and eighths > 0:
            page_str = f"{eighths}/8"
        elif eighths > 0:
            page_str = f"{full} {eighths}/8"
        else:
            page_str = f"{full}"
        # estimate seconds (1 page ~= 60 seconds)
        seconds = int(round(pages * 60))
        mm, ss = divmod(seconds, 60)
        mmss = f"{mm:02}:{ss:02}"
        return page_str, mmss

    # ------------------------
    # Compute shooting time (seconds) for a row (includes setups)
    # ------------------------
    def compute_scene_time(self, row):
        """
        For a given table row index corresponding to a scene, compute the total shooting time:
          base time derived from the MM:SS column + (setups_count * self.setup_minutes).
        Returns total seconds as integer.
        """
        # safety: check cell widget (setups combo) and length cell exist
        setups_widget = self.table.cellWidget(row, 5)
        length_item = self.table.item(row, 4)
        if setups_widget is None or length_item is None:
            return 0

        # parse setups number
        try:
            setups_val = int(setups_widget.currentText())
        except Exception:
            setups_val = 0

        # parse mm:ss from length column
        try:
            mm, ss = map(int, length_item.text().split(":"))
        except Exception:
            mm, ss = 0, 0

        # base minutes + setups penalty minutes
        base_minutes = mm + ss / 60.0
        total_minutes = base_minutes + setups_val * self.setup_minutes

        # convert to seconds and round
        return int(round(total_minutes * 60))

    # ------------------------
    # Handler when a per-row setups combo changes
    # ------------------------
    def update_scene_row_for_box(self, box):
        """
        Given a QComboBox (setups) which changed, find its row, recompute that row's shooting time,
        update the cell, and trigger animated recalculation of summary rows.
        """
        # try to locate row using indexAt on widget pos
        idx = self.table.indexAt(box.pos())
        row = idx.row()
        # fallback: iterate rows to find the widget
        if row == -1:
            for r in range(self.table.rowCount()):
                if self.table.cellWidget(r, 5) is box:
                    row = r
                    break
        # if still not found, bail out
        if row == -1:
            return

        # compute seconds for this row using compute_scene_time
        secs = self.compute_scene_time(row)
        # update the Shooting Time column (column 6) with HH:MM:SS via timedelta
        self.table.setItem(row, 6, QTableWidgetItem(str(timedelta(seconds=secs))))
        # animate recalculation to update summaries (lunch/total/wrap)
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Remove summary rows (LUNCH, TOTAL SHOOT LENGTH, ESTIMATED WRAP)
    # ------------------------
    def remove_summary_rows(self):
        """
        Walk backwards through the table and remove rows that are summary rows (based on prefix).
        We iterate in reverse so row indices do not shift during removal.
        """
        for r in reversed(range(self.table.rowCount())):
            item = self.table.item(r, 0)
            if item is None:
                continue
            text = item.text()
            if any(text.startswith(prefix) for prefix in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                self.table.removeRow(r)

    # ------------------------
    # Animated recalculation: remove old summaries, compute new, insert with fade
    # ------------------------
    def trigger_recalc_with_row_fades(self):
        """
        Update the summaries with a per-row fade animation, intended for visible user triggers.
        """
        # remove existing summary rows before recomputing
        self.remove_summary_rows()

        # compute schedule values
        total, wrap, lunch_start, insert_index = self.calculate_schedule()

        # insert lunch row if applicable
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.value()), animate=True)

        # insert total and wrap rows (appended at bottom)
        self.insert_total_row(total, animate=True)
        self.insert_wrap_row(wrap, animate=True)

        # refresh numbering of sidebar
        self.update_row_numbers()

        # update last recalculated timestamp label
        self._update_last_recalc_timestamp()

    # ------------------------
    # Fast recalculation (no animation) used for quick UI changes
    # ------------------------
    def recalculate_schedule(self):
        """
        A faster recalculation that avoids animations; used for spin changes and internal quick updates.
        """
        self.remove_summary_rows()
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.value()), animate=False)
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)
        self.update_row_numbers()
        self._update_last_recalc_timestamp()

    # ------------------------
    # Calculate schedule algorithm (where to place lunch, wrap time, total seconds)
    # ------------------------
    def calculate_schedule(self):
        """
        Core scheduling algorithm:
          - Sum scene durations (which include setups)
          - If include moves & lunch checkbox is checked:
              * Auto mode: insert lunch at midpoint (after scene where running >= midpoint)
              * Fixed mode: insert lunch after scene where running >= fixed_hours * 3600,
                            or after last scene if fixed time beyond total duration
          - Compute total seconds including lunch & moves if included
          - Return (total_scene_seconds, wrap_time_str, lunch_start_datetime_or_None, insert_index_or_None)
        """
        # compute per-scene durations and total
        total_scene_seconds = 0
        durations = []
        for i in range(len(self.scenes)):
            secs = self.compute_scene_time(i)
            durations.append(secs)
            total_scene_seconds += secs

        # read UI extras
        lunch_min = int(self.lunch_duration_input.value())
        lunch_dur = lunch_min * 60
        move_min = int(self.move_duration_input.value()) * 60
        move_count = int(self.company_moves_input.currentText())
        include = self.include_moves_lunch_toggle.isChecked()

        # initialize outputs
        lunch_start = None
        insert_index = None

        # start time as datetime (today's date is irrelevant - we just need HH:MM)
        start_dt = datetime.strptime(self.start_time_input.currentText(), "%H:%M")

        # if extras are to be included, compute lunch insertion point
        if include:
            if self.auto_lunch_toggle.isChecked():
                # Auto: compute midpoint and insert after first scene where running >= midpoint
                midpoint = total_scene_seconds // 2
                running = 0
                for i, secs in enumerate(durations):
                    running += secs
                    if running >= midpoint:
                        insert_index = i + 1
                        lunch_start = start_dt + timedelta(seconds=running)
                        break
                # fallback if no durations (empty script)
                if insert_index is None:
                    insert_index = len(durations)
                    lunch_start = start_dt
            else:
                # Fixed mode: insert after scene where running >= fixed_seconds
                fixed_hours = int(self.lunch_duration_input.value())
                fixed_seconds = fixed_hours * 3600
                running = 0
                for i, secs in enumerate(durations):
                    running += secs
                    if running >= fixed_seconds:
                        insert_index = i + 1
                        lunch_start = start_dt + timedelta(seconds=running)
                        break
                # if fixed_seconds beyond total_scene_seconds, place after last scene
                if insert_index is None:
                    insert_index = len(durations)
                    lunch_start = start_dt + timedelta(seconds=fixed_seconds)

        # compute total seconds including moves & lunch if included
        total_seconds = total_scene_seconds
        if include:
            total_seconds += lunch_dur + (move_min * move_count)

        # compute wrap clock time string (HH:MM)
        wrap_dt = start_dt + timedelta(seconds=total_seconds)
        return total_scene_seconds, wrap_dt.strftime("%H:%M"), lunch_start, insert_index

    # ------------------------
    # Populate the table with scene rows and initial summary rows (non-animated)
    # ------------------------
    def populate_table(self):
        """
        Build the QTableWidget based on the parsed self.scenes list.
        For each scene:
          - compute page length and mm:ss
          - create setups combo with default INT/EXT values
          - attach handlers
        Then compute and insert summary rows (non-animated) for initial load.
        """
        # clear any spans/items
        self.table.clearSpans()
        self.table.clear()
        # remove any lingering summary rows (defensive)
        self.remove_summary_rows()

        # define headers (keep the Camera Setups header included as requested)
        headers = [
            "Scene Heading", "Actions", "Dialogue",
            "Length (pages+1/8s)", "Length (MM:SS)",
            "Camera Setups (Count)", "Shooting Time (HH:MM:SS)"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        # set row count equal to number of scenes
        self.table.setRowCount(len(self.scenes))

        # iterate scenes and fill rows
        for i, sc in enumerate(self.scenes):
            heading = sc["heading"]
            # calculate page and mm:ss length
            page_len, mmss = self.calculate_scene_length(sc["content"])

            # create setups combo (1..20)
            setups_box = QComboBox()
            setups_box.addItems([str(n) for n in range(1, 21)])
            # apply INT/EXT default
            if heading.upper().startswith("INT"):
                setups_box.setCurrentText(str(DEFAULTS["setups_int"]))
            else:
                setups_box.setCurrentText(str(DEFAULTS["setups_ext"]))

            # connect change handler that references this specific box
            # use lambda capturing 'box' to avoid late-binding closure issues
            setups_box.currentTextChanged.connect(lambda t, box=setups_box: self.update_scene_row_for_box(box))

            # set items/cells
            self.table.setItem(i, 0, QTableWidgetItem(heading))      # Scene Heading
            self.table.setItem(i, 3, QTableWidgetItem(page_len))     # Length (pages)
            self.table.setItem(i, 4, QTableWidgetItem(mmss))         # Length (MM:SS)
            self.table.setCellWidget(i, 5, setups_box)               # Setups combo
            # compute shooting time and set HH:MM:SS string
            self.table.setItem(i, 6, QTableWidgetItem(str(timedelta(seconds=self.compute_scene_time(i)))))

        # after populating scenes, compute summaries (non-animated for initial load)
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.value()), animate=False)
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)

        # if lock setups toggled on, apply lock
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

        # refresh badges and numbering
        self._update_badges()
        self.update_row_numbers()
        # update last recalculated timestamp
        self._update_last_recalc_timestamp()

    # ------------------------
    # Helper: create centered bold 12pt item with background color for summary rows
    # ------------------------
    def make_centered_item(self, text, color):
        """
        Build a QTableWidgetItem with centered text, bold 12pt font, and background color.
        Used for LUNCH / TOTAL / WRAP rows.
        """
        item = QTableWidgetItem(text)
        item.setBackground(QBrush(QColor(color)))
        item.setFont(self._system_ui_font(12, bold=True))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    # ------------------------
    # Row fade animation overlay
    # ------------------------
    def animate_row(self, row):
        """
        Create a transparent overlay widget covering the row and animate its opacity from 0 -> 1.
        Used to make inserted summary rows feel lively.
        """
        overlay = QWidget(self.table.viewport())
        # find rectangle for the row (use model index for column 0)
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
    # Insert the lunch summary row (spanning all columns)
    # ------------------------
    def insert_lunch_row(self, row_index, lunch_start_dt, lunch_minutes, animate=True):
        """
        Insert a single-row lunch summary at row_index. The row's first cell is spanned across all columns
        so it appears as one merged cell visually. The text includes start time and the duration in parentheses.
        """
        # insert a blank row at the desired index
        self.table.insertRow(row_index)
        # create descriptive text: "LUNCH — Starts at HH:MM (HH:MM:SS)"
        text = f"LUNCH — Starts at {lunch_start_dt.strftime('%H:%M')} ({str(timedelta(minutes=lunch_minutes))})"
        # create styled item
        item = self.make_centered_item(text, "orange")
        # place item in column 0
        self.table.setItem(row_index, 0, item)
        # span across all columns to create merged effect
        self.table.setSpan(row_index, 0, 1, self.table.columnCount())
        # animate row if requested
        if animate:
            self.animate_row(row_index)

    # ------------------------
    # Insert total shoot length row
    # ------------------------
    def insert_total_row(self, total_seconds, animate=True):
        """
        Append a TOTAL SHOOT LENGTH row at the bottom spanning all columns.
        """
        row = self.table.rowCount()
        self.table.insertRow(row)
        text = f"TOTAL SHOOT LENGTH — {str(timedelta(seconds=total_seconds))}"
        item = self.make_centered_item(text, "lightgreen")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row)

    # ------------------------
    # Insert estimated wrap row
    # ------------------------
    def insert_wrap_row(self, wrap_str, animate=True):
        """
        Append an ESTIMATED WRAP row at the bottom spanning all columns.
        """
        row = self.table.rowCount()
        self.table.insertRow(row)
        text = f"ESTIMATED WRAP — {wrap_str}"
        item = self.make_centered_item(text, "lightblue")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row)

    # ------------------------
    # Update row numbering (vertical header): only number actual scene rows
    # ------------------------
    def update_row_numbers(self):
        """
        Number only the scene rows in the vertical header; summary rows have blank headers.
        The numbering uses row index + 1 to keep it simple.
        """
        for r in range(self.table.rowCount()):
            # ensure header item exists
            if not self.table.verticalHeaderItem(r):
                self.table.setVerticalHeaderItem(r, QTableWidgetItem())
            header_item = self.table.verticalHeaderItem(r)
            first_item = self.table.item(r, 0)
            # if the first cell text starts with a summary prefix, leave header blank
            if first_item and any(first_item.text().startswith(p) for p in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                header_item.setText("")
            else:
                header_item.setText(str(r + 1))

    # ------------------------
    # Gather table data as list-of-lists (header row included)
    # ------------------------
    def get_table_data(self):
        """
        Extract the table contents into a list-of-lists structure:
          [ [header1, header2, ...], [row1col1, row1col2, ...], ... ]
        Used for CSV/PDF export and preview.
        """
        headers = []
        for i in range(self.table.columnCount()):
            h = self.table.horizontalHeaderItem(i)
            headers.append(h.text() if h else "")
        data = [headers]

        # iterate rows and columns grabbing text or widget values
        for r in range(self.table.rowCount()):
            rowd = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                if item:
                    rowd.append(item.text())
                else:
                    widget = self.table.cellWidget(r, c)
                    if widget:
                        # prefer currentText for combos, text for labels
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
    # Low-level export writer used by preview and export flows
    # ------------------------
    def _write_exports(self, csv_path, pdf_path, choice="Export Both"):
        """
        Write CSV and/or PDF to the provided absolute paths according to 'choice'.
        Returns tuple: (csv_written_path_or_None, pdf_written_path_or_None)
        This function avoids showing message boxes so it can be used by the Preview modal.
        """
        data = self.get_table_data()
        csv_written = None
        pdf_written = None

        # CSV writing
        if choice in ("Export CSV", "Export Both"):
            try:
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerows(data)
                csv_written = csv_path
            except Exception:
                csv_written = None

        # PDF writing via ReportLab
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
                # color and span summary rows
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
    # Export flow that shows message boxes to the user
    # ------------------------
    def export_file(self):
        """
        Export CSV and/or PDF next to the loaded fountain file and show message boxes on success/failure.
        Returns paths written or (None, None) on failure.
        """
        # require a loaded fountain file to derive default output path
        if not self.current_fountain_path:
            QMessageBox.warning(self, "No File", "Load a Fountain file first.")
            return None, None

        base = os.path.dirname(self.current_fountain_path)
        name = os.path.splitext(os.path.basename(self.current_fountain_path))[0]
        csv_path = os.path.join(base, f"breakdown_{name}.csv")
        pdf_path = os.path.join(base, f"breakdown_{name}.pdf")

        choice = self.export_dropdown.currentText()

        csv_written, pdf_written = self._write_exports(csv_path, pdf_path, choice=choice)

        # user feedback
        if csv_written:
            QMessageBox.information(self, "Export Complete", f"CSV exported to: {csv_written}")
        if pdf_written:
            QMessageBox.information(self, "Export Complete", f"PDF exported to: {pdf_written}")
        if not csv_written and not pdf_written:
            QMessageBox.critical(self, "Export Error", "No files could be exported (check permissions).")

        return csv_written, pdf_written

    # ------------------------
    # Export wrapper: warn about saving preferences, then save and export
    # ------------------------
    def _export_with_save_warning(self):
        """
        Prompt the user that exporting will save preferences to settings.json.
        If the user confirms, save settings and perform export_file().
        """
        # warn the user that preferences will be saved as part of export
        reply = QMessageBox.question(
            self,
            "Export and Save Preferences",
            "Exporting will also save your preferences to settings.json. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            return

        # save settings (preferences persist)
        self._save_settings()

        # perform actual export
        self.export_file()

        # update badges and last-recalc label for clarity
        self._update_badges()
        self._update_last_recalc_timestamp()

    # ------------------------
    # Recalculate wrapper with feedback message
    # ------------------------
    def _recalculate_and_feedback(self):
        """
        Trigger an animated recalc and notify the user via a small messagebox when complete.
        """
        # perform the animated recalc (updates last-recalc timestamp internally)
        self.trigger_recalc_with_row_fades()
        # let the user know the schedule was recalculated
        QMessageBox.information(self, "Recalculated", "Schedule successfully updated.")

# End of Part 2
# ------------------------------------------------------------
# Ask for Part 3 when ready: Preview modal (QtPDF integration), entrypoint, and any final utilities.
# ------------------------------------------------------------
# ------------------------------------------------------------
# Producers-Toolkit_v0.19.1-test.py  (PART 3 of 3)
# ------------------------------------------------------------
# Contains:
#   - _badge_style() helper
#   - _update_last_recalc_timestamp()
#   - Preview modal with QtPDF integration (auto-load)
#   - __main__ entry point
# ------------------------------------------------------------

    # ------------------------
    # Helper: badge style (rounded pill label background)
    # ------------------------
    def _badge_style(self, bg_color):
        """
        Return a CSS string for a rounded badge label with given background color.
        """
        return (
            f"background-color: {bg_color}; "
            "color: #000000; "
            "border-radius: 10px; "
            "padding: 2px 8px;"
        )

    # ------------------------
    # Update "Last recalculated" timestamp label
    # ------------------------
    def _update_last_recalc_timestamp(self):
        """
        Replace the timestamp label with the current time.
        """
        now = datetime.now().strftime("%H:%M:%S")
        self.last_recalc_label.setText(f"Last recalculated: {now}")

    # ------------------------
    # PREVIEW MODAL with QtPDF auto-load
    # ------------------------
    
def open_preview_modal(self):
    """
    Open a modal dialog to preview CSV and PDF exports.
    Uses QtPDF (QPdfDocument + QPdfView) when available for live multi-page preview.
    Falls back to CSV text preview and a helpful message if QtPDF is not installed.
    This preview writes to a temporary preview-only PDF so user exports are not overwritten.
    """
    import csv as _csv
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    # create temp paths (unique)
    tempdir = tempfile.gettempdir()
    unique = str(uuid.uuid4())[:8]
    csv_path = os.path.join(tempdir, f"producers_toolkit_preview_{unique}.csv")
    pdf_path = os.path.join(tempdir, f"producers_toolkit_preview_{unique}.pdf")

    # prefer existing _write_exports if available
    wrote_csv = False
    wrote_pdf = False
    try:
        if hasattr(self, "_write_exports"):
            self._write_exports(csv_path, pdf_path, choice="Export Both")
            wrote_csv = os.path.exists(csv_path)
            wrote_pdf = os.path.exists(pdf_path)
    except Exception:
        wrote_csv = False
        wrote_pdf = False

    # fallback CSV/PDF writer if needed
    if not (wrote_csv and wrote_pdf):
        # CSV
        try:
            if hasattr(self, "get_table_data"):
                data = self.get_table_data()
            else:
                headers = [self.table.horizontalHeaderItem(i).text() if self.table.horizontalHeaderItem(i) else "" for i in range(self.table.columnCount())]
                data = [headers]
                for r in range(self.table.rowCount()):
                    rowd = []
                    for c in range(self.table.columnCount()):
                        it = self.table.item(r, c)
                        if it:
                            rowd.append(it.text())
                        else:
                            widget = self.table.cellWidget(r, c)
                            if widget and hasattr(widget, "currentText"):
                                rowd.append(widget.currentText())
                            else:
                                rowd.append("")
                    data.append(rowd)
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                _csv.writer(f).writerows(data)
            wrote_csv = True
        except Exception:
            wrote_csv = False

        # PDF via reportlab
        try:
            styles = getSampleStyleSheet()
            formatted = [[Paragraph(str(cell), styles["Normal"]) for cell in row] for row in data]
            table = Table(formatted)
            ts = TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ])
            table.setStyle(ts)
            SimpleDocTemplate(pdf_path, pagesize=letter).build([table])
            wrote_pdf = True
        except Exception:
            wrote_pdf = False

    # Build modal
    dlg = QDialog(self)
    dlg.setWindowTitle("Preview — Producer's Toolkit (Temporary)")
    dlg.resize(1000, 700)
    dlg.setModal(True)
    layout = QVBoxLayout(dlg)
    tabs = QTabWidget()
    layout.addWidget(tabs)

    # CSV tab
    csv_tab = QWidget()
    csv_layout = QVBoxLayout(csv_tab)
    csv_browser = QTextBrowser()
    csv_browser.setFont(self._system_ui_font(12))
    if wrote_csv and os.path.exists(csv_path):
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                csv_browser.setText(f.read())
        except Exception as e:
            csv_browser.setText(f"Could not load CSV preview: {e}")
    else:
        csv_browser.setText("CSV preview not available.")
    csv_layout.addWidget(csv_browser)
    tabs.addTab(csv_tab, "CSV Preview")

    # PDF tab
    pdf_tab = QWidget()
    pdf_layout = QVBoxLayout(pdf_tab)
    if QT_PDF_AVAILABLE and wrote_pdf and os.path.exists(pdf_path):
        try:
            doc = QPdfDocument(dlg)
            load_result = doc.load(pdf_path)
            if doc.pageCount() > 0:
                view = QPdfView()
                view.setDocument(doc)
                try:
                    view.setZoomMode(QPdfView.ZoomMode.FitInView)
                except Exception:
                    pass
                # hold references
                self._preview_pdf_doc = doc
                self._preview_pdf_view = view
                pdf_layout.addWidget(view)
            else:
                lbl = QLabel("PDF generated but contains no pages.")
                lbl.setFont(self._system_ui_font(12))
                pdf_layout.addWidget(lbl)
        except Exception as e:
            lbl = QLabel(f"PDF preview error: {e}")
            lbl.setFont(self._system_ui_font(12))
            pdf_layout.addWidget(lbl)
    else:
        lbl = QLabel("QtPDF not available or PDF not generated.\\nInstall PyQt6-QtPdf and PyQt6-QtPdfWidgets for live preview.")
        lbl.setFont(self._system_ui_font(12))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pdf_layout.addWidget(lbl)
    tabs.addTab(pdf_tab, "PDF Preview")

    # Bottom buttons
    btns = QHBoxLayout()
    layout.addLayout(btns)
    btns.addStretch()
    open_btn = QPushButton("Open Preview File")
    open_btn.setFont(self._system_ui_font(12))
    btns.addWidget(open_btn)
    close_btn = QPushButton("Close Preview")
    close_btn.setFont(self._system_ui_font(12))
    btns.addWidget(close_btn)

    def _open_external():
        path_to_open = pdf_path if os.path.exists(pdf_path) else csv_path if os.path.exists(csv_path) else None
        if not path_to_open:
            QMessageBox.information(self, "Nothing to open", "No preview file available to open.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path_to_open)
            elif sys.platform == "darwin":
                os.system(f"open '{path_to_open}'")
            else:
                os.system(f"xdg-open '{path_to_open}'")
        except Exception as e:
            QMessageBox.warning(self, "Open Error", f"Could not open file: {e}")

    open_btn.clicked.connect(_open_external)
    close_btn.clicked.connect(dlg.close)

    def _on_close():
        try:
            if hasattr(self, "_preview_pdf_doc"):
                try:
                    del self._preview_pdf_view
                except Exception:
                    pass
                try:
                    del self._preview_pdf_doc
                except Exception:
                    pass
        except Exception:
            pass

    dlg.finished.connect(_on_close)
    dlg.exec()

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

        # show dialog modally
        dlg.exec()

# ------------------------------------------------------------
# Application entry point
# ------------------------------------------------------------
# Enable high-DPI scaling for sharper UI on modern screens
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
if __name__ == "__main__":
    # Create Qt application instance
    app = QApplication(sys.argv)

    


    # Create and show main window
    window = ProducersToolkit()
    window.show()

    # Run the application event loop
    sys.exit(app.exec())
# ------------------------------------------------------------
# END OF FILE
# ------------------------------------------------------------
