# ------------------------------------------------------------
# PRODUCER'S TOOLKIT - Version v0.18.3-pre
# ------------------------------------------------------------
# Changes in this version:
#  - Adds status badges (top-right) showing Lunch Mode and Setup Time (instant updates).
#  - Fixes the Fixed Lunch Mode insertion bug (lunch now appears correctly).
#  - Makes the UI more compact and stylish while preserving 12pt readability.
#  - Keeps single-file PyQt6 structure, per-row fade summary animations, and export features.
# ------------------------------------------------------------

# ------------------------
# Standard library imports
# ------------------------
import sys                         # access to argv and exit
import os                          # path manipulation for exports
import re                          # simple Fountain parsing
import csv                         # CSV export
from datetime import timedelta, datetime  # time arithmetic and formatting

# ------------------------
# PyQt6 imports (GUI)
# ------------------------
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLabel, QSpinBox, QCheckBox,
    QMessageBox, QFileDialog, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, QPropertyAnimation
from PyQt6.QtGui import QBrush, QColor, QFont

# ------------------------
# ReportLab imports (PDF export)
# ------------------------
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ------------------------
# Constants and defaults
# ------------------------
DEFAULTS = {
    "words_per_page": 150,    # default words-per-page
    "setup_minutes": 5,       # default minutes per setup
    "setups_int": 3,          # default setups for INT scenes
    "setups_ext": 5,          # default setups for EXT scenes
    "default_move_duration": 10,
    "default_lunch_duration": 60,
    "default_start_time": "08:00"
}

FADE_DURATION_MS = 500      # milliseconds for row fade animations
CARD_BG = "#f8f9fb"         # card background color
CARD_PADDING = 8            # inner padding for cards
CARD_RADIUS = 6             # rounded corner radius
CARD_SHADOW_BLUR = 12       # shadow blur for compact feel
CARD_SHADOW_OFFSET = (0, 3) # shadow offset

# ------------------------
# Main window class
# ------------------------
class ProducersToolkit(QMainWindow):
    """
    Main application window for the Producer's Toolkit.
    Contains:
      - top bar with load button and status badges
      - three compact "cards" for global controls
      - main table with scene rows and summary rows (lunch, total, wrap)
      - export controls
    """

    def __init__(self):
        # initialize base QMainWindow
        super().__init__()

        # window title and size
        self.setWindowTitle("Producer's Toolkit  v0.18.3-pre")
        self.resize(1400, 900)

        # application state variables
        self.scenes = []                         # parsed scenes list
        self.current_fountain_path = ""          # path to loaded fountain file
        self.words_per_page = DEFAULTS["words_per_page"]
        self.setup_minutes = DEFAULTS["setup_minutes"]

        # ------------------------
        # Central widget & layout
        # ------------------------
        central = QWidget()                      # create central container
        self.setCentralWidget(central)           # set as central widget
        self.main_layout = QVBoxLayout(central)  # main vertical layout

        # ------------------------
        # Top row: Load button + status badges (right-aligned)
        # ------------------------
        top_row = QHBoxLayout()                  # horizontal layout for top bar
        self.main_layout.addLayout(top_row)      # add to main layout

        # Load Fountain button (left)
        self.load_btn = QPushButton("Load Fountain File")
        self.load_btn.setFont(QFont("Helvetica", 12))
        self.load_btn.clicked.connect(self.load_fountain_file)
        top_row.addWidget(self.load_btn)

        # Spacer between left and right (pushes badges to right)
        top_row.addStretch()

        # Status badges container (small horizontal layout)
        badges_layout = QHBoxLayout()
        # Lunch mode badge label (will be updated in methods)
        self.badge_lunch = QLabel()                # QLabel used as badge
        self.badge_lunch.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        self.badge_lunch.setStyleSheet(self._badge_style("#C8E6C9"))  # default: soft green (Auto)
        self.badge_lunch.setText("Auto Lunch Mode")
        self.badge_lunch.setContentsMargins(8, 4, 8, 4)  # padding inside badge
        badges_layout.addWidget(self.badge_lunch)

        # Setup time badge label (neutral gray)
        self.badge_setup = QLabel()
        self.badge_setup.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        self.badge_setup.setStyleSheet(self._badge_style("#E0E0E0"))  # neutral gray
        self.badge_setup.setText(f"Setup Time: {self.setup_minutes} min")
        self.badge_setup.setContentsMargins(8, 4, 8, 4)
        badges_layout.addWidget(self.badge_setup)

        # add badges layout to top row (right)
        top_row.addLayout(badges_layout)

        # small vertical spacing after top row
        self.main_layout.addSpacing(8)

        # ------------------------
        # Card A: Timing Inputs (compact)
        # ------------------------
        self.card_timing = self._make_card()
        self.main_layout.addWidget(self.card_timing)
        timing_layout = QHBoxLayout(self.card_timing)

        # label font (12pt bold)
        label_font = QFont("Helvetica", 12, QFont.Weight.Bold)

        # Company moves
        lbl_moves = QLabel("Company moves:")
        lbl_moves.setFont(label_font)
        timing_layout.addWidget(lbl_moves)
        self.company_moves_input = QComboBox()
        self.company_moves_input.addItems([str(i) for i in range(0, 21)])
        self.company_moves_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.company_moves_input)

        # Move duration
        lbl_move_dur = QLabel("Move duration (min):")
        lbl_move_dur.setFont(label_font)
        timing_layout.addWidget(lbl_move_dur)
        self.move_duration_input = QComboBox()
        self.move_duration_input.addItems([str(i) for i in range(0, 121)])
        self.move_duration_input.setCurrentText(str(DEFAULTS["default_move_duration"]))
        self.move_duration_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.move_duration_input)

        # Lunch duration
        lbl_lunch_dur = QLabel("Lunch duration (min):")
        lbl_lunch_dur.setFont(label_font)
        timing_layout.addWidget(lbl_lunch_dur)
        self.lunch_duration_input = QComboBox()
        self.lunch_duration_input.addItems([str(i) for i in range(0, 181)])
        self.lunch_duration_input.setCurrentText(str(DEFAULTS["default_lunch_duration"]))
        self.lunch_duration_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.lunch_duration_input)

        # Start time
        lbl_start = QLabel("Start time:")
        lbl_start.setFont(label_font)
        timing_layout.addWidget(lbl_start)
        self.start_time_input = QComboBox()
        times = [f"{h:02}:{m:02}" for h in range(24) for m in (0, 15, 30, 45)]
        self.start_time_input.addItems(times)
        self.start_time_input.setCurrentText(DEFAULTS["default_start_time"])
        self.start_time_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.start_time_input)

        # Include moves & lunch checkbox
        self.include_moves_lunch_toggle = QCheckBox("Include moves & lunch in totals?")
        self.include_moves_lunch_toggle.setFont(label_font)
        self.include_moves_lunch_toggle.setChecked(True)
        timing_layout.addWidget(self.include_moves_lunch_toggle)

        timing_layout.addStretch()
        # small spacing between cards
        self.main_layout.addSpacing(6)

        # ------------------------
        # Card B: Calculation Controls (compact)
        # ------------------------
        self.card_calc = self._make_card()
        self.main_layout.addWidget(self.card_calc)
        calc_layout = QHBoxLayout(self.card_calc)

        # Custom WPP toggle
        self.custom_wpp_toggle = QCheckBox("Use Custom Words Per Page")
        self.custom_wpp_toggle.setFont(label_font)
        self.custom_wpp_toggle.setChecked(False)
        self.custom_wpp_toggle.stateChanged.connect(self.toggle_custom_wpp_changed)
        calc_layout.addWidget(self.custom_wpp_toggle)

        # WPP spinbox
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

        # LX & Camera Setup Time label + spinbox
        lbl_setup = QLabel("LX & Camera Setup Time (min):")
        lbl_setup.setFont(label_font)
        calc_layout.addWidget(lbl_setup)
        self.setup_minutes_spin = QSpinBox()
        self.setup_minutes_spin.setRange(1, 30)
        self.setup_minutes_spin.setValue(self.setup_minutes)
        self.setup_minutes_spin.setFont(QFont("Helvetica", 12))
        self.setup_minutes_spin.valueChanged.connect(self.setup_minutes_changed)
        calc_layout.addWidget(self.setup_minutes_spin)

        # Lock setups toggle
        self.lock_setups_toggle = QCheckBox("Use and Lock Default Number of Setups (INT=3, EXT=5)")
        self.lock_setups_toggle.setFont(label_font)
        self.lock_setups_toggle.setChecked(False)
        self.lock_setups_toggle.stateChanged.connect(self.toggle_default_setups_lock)
        calc_layout.addWidget(self.lock_setups_toggle)

        calc_layout.addStretch()

        # Recalculate button
        self.recalc_button = QPushButton("Recalculate Schedule")
        self.recalc_button.setFont(QFont("Helvetica", 12))
        self.recalc_button.clicked.connect(self.trigger_recalc_with_row_fades)
        calc_layout.addWidget(self.recalc_button)

        self.main_layout.addSpacing(6)

        # ------------------------
        # Card C: Lunch Placement Controls (compact)
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
        # Main Table
        # ------------------------
        self.table = QTableWidget()
        self.main_layout.addWidget(self.table)

        # ------------------------
        # Export row
        # ------------------------
        export_row = QHBoxLayout()
        self.export_dropdown = QComboBox()
        self.export_dropdown.addItems(["Export CSV", "Export PDF", "Export Both"])
        self.export_dropdown.setFont(QFont("Helvetica", 12))
        export_row.addWidget(self.export_dropdown)
        self.export_button = QPushButton("Export")
        self.export_button.setFont(QFont("Helvetica", 12))
        self.export_button.clicked.connect(self.export_file)
        export_row.addWidget(self.export_button)
        export_row.addStretch()
        self.main_layout.addLayout(export_row)

    # ------------------------
    # Helper: make a compact card (QFrame) with shadow-only styling
    # ------------------------
    def _make_card(self):
        """
        Create a QFrame styled as a card with rounded corners and a subtle shadow.
        Returns the created QFrame.
        """
        frame = QFrame()
        # CSS: rounded corners and background
        frame.setStyleSheet(f"background-color: {CARD_BG}; border-radius: {CARD_RADIUS}px; padding:{CARD_PADDING}px;")
        # Add soft drop shadow
        shadow = QGraphicsDropShadowEffect(frame)
        shadow.setBlurRadius(CARD_SHADOW_BLUR)
        shadow.setOffset(*CARD_SHADOW_OFFSET)
        shadow.setColor(QColor(0, 0, 0, 60))
        frame.setGraphicsEffect(shadow)
        return frame

    # ------------------------
    # Helper: badge CSS generator (rounded pill-like label)
    # ------------------------
    def _badge_style(self, bg_hex):
        """
        Return a stylesheet string that makes a QLabel look like a small rounded badge.
        """
        style = (
            f"background-color: {bg_hex}; "
            "color: #000000; "
            "border-radius: 12px; "
            "padding-left: 8px; padding-right: 8px; "
        )
        return style

    # ------------------------
    # Update badges: instant changes to badge text and background
    # ------------------------
    def _update_badges(self):
        """
        Update the Lunch Mode badge and the Setup Time badge instantly.
        Called whenever lunch mode or setup minutes changes or on load.
        """
        # Lunch mode badge color/text
        if self.lunch_auto_toggle.isChecked():
            self.badge_lunch.setText("Auto Lunch Mode")
            self.badge_lunch.setStyleSheet(self._badge_style("#C8E6C9"))  # soft green
        else:
            self.badge_lunch.setText("Fixed Lunch Mode")
            self.badge_lunch.setStyleSheet(self._badge_style("#BBDEFB"))  # soft blue

        # Setup time badge: reflect current minutes per setup
        self.badge_setup.setText(f"Setup Time: {self.setup_minutes} min")
        # neutral gray background stays the same
        self.badge_setup.setStyleSheet(self._badge_style("#E0E0E0"))

    # ------------------------
    # Words-per-page helper (respects toggle)
    # ------------------------
    def get_current_wpp(self):
        if self.custom_wpp_toggle.isChecked():
            return int(self.wpp_spin.value())
        return int(DEFAULTS["words_per_page"])

    # ------------------------
    # Custom WPP toggle changed (animated recalc)
    # ------------------------
    def toggle_custom_wpp_changed(self, state):
        if state:
            self.wpp_spin.setEnabled(True)
            self.words_per_page = int(self.wpp_spin.value())
        else:
            self.wpp_spin.setEnabled(False)
            self.words_per_page = DEFAULTS["words_per_page"]
        # badge update (no change to setup badge but keep consistent)
        self._update_badges()
        # animated recalc to show changes
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # WPP spinbox changed (animated recalc)
    # ------------------------
    def wpp_value_changed(self, val):
        self.words_per_page = int(val)
        self._update_badges()
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Setup minutes changed (auto recalc, no animation)
    # ------------------------
    def setup_minutes_changed(self, val):
        # update internal variable
        self.setup_minutes = int(val)
        # update badges immediately
        self._update_badges()
        # quick non-animated recalc for responsiveness
        self.recalculate_schedule()

    # ------------------------
    # Toggle default setups lock for all per-row combos (visible but disabled)
    # ------------------------
    def toggle_default_setups_lock(self, state):
        lock_on = bool(state)
        # iterate through rows and set/lock the setups combo if present
        for r in range(self.table.rowCount()):
            widget = self.table.cellWidget(r, 5)  # setups at column 5
            if widget is not None:
                try:
                    if lock_on:
                        item = self.table.item(r, 0)
                        heading_text = item.text() if item else ""
                        if heading_text.upper().startswith("INT"):
                            widget.setCurrentText(str(DEFAULTS["setups_int"]))
                        else:
                            widget.setCurrentText(str(DEFAULTS["setups_ext"]))
                        widget.setEnabled(False)  # visible but locked
                    else:
                        widget.setEnabled(True)   # re-enable for manual edit
                except Exception:
                    # robustly ignore problematic widgets
                    continue
        # recalc animated to show summary change
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Lunch mode changed (Auto <-> Fixed)
    # ------------------------
    def lunch_mode_changed(self, state):
        # update badges and run animated recalc to reflect change
        self._update_badges()
        self.trigger_recalc_with_row_fades()

    # ------------------------
    # Fixed hours changed (only affects if fixed mode is active)
    # ------------------------
    def lunch_fixed_hours_changed(self, val):
        if not self.lunch_auto_toggle.isChecked():
            # Recalculate with animation to show the change
            self.trigger_recalc_with_row_fades()

    # ------------------------
    # Load a Fountain file, parse scenes, and populate table
    # ------------------------
    def load_fountain_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Fountain", "", "Fountain Files (*.fountain)")
        if not file_path:
            return
        # save path for export filenames
        self.current_fountain_path = file_path
        # read content
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        # parse scenes
        self.scenes = self.parse_fountain(content)
        # populate UI table
        self.populate_table()
        # enforce lock if the user had lock set before loading
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)
        # ensure badges reflect current state
        self._update_badges()

    # ------------------------
    # Simple Fountain parser splitting on INT./EXT.
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
    # Calculate page representation and mm:ss for a scene
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
    # Compute shooting time (seconds) for a scene row using self.setup_minutes
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
    # Per-row setups combo changed: update row and recalc (animated)
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
    # Remove summary rows (LUNCH, TOTAL, ESTIMATED WRAP)
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
    # Animated recalc variant (uses per-row fades)
    # ------------------------
    def trigger_recalc_with_row_fades(self):
        # remove previous summary rows
        self.remove_summary_rows()
        # compute schedule values
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        # insert lunch if applicable (animated)
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=True)
        # insert total and wrap rows (animated)
        self.insert_total_row(total, animate=True)
        self.insert_wrap_row(wrap, animate=True)
        # update numbering
        self.update_row_numbers()

    # ------------------------
    # Quick recalculation without animation (used for fast UI changes)
    # ------------------------
    def recalculate_schedule(self):
        # remove old summaries
        self.remove_summary_rows()
        # compute schedule
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        # insert without animation for speed
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)
        self.update_row_numbers()

    # ------------------------
    # Scheduling algorithm (fixed-mode bug fix included)
    # ------------------------
    def calculate_schedule(self):
        # compute per-scene durations (they already include setups via compute_scene_time)
        total_scene_seconds = 0
        durations = []
        for i in range(len(self.scenes)):
            s = self.compute_scene_time(i)
            durations.append(s)
            total_scene_seconds += s

        # extras and GUI inputs
        lunch_min = int(self.lunch_duration_input.currentText())
        lunch_dur = lunch_min * 60
        move_min = int(self.move_duration_input.currentText()) * 60
        move_count = int(self.company_moves_input.currentText())
        include = self.include_moves_lunch_toggle.isChecked()

        lunch_start = None
        insert_index = None

        # start time for clock math
        start_dt = datetime.strptime(self.start_time_input.currentText(), "%H:%M")

        if include:
            if self.lunch_auto_toggle.isChecked():
                # Auto midpoint logic
                midpoint = total_scene_seconds // 2
                running = 0
                for i, secs in enumerate(durations):
                    running += secs
                    if running >= midpoint:
                        insert_index = i + 1
                        lunch_start = start_dt + timedelta(seconds=running)
                        break
                # If nothing matched (empty durations), set lunch after start
                if insert_index is None:
                    insert_index = len(durations)
                    lunch_start = start_dt
            else:
                # Fixed-after-X-hours logic (bug fixed)
                fixed_hours = int(self.lunch_fixed_spin.value())
                fixed_seconds = fixed_hours * 3600
                running = 0
                for i, secs in enumerate(durations):
                    running += secs
                    if running >= fixed_seconds:
                        insert_index = i + 1
                        lunch_start = start_dt + timedelta(seconds=running)
                        break
                # If fixed_seconds is beyond the total_scene_seconds, place lunch after last scene
                if insert_index is None:
                    insert_index = len(durations)  # after last scene
                    # Calculate lunch_start as start + fixed_seconds (reflects user's requested time)
                    lunch_start = start_dt + timedelta(seconds=fixed_seconds)

        # compute total_seconds including extras if included
        total_seconds = total_scene_seconds
        if include:
            total_seconds += lunch_dur + (move_min * move_count)

        # compute wrap clock time
        wrap_dt = start_dt + timedelta(seconds=total_seconds)
        return total_scene_seconds, wrap_dt.strftime("%H:%M"), lunch_start, insert_index

    # ------------------------
    # Populate table with scene rows (initial load)
    # ------------------------
    def populate_table(self):
        # clear spans & items
        self.table.clearSpans()
        self.table.clear()
        # remove any summary rows
        self.remove_summary_rows()
        # headers (Camera Setups header preserved)
        headers = [
            "Scene Heading", "Actions", "Dialogue",
            "Length (pages+1/8s)", "Length (MM:SS)",
            "Camera Setups (Count)", "Shooting Time (HH:MM:SS)"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        # set rows to number of scenes
        self.table.setRowCount(len(self.scenes))
        # populate rows
        for i, sc in enumerate(self.scenes):
            heading = sc["heading"]
            page_len, mmss = self.calculate_scene_length(sc["content"])
            setups_box = QComboBox()
            setups_box.addItems([str(n) for n in range(1, 21)])
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

        # compute and insert summaries (non-animated for initial load)
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)

        # enforce lock if needed
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

        # update badges and numbering
        self._update_badges()
        self.update_row_numbers()

    # ------------------------
    # Create a centered bold 12pt table item with background color
    # ------------------------
    def make_centered_item(self, text, color):
        item = QTableWidgetItem(text)
        item.setBackground(QBrush(QColor(color)))
        item.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    # ------------------------
    # Animate overlay for a given row (per-row fade)
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
    # Insert lunch row (optionally animate)
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
    # Insert total shoot length row
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
    # Insert estimated wrap row
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
    # Update vertical header numbering: number only scene rows
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
    # Gather table data for exports
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
    # Export dispatcher
    # ------------------------
    def export_file(self):
        if not self.current_fountain_path:
            QMessageBox.warning(self, "No File", "Load a Fountain file first.")
            return
        choice = self.export_dropdown.currentText()
        if choice == "Export CSV":
            self.export_csv()
        elif choice == "Export PDF":
            self.export_pdf()
        else:
            self.export_csv()
            self.export_pdf()

    # ------------------------
    # CSV export
    # ------------------------
    def export_csv(self):
        base = os.path.dirname(self.current_fountain_path)
        name = os.path.splitext(os.path.basename(self.current_fountain_path))[0]
        path = os.path.join(base, f"breakdown_{name}.csv")
        data = self.get_table_data()
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(data)

    # ------------------------
    # PDF export (preserve spans/colors)
    # ------------------------
    def export_pdf(self):
        base = os.path.dirname(self.current_fountain_path)
        name = os.path.splitext(os.path.basename(self.current_fountain_path))[0]
        path = os.path.join(base, f"breakdown_{name}.pdf")
        data = self.get_table_data()
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
        SimpleDocTemplate(path, pagesize=letter).build([table])

# ------------------------
# Run the application
# ------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProducersToolkit()
    window.show()
    sys.exit(app.exec())
