# ------------------------------------------------------------
# PRODUCER'S TOOLKIT - Version v0.18-pre
# ------------------------------------------------------------
# - PyQt6 single-file application.
# - Adds Lunch Placement Mode (Auto midpoint or Fixed after X hours).
# - Uses per-row fade animations for summary rows (lighter than full-overlay).
# - Adds LX && Camera Setup Time label and Minutes-per-Setup spinbox.
# - Renames "Setups" column to "Camera Setups (Count)".
# - Keeps single-file layout and detailed inline comments.
# ------------------------------------------------------------

# --- standard library imports ---
import sys                                     # system-level functions and exit
import os                                      # file/directory helpers
import re                                      # regular expressions for simple parsing
import csv                                     # CSV writer for export
from datetime import timedelta, datetime      # time arithmetic and formatting

# --- PyQt6 GUI imports ---
from PyQt6.QtWidgets import (                   # main widgets used in the GUI
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox, QLabel,
    QSpinBox, QCheckBox, QMessageBox, QFileDialog, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation  # alignment flags and animations
from PyQt6.QtGui import QBrush, QColor, QFont     # styling helpers for items

# --- ReportLab for PDF export ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ------------------------------------------------------------
# Default constants and configuration
# ------------------------------------------------------------
DEFAULTS = {
    "words_per_page": 150,          # words per script page default
    "setup_minutes": 5,             # default minutes per setup
    "setups_int": 3,                # default setups for INT scenes
    "setups_ext": 5,                # default setups for EXT scenes
    "default_move_duration": 10,    # minutes per company move
    "default_lunch_duration": 60,   # default lunch length (minutes)
    "default_start_time": "08:00"   # default start time (24h)
}

# fade duration in milliseconds for per-row animations
FADE_DURATION_MS = 500

# pale gray color for global controls bar background
GLOBAL_BAR_COLOR = "#f2f2f2"

# ------------------------------------------------------------
# Main application class
# ------------------------------------------------------------
class ProducersToolkit(QMainWindow):
    # -------------------------
    # Initialize the window and UI
    # -------------------------
    def __init__(self):
        super().__init__()                         # initialize base QMainWindow

        # window title
        self.setWindowTitle("Producer's Toolkit  v0.18-pre")

        # window starting size
        self.resize(1400, 880)

        # application state variables
        self.scenes = []                            # parsed scenes will be stored here
        self.current_fountain_path = ""             # path for current fountain file
        self.words_per_page = DEFAULTS["words_per_page"]  # active WPP
        self.setup_minutes = DEFAULTS["setup_minutes"]    # active minutes per setup

        # ---------- central widget and top-level layout ----------
        central = QWidget()                         # create a central container widget
        self.setCentralWidget(central)              # set as central widget of the window
        self.main_layout = QVBoxLayout(central)     # vertical layout stacking UI sections

        # ---------- top row: Load button ----------
        top_row = QHBoxLayout()                     # horizontal layout for top row
        self.main_layout.addLayout(top_row)         # add to main layout

        # Create "Load Fountain File" button and wire to loader
        self.load_btn = QPushButton("Load Fountain File")
        self.load_btn.clicked.connect(self.load_fountain_file)
        top_row.addWidget(self.load_btn)

        # small spacer to balance layout
        top_row.addWidget(QLabel(""))

        # ---------- Global Controls Bar (pale gray) ----------
        # container widget with background color for grouped global controls
        self.global_bar = QWidget()
        self.global_bar.setStyleSheet(f"background-color: {GLOBAL_BAR_COLOR}; padding: 8px;")
        self.main_layout.addWidget(self.global_bar)

        # Vertical layout inside the global bar to host three rows (timing, calc, lunch placement)
        self.global_bar_layout = QVBoxLayout(self.global_bar)

        # ---------- Global Bar Row A: Timing inputs (company moves, durations, start time) ----------
        self.timing_row = QHBoxLayout()
        self.global_bar_layout.addLayout(self.timing_row)

        # Company moves combo (0..20)
        self.company_moves_input = QComboBox()
        self.company_moves_input.addItems([str(i) for i in range(0, 21)])
        self.timing_row.addWidget(QLabel("Company moves:"))
        self.timing_row.addWidget(self.company_moves_input)

        # Move duration combo (0..120)
        self.move_duration_input = QComboBox()
        self.move_duration_input.addItems([str(i) for i in range(0, 121)])
        self.move_duration_input.setCurrentText(str(DEFAULTS["default_move_duration"]))
        self.timing_row.addWidget(QLabel("Move duration (min):"))
        self.timing_row.addWidget(self.move_duration_input)

        # Lunch duration combo (0..180)
        self.lunch_duration_input = QComboBox()
        self.lunch_duration_input.addItems([str(i) for i in range(0, 181)])
        self.lunch_duration_input.setCurrentText(str(DEFAULTS["default_lunch_duration"]))
        self.timing_row.addWidget(QLabel("Lunch duration (min):"))
        self.timing_row.addWidget(self.lunch_duration_input)

        # Start time (24-hr in 15-min increments)
        self.start_time_input = QComboBox()
        times = [f"{h:02}:{m:02}" for h in range(24) for m in (0, 15, 30, 45)]
        self.start_time_input.addItems(times)
        self.start_time_input.setCurrentText(DEFAULTS["default_start_time"])
        self.timing_row.addWidget(QLabel("Start time:"))
        self.timing_row.addWidget(self.start_time_input)

        # Include moves & lunch toggle
        self.include_moves_lunch_toggle = QCheckBox("Include moves && lunch in totals?")
        self.include_moves_lunch_toggle.setChecked(True)
        self.timing_row.addWidget(self.include_moves_lunch_toggle)

        # Push remaining items to the left
        self.timing_row.addStretch()

        # ---------- Global Bar Row B: Calculation controls (WPP, setup minutes, lock setups, recalc) ----------
        self.calc_row = QHBoxLayout()
        self.global_bar_layout.addLayout(self.calc_row)

        # Custom WPP toggle
        self.custom_wpp_toggle = QCheckBox("Use Custom Words Per Page")
        self.custom_wpp_toggle.setChecked(False)
        self.custom_wpp_toggle.stateChanged.connect(self.toggle_custom_wpp_changed)
        self.calc_row.addWidget(self.custom_wpp_toggle)

        # WPP spinbox (100..250)
        self.wpp_spin = QSpinBox()
        self.wpp_spin.setRange(100, 250)
        self.wpp_spin.setValue(DEFAULTS["words_per_page"])
        self.wpp_spin.setEnabled(False)
        self.wpp_spin.valueChanged.connect(self.wpp_value_changed)
        self.calc_row.addWidget(QLabel("Words Per Page:"))
        self.calc_row.addWidget(self.wpp_spin)

        # LX & Camera Setup Time label (new small label) — shows text with ampersand escaped
        self.setup_label = QLabel("LX && Camera Setup Time (min):")
        self.calc_row.addWidget(self.setup_label)

        # Minutes-per-Setup spinbox (1..30), default set from self.setup_minutes
        self.setup_minutes_spin = QSpinBox()
        self.setup_minutes_spin.setRange(1, 30)
        self.setup_minutes_spin.setValue(self.setup_minutes)
        # Changing minutes per setup should auto-recalc WITHOUT animation
        self.setup_minutes_spin.valueChanged.connect(self.setup_minutes_changed)
        self.calc_row.addWidget(self.setup_minutes_spin)

        # Lock default number of setups (visible but disables per-row combos when ON)
        self.lock_setups_toggle = QCheckBox("Use and Lock Default Number of Setups (INT=3, EXT=5)")
        self.lock_setups_toggle.setChecked(False)
        self.lock_setups_toggle.stateChanged.connect(self.toggle_default_setups_lock)
        self.calc_row.addWidget(self.lock_setups_toggle)

        # Push recalc button to right side
        self.calc_row.addStretch()

        # Recalculate button - this uses per-row fades to animate the summary rows
        self.recalc_button = QPushButton("Recalculate Schedule")
        self.recalc_button.clicked.connect(self.trigger_recalc_with_row_fades)
        self.calc_row.addWidget(self.recalc_button)

        # ---------- Global Bar Row C: Lunch placement controls (separate row for clarity) ----------
        self.lunch_row = QHBoxLayout()
        self.global_bar_layout.addLayout(self.lunch_row)

        # Lunch placement mode toggle: Auto (midpoint) when checked, Fixed when unchecked
        self.lunch_auto_toggle = QCheckBox("Lunch Placement Mode: Auto (midpoint when checked)")
        self.lunch_auto_toggle.setChecked(True)      # default is Auto midpoint
        # When toggled, recalc with animation to show change
        self.lunch_auto_toggle.stateChanged.connect(self.lunch_mode_changed)
        self.lunch_row.addWidget(self.lunch_auto_toggle)

        # Fixed hours spinbox (1..12) for "Fixed after X hours" mode
        self.lunch_fixed_spin = QSpinBox()
        self.lunch_fixed_spin.setRange(1, 12)       # reasonable daily hours (1..12)
        self.lunch_fixed_spin.setValue(6)           # default 6 hours after start
        # Only relevant when Auto is unchecked; changing it triggers a recalc (animated)
        self.lunch_fixed_spin.valueChanged.connect(self.lunch_fixed_hours_changed)
        # add label and spin to lunch row
        self.lunch_row.addWidget(QLabel("Fixed after (hours):"))
        self.lunch_row.addWidget(self.lunch_fixed_spin)

        # Spacer to keep layout tidy
        self.lunch_row.addStretch()

        # ---------- Main Table widget ----------
        self.table = QTableWidget()
        self.main_layout.addWidget(self.table)

        # ---------- Export row (CSV / PDF) ----------
        export_row = QHBoxLayout()
        self.export_dropdown = QComboBox()
        self.export_dropdown.addItems(["Export CSV", "Export PDF", "Export Both"])
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export_file)
        export_row.addWidget(self.export_dropdown)
        export_row.addWidget(self.export_button)
        export_row.addStretch()
        self.main_layout.addLayout(export_row)

    # -------------------------
    # Helper: get the active Words Per Page value
    # -------------------------
    def get_current_wpp(self):
        # If custom WPP toggle is on, use the spinbox value; otherwise use default
        if self.custom_wpp_toggle.isChecked():
            return int(self.wpp_spin.value())
        return int(DEFAULTS["words_per_page"])

    # -------------------------
    # Event handler: custom WPP toggle changed
    # -------------------------
    def toggle_custom_wpp_changed(self, state):
        # If toggle is ON, enable the spinbox and set words_per_page to its value
        if state:
            self.wpp_spin.setEnabled(True)
            self.words_per_page = int(self.wpp_spin.value())
        else:
            # If OFF, disable the spinbox and revert to default WPP
            self.wpp_spin.setEnabled(False)
            self.words_per_page = DEFAULTS["words_per_page"]

        # Animated recalc to visually reflect new WPP
        self.trigger_recalc_with_row_fades()

    # -------------------------
    # Event handler: WPP spin value changed
    # -------------------------
    def wpp_value_changed(self, val):
        # Update active words_per_page
        self.words_per_page = int(val)
        # Animated recalc for visual confirmation
        self.trigger_recalc_with_row_fades()

    # -------------------------
    # Event handler: minutes-per-setup changed (auto recalc, no animation)
    # -------------------------
    def setup_minutes_changed(self, val):
        # Update internal setup_minutes
        self.setup_minutes = int(val)
        # Immediately recalc WITHOUT animations for quick responsiveness
        self.recalculate_schedule()

    # -------------------------
    # Handler: lock default setups toggle
    # -------------------------
    def toggle_default_setups_lock(self, state):
        # Convert to boolean
        lock_on = bool(state)

        # Iterate each row and apply defaults / enable/disable combos
        for r in range(self.table.rowCount()):
            widget = self.table.cellWidget(r, 5)  # combos expected in column 5
            if widget is not None:
                try:
                    if lock_on:
                        # read heading to decide INT vs EXT
                        item = self.table.item(r, 0)
                        heading_text = item.text() if item else ""
                        # set defaults based on heading
                        if heading_text.upper().startswith("INT"):
                            widget.setCurrentText(str(DEFAULTS["setups_int"]))
                        else:
                            widget.setCurrentText(str(DEFAULTS["setups_ext"]))
                        # disable widget but keep visible
                        widget.setEnabled(False)
                    else:
                        # unlock: re-enable widget for manual editing
                        widget.setEnabled(True)
                except Exception:
                    # swallow exceptions for robustness
                    continue

        # Animated recalc after applying locks so summary rows update visually
        self.trigger_recalc_with_row_fades()

    # -------------------------
    # Lunch mode changed (Auto vs Fixed)
    # -------------------------
    def lunch_mode_changed(self, state):
        # If Auto is ON (state truthy) then we use midpoint logic
        # If unchecked (state false), we use fixed hours spinbox
        # Regardless, run an animated recalc to show change
        self.trigger_recalc_with_row_fades()

    # -------------------------
    # Lunch fixed hours changed (only relevant if Auto is OFF)
    # -------------------------
    def lunch_fixed_hours_changed(self, val):
        # If the mode is fixed (Auto unchecked), changing the value should re-run animated recalc
        if not self.lunch_auto_toggle.isChecked():
            # Animated recalc to reflect the new fixed hour placement
            self.trigger_recalc_with_row_fades()

    # -------------------------
    # Load fountain file from disk, parse, and populate table
    # -------------------------
    def load_fountain_file(self):
        # Open file dialog filtered to .fountain files
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Fountain", "", "Fountain Files (*.fountain)")
        if not file_path:
            # User cancelled; nothing to do
            return

        # Save path for exports
        self.current_fountain_path = file_path

        # Read file content as UTF-8
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Parse content into scenes
        self.scenes = self.parse_fountain(content)

        # Populate table
        self.populate_table()

        # If lock setups toggle active, enforce defaults and lock on newly created rows
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

    # -------------------------
    # Simple Fountain parser: split on INT./EXT.
    # -------------------------
    def parse_fountain(self, content):
        scenes = []                        # list to hold scene dicts
        current = None                     # temporary scene container
        for line in content.splitlines():
            stripped = line.strip()        # remove surrounding whitespace
            if re.match(r"^(INT\.|EXT\.)", stripped, re.I):
                # New scene heading encountered
                if current:
                    scenes.append(current) # save previous scene
                current = {"heading": stripped, "content": []}
            elif current is not None:
                # Add content line to current scene
                current["content"].append(stripped)
        if current:
            scenes.append(current)          # append last scene
        return scenes

    # -------------------------
    # Calculate scene length string and mm:ss using current WPP
    # -------------------------
    def calculate_scene_length(self, scene_text):
        # Count words with regex tokenization
        words = len(re.findall(r"\w+", " ".join(scene_text)))
        # Determine WPP (respecting toggle)
        wpp = self.get_current_wpp()
        # Avoid division by zero; compute pages
        pages = (words / wpp) if wpp > 0 else 0.0
        # Full pages and fractional eighths
        full = int(pages)
        eighths = int(round((pages - full) * 8))
        if eighths == 8:
            full += 1
            eighths = 0
        # Format page display
        if full == 0 and eighths > 0:
            page_str = f"{eighths}/8"
        elif eighths > 0:
            page_str = f"{full} {eighths}/8"
        else:
            page_str = f"{full}"
        # Convert pages to seconds (approx 1 page = 60 sec)
        seconds = int(round(pages * 60))
        mm, ss = divmod(seconds, 60)
        mmss = f"{mm:02}:{ss:02}"
        return page_str, mmss

    # -------------------------
    # Compute shooting time for row using self.setup_minutes dynamically
    # -------------------------
    def compute_scene_time(self, row):
        # Find setups combo widget in column 5 (may be disabled but present)
        setups_widget = self.table.cellWidget(row, 5)
        # Find length item (MM:SS) in column 4
        length_item = self.table.item(row, 4)
        # If missing, return zero seconds
        if setups_widget is None or length_item is None:
            return 0
        # Parse setups count safely
        try:
            setups_val = int(setups_widget.currentText())
        except Exception:
            setups_val = 0
        # Parse mm:ss safely
        try:
            mm, ss = map(int, length_item.text().split(":"))
        except Exception:
            mm, ss = 0, 0
        # Base minutes from mm:ss
        base_minutes = mm + ss / 60.0
        # Add setups penalty using dynamic setup_minutes value
        total_minutes = base_minutes + setups_val * self.setup_minutes
        # Return seconds rounded to int
        return int(round(total_minutes * 60))

    # -------------------------
    # When a per-row setups combo changes, update that row and recalc (animated)
    # -------------------------
    def update_scene_row_for_box(self, box):
        # Find the current row by position
        idx = self.table.indexAt(box.pos())
        row = idx.row()
        # Fallback: scan rows for widget reference
        if row == -1:
            for r in range(self.table.rowCount()):
                if self.table.cellWidget(r, 5) is box:
                    row = r
                    break
        # If not found, exit
        if row == -1:
            return
        # Compute seconds for this row and update column 6
        secs = self.compute_scene_time(row)
        self.table.setItem(row, 6, QTableWidgetItem(str(timedelta(seconds=secs))))
        # Animated recalc for summary rows
        self.trigger_recalc_with_row_fades()

    # -------------------------
    # Remove summary rows to avoid duplicates
    # -------------------------
    def remove_summary_rows(self):
        # Iterate backwards and remove rows whose first column starts with summary prefixes
        for r in reversed(range(self.table.rowCount())):
            item = self.table.item(r, 0)
            if item is None:
                continue
            text = item.text()
            if any(text.startswith(prefix) for prefix in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                self.table.removeRow(r)

    # -------------------------
    # Animated per-row recalc: remove old summaries, compute, insert summary rows and animate them individually
    # -------------------------
    def trigger_recalc_with_row_fades(self):
        # Remove previous summary rows first
        self.remove_summary_rows()
        # Compute schedule values (this only computes; no UI changes yet)
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        # Insert lunch row if needed; animate=True to use per-row fade
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=True)
        # Append total and wrap rows with animation
        self.insert_total_row(total, animate=True)
        self.insert_wrap_row(wrap, animate=True)
        # Update numbering (summary rows unnumbered)
        self.update_row_numbers()

    # -------------------------
    # Recalculate schedule without animation (used for quick changes like setup_minutes)
    # -------------------------
    def recalculate_schedule(self):
        # Remove old summaries
        self.remove_summary_rows()
        # Compute schedule data
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        # Insert lunch without animation
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        # Insert total and wrap without animation
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)
        # Update numbering
        self.update_row_numbers()

    # -------------------------
    # Calculate schedule: returns (total_scene_seconds, wrap_str, lunch_start_dt_or_None, insert_index_or_None)
    # -------------------------
    def calculate_schedule(self):
        # Total seconds for scene shooting only
        total_scene_seconds = 0
        # Read GUI inputs for extras
        lunch_min = int(self.lunch_duration_input.currentText())
        lunch_dur = lunch_min * 60
        move_min = int(self.move_duration_input.currentText()) * 60
        move_count = int(self.company_moves_input.currentText())
        include = self.include_moves_lunch_toggle.isChecked()
        # Build durations list for each scene using compute_scene_time which uses self.setup_minutes
        durations = []
        for i in range(len(self.scenes)):
            s = self.compute_scene_time(i)
            durations.append(s)
            total_scene_seconds += s
        # Determine lunch insertion based on mode (auto midpoint or fixed after N hours)
        lunch_start = None
        insert_index = None
        # Convert start time string to datetime for clock math
        start_dt = datetime.strptime(self.start_time_input.currentText(), "%H:%M")
        if self.lunch_auto_toggle.isChecked():
            # Auto midpoint: find first scene where running >= midpoint
            midpoint = total_scene_seconds // 2
            running = 0
            for i, secs in enumerate(durations):
                running += secs
                if running >= midpoint and include and lunch_start is None:
                    insert_index = i + 1
                    lunch_start = start_dt + timedelta(seconds=running)
                    break
        else:
            # Fixed-after-X-hours mode: find the scene where running >= fixed_seconds
            fixed_hours = int(self.lunch_fixed_spin.value())   # integer hours to wait after start
            fixed_seconds = fixed_hours * 3600                 # convert hours to seconds
            running = 0
            for i, secs in enumerate(durations):
                running += secs
                # when running >= fixed_seconds, insert after this scene
                if running >= fixed_seconds and include and lunch_start is None:
                    insert_index = i + 1
                    lunch_start = start_dt + timedelta(seconds=running)
                    break
        # Compute total seconds for the day optionally including lunch & moves
        total_seconds = total_scene_seconds
        if include:
            total_seconds += lunch_dur + (move_min * move_count)
        # Compute wrap time (clock) by adding total_seconds to start_dt
        wrap_dt = start_dt + timedelta(seconds=total_seconds)
        # Return all computed values
        return total_scene_seconds, wrap_dt.strftime("%H:%M"), lunch_start, insert_index

    # -------------------------
    # Populate the table with scene rows (and append summary rows)
    # -------------------------
    def populate_table(self):
        # Clear any existing merged spans and contents
        self.table.clearSpans()
        self.table.clear()
        # Remove any leftover summary rows as a safeguard
        self.remove_summary_rows()
        # Define column headers (changed "Setups" header to "Camera Setups (Count)")
        headers = [
            "Scene Heading", "Actions", "Dialogue",
            "Length (pages+1/8s)", "Length (MM:SS)",
            "Camera Setups (Count)", "Shooting Time (HH:MM:SS)"
        ]
        # Apply headers to table
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        # Set the number of rows equal to number of scenes
        self.table.setRowCount(len(self.scenes))
        # Populate each scene row
        for i, sc in enumerate(self.scenes):
            heading = sc["heading"]   # e.g., "EXT. PARK - DAY"
            # Calculate page string and mm:ss representation
            page_len, mmss = self.calculate_scene_length(sc["content"])
            # Create setups combo (options 1..20)
            setups_box = QComboBox()
            setups_box.addItems([str(n) for n in range(1, 21)])
            # Apply defaults (INT or EXT)
            if heading.upper().startswith("INT"):
                setups_box.setCurrentText(str(DEFAULTS["setups_int"]))
            else:
                setups_box.setCurrentText(str(DEFAULTS["setups_ext"]))
            # Connect combo changes to robust handler referencing the widget
            setups_box.currentTextChanged.connect(lambda t, box=setups_box: self.update_scene_row_for_box(box))
            # Place items/widgets into table cells
            self.table.setItem(i, 0, QTableWidgetItem(heading))    # heading
            self.table.setItem(i, 3, QTableWidgetItem(page_len))   # pages string
            self.table.setItem(i, 4, QTableWidgetItem(mmss))       # mm:ss string
            self.table.setCellWidget(i, 5, setups_box)             # setups widget
            # Compute initial shooting time for this row and set it in column 6
            self.table.setItem(i, 6, QTableWidgetItem(str(timedelta(seconds=self.compute_scene_time(i)))))
        # After scene rows are populated, compute summary data
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        # Insert lunch row if applicable (no animation here; we'll animate explicitly if needed)
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        # Append total & wrap rows without animation
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)
        # If lock-setups toggle is ON, enforce defaults and disable widgets
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)
        # Update vertical row numbers to show only scene rows numbered
        self.update_row_numbers()

    # -------------------------
    # Create a centered, bold 12pt table item with background color
    # -------------------------
    def make_centered_item(self, text, color):
        item = QTableWidgetItem(text)                    # create the item with text
        item.setBackground(QBrush(QColor(color)))        # set background color
        item.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))  # set font bold 12pt
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)     # center alignment
        return item

    # -------------------------
    # Per-row fade animation helper: overlays and animates the row area only
    # -------------------------
    def animate_row(self, row):
        # create a temporary overlay widget rooted in the table viewport
        overlay = QWidget(self.table.viewport())
        # compute visual rectangle for the given row/first column to find y and height
        rect = self.table.visualRect(self.table.model().index(row, 0))
        # set overlay geometry to full table width and row height at that y
        overlay.setGeometry(0, rect.y(), self.table.viewport().width(), rect.height())
        # create opacity effect and attach to overlay
        eff = QGraphicsOpacityEffect()
        overlay.setGraphicsEffect(eff)
        # animate opacity from 0 -> 1 (fade-in)
        anim = QPropertyAnimation(eff, b"opacity", overlay)
        anim.setDuration(FADE_DURATION_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        # delete overlay when animation completes to avoid blocking input
        anim.finished.connect(overlay.deleteLater)
        overlay.show()
        anim.start()

    # -------------------------
    # Insert lunch summary row (optionally animate)
    # -------------------------
    def insert_lunch_row(self, row_index, lunch_start_dt, lunch_minutes, animate=True):
        self.table.insertRow(row_index)                    # insert empty row at index
        text = f"LUNCH — Starts at {lunch_start_dt.strftime('%H:%M')} ({str(timedelta(minutes=lunch_minutes))})"
        item = self.make_centered_item(text, "orange")    # styled item
        self.table.setItem(row_index, 0, item)            # set into column 0
        # merge across all columns to create full-width summary row
        self.table.setSpan(row_index, 0, 1, self.table.columnCount())
        # animate only if requested
        if animate:
            self.animate_row(row_index)

    # -------------------------
    # Insert total shoot length summary row (optionally animate)
    # -------------------------
    def insert_total_row(self, total_seconds, animate=True):
        row = self.table.rowCount()
        self.table.insertRow(row)
        text = f"TOTAL SHOOT LENGTH — {str(timedelta(seconds=total_seconds))}"
        item = self.make_centered_item(text, "lightgreen")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row)

    # -------------------------
    # Insert estimated wrap summary row (optionally animate)
    # -------------------------
    def insert_wrap_row(self, wrap_str, animate=True):
        row = self.table.rowCount()
        self.table.insertRow(row)
        text = f"ESTIMATED WRAP — {wrap_str}"
        item = self.make_centered_item(text, "lightblue")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row)

    # -------------------------
    # Update vertical header numbers so only scene rows are numbered
    # -------------------------
    def update_row_numbers(self):
        # iterate all rows in the table
        for r in range(self.table.rowCount()):
            # ensure a vertical header item exists for this row
            if not self.table.verticalHeaderItem(r):
                self.table.setVerticalHeaderItem(r, QTableWidgetItem())
            header_item = self.table.verticalHeaderItem(r)
            first_item = self.table.item(r, 0)
            # summary rows are not numbered
            if first_item and any(first_item.text().startswith(p) for p in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                header_item.setText("")    # clear numbering
            else:
                header_item.setText(str(r + 1))  # number scene rows starting at 1

    # -------------------------
    # Gather table content as list-of-lists for export
    # -------------------------
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

    # -------------------------
    # Export dispatcher (CSV / PDF)
    # -------------------------
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

    # -------------------------
    # Export CSV
    # -------------------------
    def export_csv(self):
        base = os.path.dirname(self.current_fountain_path)
        name = os.path.splitext(os.path.basename(self.current_fountain_path))[0]
        path = os.path.join(base, f"breakdown_{name}.csv")
        data = self.get_table_data()
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(data)

    # -------------------------
    # Export PDF with ReportLab, preserving SPANs and colors for summary rows
    # -------------------------
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

# ------------------------------------------------------------
# Launch the application when executed directly
# ------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)         # create Qt application
    window = ProducersToolkit()          # instantiate the main window class
    window.show()                        # display the window
    sys.exit(app.exec())                 # enter Qt event loop and exit on close
