# ------------------------------------------------------------
# PRODUCER'S TOOLKIT - Version v0.18.2-pre
# ------------------------------------------------------------
# Single-file PyQt6 application (one module).
#
# Visual:
# - "Card-like" Global Control area: three cards (Timing, Calculation, Lunch Placement)
# - Cards use a drop-shadow effect (shadow-only, no borders)
# - All control labels and UI text use 12pt Helvetica Bold for clarity
#
# Behavior:
# - Preserves all logic from v0.18-pre (WPP toggle, setup minutes, lock setups, lunch placement modes)
# - Uses per-row fade animations for summary rows (lightweight)
# - Changing Minutes-per-Setup auto-recalculates without animation
# - Recalculate button triggers animated insertion of summary rows (per-row fades)
#
# Extensive inline comments added to explain structure and each important step.
# ------------------------------------------------------------

# --- standard library imports ---
import sys                                       # for argv and exit
import os                                        # for file path operations (exports)
import re                                        # for parsing fountain headings
import csv                                       # for CSV export
from datetime import timedelta, datetime        # for time math and formatting

# --- PyQt6 imports ---
from PyQt6.QtWidgets import (                     # many widgets imported for UI
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox, QLabel,
    QSpinBox, QCheckBox, QMessageBox, QFileDialog,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QFrame
)
from PyQt6.QtCore import Qt, QPropertyAnimation   # alignment flags and animation class
from PyQt6.QtGui import QBrush, QColor, QFont     # styling helpers

# --- ReportLab for PDF export ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ------------------------------------------------------------
# Default constants and UI constants
# ------------------------------------------------------------
DEFAULTS = {
    "words_per_page": 150,            # default words-per-page (WPP) if not custom
    "setup_minutes": 5,               # default minutes per setup
    "setups_int": 3,                  # default number of setups for INT scenes
    "setups_ext": 5,                  # default number of setups for EXT scenes
    "default_move_duration": 10,      # default mins per company move
    "default_lunch_duration": 60,     # default lunch length minutes
    "default_start_time": "08:00"     # default start time string (24h)
}

FADE_DURATION_MS = 500                # animation duration for row fades (ms)
GLOBAL_CARD_BG = "#f8f9fb"            # slightly deeper pale background for cards
GLOBAL_BAR_PADDING = 10               # padding inside cards (px)

# ------------------------------------------------------------
# Main application class
# ------------------------------------------------------------
class ProducersToolkit(QMainWindow):
    # --------------------------------------------------------
    # Initialize the main window and all widgets/layouts
    # --------------------------------------------------------
    def __init__(self):
        # call the parent constructor to initialize QMainWindow internals
        super().__init__()

        # set window title and starting size
        self.setWindowTitle("Producer's Toolkit  v0.18.2-pre")
        self.resize(1400, 900)

        # ------------------------
        # Internal state variables
        # ------------------------
        self.scenes = []                             # stores parsed scenes as list of dicts
        self.current_fountain_path = ""              # last loaded fountain file path
        self.words_per_page = DEFAULTS["words_per_page"]  # active words-per-page (WPP)
        self.setup_minutes = DEFAULTS["setup_minutes"]    # active minutes per setup

        # ------------------------
        # Central widget and main vertical layout
        # ------------------------
        central = QWidget()                          # central container widget
        self.setCentralWidget(central)               # make it the central widget
        self.main_layout = QVBoxLayout(central)      # top-level vertical layout to stack UI sections

        # ------------------------
        # TOP ROW: Load Fountain button (simple)
        # ------------------------
        top_row = QHBoxLayout()                      # horizontal layout for top row
        self.main_layout.addLayout(top_row)          # add to main layout

        # Load button: opens file dialog to choose .fountain file
        self.load_btn = QPushButton("Load Fountain File")
        self.load_btn.clicked.connect(self.load_fountain_file)  # connect click signal
        top_row.addWidget(self.load_btn)             # add button to top row layout

        # stretch to push load button to left (keeps layout neat)
        top_row.addStretch()

        # ------------------------
        # GLOBAL CONTROLS AREA (Card-like)
        # We'll create three QFrame "cards" stacked vertically to achieve a card-like layout.
        # Each card will have a drop-shadow effect (no border), padding, and a background color.
        # ------------------------

        # --- CARD A: Timing Inputs (company moves, durations, start time)
        self.card_timing = QFrame()                  # use QFrame as card container
        self.card_timing.setStyleSheet(
            f"background-color: {GLOBAL_CARD_BG}; border-radius: 8px; padding: {GLOBAL_BAR_PADDING}px;"
        )
        # add shadow effect to the card (shadow-only look)
        shadow = QGraphicsDropShadowEffect(self.card_timing)
        shadow.setBlurRadius(18)                     # blur radius for soft shadow
        shadow.setOffset(0, 4)                       # slight downward offset
        shadow.setColor(QColor(0, 0, 0, 80))         # semi-transparent black shadow
        self.card_timing.setGraphicsEffect(shadow)   # attach the shadow to the card

        # add card to main layout as a widget
        self.main_layout.addWidget(self.card_timing)

        # inner layout for the timing card
        timing_layout = QHBoxLayout(self.card_timing)

        # font for bold 12pt labels in cards
        label_font = QFont("Helvetica", 12, QFont.Weight.Bold)  # 12pt bold as requested

        # "Company moves" label and combo
        lbl = QLabel("Company moves:")
        lbl.setFont(label_font)
        timing_layout.addWidget(lbl)
        self.company_moves_input = QComboBox()
        self.company_moves_input.addItems([str(i) for i in range(0, 21)])  # 0..20
        self.company_moves_input.setFont(QFont("Helvetica", 12))            # inherit 12pt for controls
        timing_layout.addWidget(self.company_moves_input)

        # "Move duration (min)" label and combo
        lbl = QLabel("Move duration (min):")
        lbl.setFont(label_font)
        timing_layout.addWidget(lbl)
        self.move_duration_input = QComboBox()
        self.move_duration_input.addItems([str(i) for i in range(0, 121)])  # 0..120
        self.move_duration_input.setCurrentText(str(DEFAULTS["default_move_duration"]))
        self.move_duration_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.move_duration_input)

        # "Lunch duration (min)" label and combo
        lbl = QLabel("Lunch duration (min):")
        lbl.setFont(label_font)
        timing_layout.addWidget(lbl)
        self.lunch_duration_input = QComboBox()
        self.lunch_duration_input.addItems([str(i) for i in range(0, 181)])  # 0..180
        self.lunch_duration_input.setCurrentText(str(DEFAULTS["default_lunch_duration"]))
        self.lunch_duration_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.lunch_duration_input)

        # "Start time" label and combo (24hr, 15-min increments)
        lbl = QLabel("Start time:")
        lbl.setFont(label_font)
        timing_layout.addWidget(lbl)
        self.start_time_input = QComboBox()
        times = [f"{h:02}:{m:02}" for h in range(24) for m in (0, 15, 30, 45)]
        self.start_time_input.addItems(times)
        self.start_time_input.setCurrentText(DEFAULTS["default_start_time"])
        self.start_time_input.setFont(QFont("Helvetica", 12))
        timing_layout.addWidget(self.start_time_input)

        # "Include moves & lunch in totals?" checkbox (same row)
        self.include_moves_lunch_toggle = QCheckBox("Include moves & lunch in totals?")
        self.include_moves_lunch_toggle.setFont(label_font)
        self.include_moves_lunch_toggle.setChecked(True)
        timing_layout.addWidget(self.include_moves_lunch_toggle)

        # push remaining items to the left to keep controls compact
        timing_layout.addStretch()

        # small spacing after the card (visual separation)
        self.main_layout.addSpacing(8)

        # --- CARD B: Calculation Controls (WPP toggle, WPP spin, LX & Setup time, lock setups, recalc)
        self.card_calc = QFrame()
        self.card_calc.setStyleSheet(
            f"background-color: {GLOBAL_CARD_BG}; border-radius: 8px; padding: {GLOBAL_BAR_PADDING}px;"
        )
        shadow2 = QGraphicsDropShadowEffect(self.card_calc)
        shadow2.setBlurRadius(18)
        shadow2.setOffset(0, 4)
        shadow2.setColor(QColor(0, 0, 0, 80))
        self.card_calc.setGraphicsEffect(shadow2)
        self.main_layout.addWidget(self.card_calc)

        # inner layout for calculation controls
        calc_layout = QHBoxLayout(self.card_calc)

        # Custom WPP toggle
        self.custom_wpp_toggle = QCheckBox("Use Custom Words Per Page")
        self.custom_wpp_toggle.setFont(label_font)
        self.custom_wpp_toggle.setChecked(False)
        self.custom_wpp_toggle.stateChanged.connect(self.toggle_custom_wpp_changed)
        calc_layout.addWidget(self.custom_wpp_toggle)

        # WPP label and spinbox (100..250)
        lbl = QLabel("Words Per Page:")
        lbl.setFont(label_font)
        calc_layout.addWidget(lbl)
        self.wpp_spin = QSpinBox()
        self.wpp_spin.setRange(100, 250)
        self.wpp_spin.setValue(DEFAULTS["words_per_page"])
        self.wpp_spin.setEnabled(False)               # disabled until toggle ON
        self.wpp_spin.setFont(QFont("Helvetica", 12))
        self.wpp_spin.valueChanged.connect(self.wpp_value_changed)
        calc_layout.addWidget(self.wpp_spin)

        # LX & Camera Setup Time label and spinbox (1..30 minutes)
        lbl = QLabel("LX & Camera Setup Time (min):")
        lbl.setFont(label_font)                       # bold 12pt label as requested
        calc_layout.addWidget(lbl)
        self.setup_minutes_spin = QSpinBox()
        self.setup_minutes_spin.setRange(1, 30)       # allowed minutes per setup
        self.setup_minutes_spin.setValue(self.setup_minutes)
        self.setup_minutes_spin.setFont(QFont("Helvetica", 12))
        # Changing this triggers auto recalculation WITHOUT animation for speed
        self.setup_minutes_spin.valueChanged.connect(self.setup_minutes_changed)
        calc_layout.addWidget(self.setup_minutes_spin)

        # Lock default number of setups toggle (visible but disables per-row combos when ON)
        self.lock_setups_toggle = QCheckBox("Use and Lock Default Number of Setups (INT=3, EXT=5)")
        self.lock_setups_toggle.setFont(label_font)
        self.lock_setups_toggle.setChecked(False)
        self.lock_setups_toggle.stateChanged.connect(self.toggle_default_setups_lock)
        calc_layout.addWidget(self.lock_setups_toggle)

        # push recalc button to the right side
        calc_layout.addStretch()

        # Recalculate schedule button (animated per-row insertion)
        self.recalc_button = QPushButton("Recalculate Schedule")
        self.recalc_button.setFont(QFont("Helvetica", 12))
        self.recalc_button.clicked.connect(self.trigger_recalc_with_row_fades)
        calc_layout.addWidget(self.recalc_button)

        # spacing after card B
        self.main_layout.addSpacing(8)

        # --- CARD C: Lunch Placement Controls (self-contained card)
        self.card_lunch = QFrame()
        self.card_lunch.setStyleSheet(
            f"background-color: {GLOBAL_CARD_BG}; border-radius: 8px; padding: {GLOBAL_BAR_PADDING}px;"
        )
        shadow3 = QGraphicsDropShadowEffect(self.card_lunch)
        shadow3.setBlurRadius(18)
        shadow3.setOffset(0, 4)
        shadow3.setColor(QColor(0, 0, 0, 80))
        self.card_lunch.setGraphicsEffect(shadow3)
        self.main_layout.addWidget(self.card_lunch)

        # inner layout for lunch placement
        lunch_layout = QHBoxLayout(self.card_lunch)

        # Lunch placement mode toggle: Auto (midpoint) when checked
        self.lunch_auto_toggle = QCheckBox("Lunch Placement Mode: Auto (midpoint when checked)")
        self.lunch_auto_toggle.setFont(label_font)
        self.lunch_auto_toggle.setChecked(True)
        self.lunch_auto_toggle.stateChanged.connect(self.lunch_mode_changed)
        lunch_layout.addWidget(self.lunch_auto_toggle)

        # Fixed-after-X-hours label + spinbox (1..12 hours)
        lbl = QLabel("Fixed after (hours):")
        lbl.setFont(label_font)
        lunch_layout.addWidget(lbl)
        self.lunch_fixed_spin = QSpinBox()
        self.lunch_fixed_spin.setRange(1, 12)
        self.lunch_fixed_spin.setValue(6)            # default = 6 hours after start
        self.lunch_fixed_spin.setFont(QFont("Helvetica", 12))
        # changes trigger animated recalc only if in Fixed mode
        self.lunch_fixed_spin.valueChanged.connect(self.lunch_fixed_hours_changed)
        lunch_layout.addWidget(self.lunch_fixed_spin)

        # push elements to the left for neatness
        lunch_layout.addStretch()

        # spacing after global controls
        self.main_layout.addSpacing(12)

        # ------------------------
        # Main Table Widget below the cards
        # ------------------------
        self.table = QTableWidget()
        self.main_layout.addWidget(self.table)

        # ------------------------
        # Export row (CSV / PDF) at bottom
        # ------------------------
        export_row = QHBoxLayout()
        self.export_dropdown = QComboBox()
        self.export_dropdown.addItems(["Export CSV", "Export PDF", "Export Both"])
        self.export_dropdown.setFont(QFont("Helvetica", 12))
        self.export_button = QPushButton("Export")
        self.export_button.setFont(QFont("Helvetica", 12))
        self.export_button.clicked.connect(self.export_file)
        export_row.addWidget(self.export_dropdown)
        export_row.addWidget(self.export_button)
        export_row.addStretch()
        self.main_layout.addLayout(export_row)

        # end of __init__: UI built and ready

    # --------------------------------------------------------
    # Helper: Return currently active words-per-page (respects toggle)
    # --------------------------------------------------------
    def get_current_wpp(self):
        # If the custom WPP toggle is on, return spinbox value; otherwise use DEFAULTS.
        if self.custom_wpp_toggle.isChecked():
            return int(self.wpp_spin.value())
        return int(DEFAULTS["words_per_page"])

    # --------------------------------------------------------
    # Toggle handler for custom WPP
    # --------------------------------------------------------
    def toggle_custom_wpp_changed(self, state):
        # If checked (truthy): enable spinbox and set words_per_page
        if state:
            self.wpp_spin.setEnabled(True)
            self.words_per_page = int(self.wpp_spin.value())
        else:
            # If unchecked: disable spinbox and revert to default WPP
            self.wpp_spin.setEnabled(False)
            self.words_per_page = DEFAULTS["words_per_page"]
        # Animated recalc to show changes visually
        self.trigger_recalc_with_row_fades()

    # --------------------------------------------------------
    # Handler for WPP spin changes (animated recalc)
    # --------------------------------------------------------
    def wpp_value_changed(self, val):
        # Update the internal variable then animate recalc so user sees changes
        self.words_per_page = int(val)
        self.trigger_recalc_with_row_fades()

    # --------------------------------------------------------
    # Handler: minutes-per-setup changed (auto recalc WITHOUT animation)
    # --------------------------------------------------------
    def setup_minutes_changed(self, val):
        # Update internal minutes-per-setup
        self.setup_minutes = int(val)
        # Recalculate immediately without animation for responsiveness
        self.recalculate_schedule()

    # --------------------------------------------------------
    # Handler: lock default setups toggle
    # When ON: set per-row combos to defaults (INT/EXT) and disable them (visible but disabled).
    # When OFF: re-enable per-row combos for manual editing.
    # --------------------------------------------------------
    def toggle_default_setups_lock(self, state):
        # convert to boolean
        lock_on = bool(state)
        # iterate rows and adjust each row's setups combo if present
        for r in range(self.table.rowCount()):
            widget = self.table.cellWidget(r, 5)   # column 5 expected to hold combos
            if widget is not None:
                try:
                    if lock_on:
                        # read heading to decide INT vs EXT
                        item = self.table.item(r, 0)
                        heading_text = item.text() if item else ""
                        # set default count based on heading
                        if heading_text.upper().startswith("INT"):
                            widget.setCurrentText(str(DEFAULTS["setups_int"]))
                        else:
                            widget.setCurrentText(str(DEFAULTS["setups_ext"]))
                        # disable widget but keep visible
                        widget.setEnabled(False)
                    else:
                        # re-enable widget for manual edits
                        widget.setEnabled(True)
                except Exception:
                    # swallow errors (robustness)
                    continue
        # After lock/unlock, animate recalc to update summary rows visually
        self.trigger_recalc_with_row_fades()

    # --------------------------------------------------------
    # Handler when lunch placement mode toggles (Auto <-> Fixed)
    # --------------------------------------------------------
    def lunch_mode_changed(self, state):
        # simply re-run animated recalc to reflect mode change
        self.trigger_recalc_with_row_fades()

    # --------------------------------------------------------
    # Handler when fixed hours spinbox changes (only matters if Fixed mode active)
    # --------------------------------------------------------
    def lunch_fixed_hours_changed(self, val):
        # only animate recalc if in Fixed mode (Auto unchecked)
        if not self.lunch_auto_toggle.isChecked():
            self.trigger_recalc_with_row_fades()

    # --------------------------------------------------------
    # Load a fountain file, parse it, and populate table
    # --------------------------------------------------------
    def load_fountain_file(self):
        # open file dialog to pick .fountain files
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Fountain", "", "Fountain Files (*.fountain)")
        if not file_path:
            # user cancelled; nothing to do
            return
        # store path for export naming
        self.current_fountain_path = file_path
        # read UTF-8 content
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        # parse content into scenes
        self.scenes = self.parse_fountain(content)
        # populate the visible table with scenes and summaries
        self.populate_table()
        # if lock setups toggle was ON before loading, enforce lock now on new rows
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

    # --------------------------------------------------------
    # Simple fountain parser that splits on INT./EXT. headings
    # Returns list of dicts: { "heading": str, "content": [lines] }
    # --------------------------------------------------------
    def parse_fountain(self, content):
        scenes = []                    # accumulator
        current = None                 # placeholder for current scene while parsing
        # iterate each line of input
        for line in content.splitlines():
            stripped = line.strip()    # trim whitespace
            # treat lines that start with INT. or EXT. as scene headings
            if re.match(r"^(INT\.|EXT\.)", stripped, re.I):
                if current:
                    scenes.append(current)  # save previous scene
                current = {"heading": stripped, "content": []}
            elif current is not None:
                # append regular lines to current scene content
                current["content"].append(stripped)
        # append last scene if present
        if current:
            scenes.append(current)
        return scenes

    # --------------------------------------------------------
    # Calculate page representation and mm:ss for a scene using current WPP
    # Returns: (page_str, mmss)
    # --------------------------------------------------------
    def calculate_scene_length(self, scene_text):
        # count words in scene content
        words = len(re.findall(r"\w+", " ".join(scene_text)))
        # get current WPP (respects the toggle)
        wpp = self.get_current_wpp()
        # compute pages as float safely (guard divide-by-zero)
        pages = (words / wpp) if wpp > 0 else 0.0
        full = int(pages)                       # full pages
        eighths = int(round((pages - full) * 8))# fractional eighths
        # normalize if rounding produces 8 eighths (bump full page)
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
        # estimate seconds (1 page ~ 60s)
        seconds = int(round(pages * 60))
        mm, ss = divmod(seconds, 60)
        mmss = f"{mm:02}:{ss:02}"
        return page_str, mmss

    # --------------------------------------------------------
    # Compute total shooting seconds for a given scene row index using self.setup_minutes
    # --------------------------------------------------------
    def compute_scene_time(self, row):
        # retrieve setups widget (may be disabled but present)
        setups_widget = self.table.cellWidget(row, 5)
        # get mm:ss length item
        length_item = self.table.item(row, 4)
        # if missing data, return 0 seconds safely
        if setups_widget is None or length_item is None:
            return 0
        # parse setups count with fallback
        try:
            setups_val = int(setups_widget.currentText())
        except Exception:
            setups_val = 0
        # parse mm:ss with fallback
        try:
            mm, ss = map(int, length_item.text().split(":"))
        except Exception:
            mm, ss = 0, 0
        # base minutes from page-derived mm:ss
        base_minutes = mm + ss / 60.0
        # add setups penalty using dynamic minutes per setup
        total_minutes = base_minutes + setups_val * self.setup_minutes
        # return seconds integer
        return int(round(total_minutes * 60))

    # --------------------------------------------------------
    # When a per-row setups combo changes, update that row and re-run animated recalc
    # Robust to row insertions/removals because it finds widget by position or scanning.
    # --------------------------------------------------------
    def update_scene_row_for_box(self, box):
        # try to get the table index at the widget's position
        idx = self.table.indexAt(box.pos())
        row = idx.row()
        # fallback scan in case indexAt failed
        if row == -1:
            for r in range(self.table.rowCount()):
                if self.table.cellWidget(r, 5) is box:
                    row = r
                    break
        # if still not found, exit
        if row == -1:
            return
        # compute seconds and write to column 6
        secs = self.compute_scene_time(row)
        self.table.setItem(row, 6, QTableWidgetItem(str(timedelta(seconds=secs))))
        # animated recalc to refresh summary rows
        self.trigger_recalc_with_row_fades()

    # --------------------------------------------------------
    # Remove summary rows (Lunch, Total, Wrap)
    # Iterate backwards so row removals do not disturb earlier indices
    # --------------------------------------------------------
    def remove_summary_rows(self):
        for r in reversed(range(self.table.rowCount())):
            item = self.table.item(r, 0)
            if item is None:
                continue
            text = item.text()
            if any(text.startswith(prefix) for prefix in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                self.table.removeRow(r)

    # --------------------------------------------------------
    # Animated recalc variant: removes old summaries, computes new, inserts them and animates per-row fades
    # This is used by the recalc button and when toggles that the user wants to see animated.
    # --------------------------------------------------------
    def trigger_recalc_with_row_fades(self):
        # remove prior summaries
        self.remove_summary_rows()
        # compute new schedule values
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        # insert lunch if present (animate per-row)
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=True)
        # insert total and wrap rows with animation
        self.insert_total_row(total, animate=True)
        self.insert_wrap_row(wrap, animate=True)
        # update numbering so summary rows are unnumbered
        self.update_row_numbers()

    # --------------------------------------------------------
    # Non-animated recalculation used by fast changes (e.g., minutes-per-setup spin)
    # --------------------------------------------------------
    def recalculate_schedule(self):
        # remove previous summaries
        self.remove_summary_rows()
        # compute schedule values
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        # insert new summaries WITHOUT animation for speed
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)
        # refresh numbering
        self.update_row_numbers()

    # --------------------------------------------------------
    # The scheduling algorithm:
    # - calculates per-scene durations (compute_scene_time)
    # - determines lunch insertion either by midpoint or fixed hours after start
    # - returns total scene seconds, wrap clock string, lunch_start datetime or None, insert index or None
    # --------------------------------------------------------
    def calculate_schedule(self):
        total_scene_seconds = 0
        # GUI inputs for extras
        lunch_min = int(self.lunch_duration_input.currentText())
        lunch_dur = lunch_min * 60
        move_min = int(self.move_duration_input.currentText()) * 60
        move_count = int(self.company_moves_input.currentText())
        include = self.include_moves_lunch_toggle.isChecked()
        # collect per-scene durations
        durations = []
        for i in range(len(self.scenes)):
            s = self.compute_scene_time(i)
            durations.append(s)
            total_scene_seconds += s
        # lunch insertion logic
        lunch_start = None
        insert_index = None
        # parse start time for clock math
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
            # Fixed-after-X-hours mode
            fixed_hours = int(self.lunch_fixed_spin.value())
            fixed_seconds = fixed_hours * 3600
            running = 0
            for i, secs in enumerate(durations):
                running += secs
                if running >= fixed_seconds and include and lunch_start is None:
                    insert_index = i + 1
                    lunch_start = start_dt + timedelta(seconds=running)
                    break
        # compute total seconds including extras if included
        total_seconds = total_scene_seconds
        if include:
            total_seconds += lunch_dur + (move_min * move_count)
        # compute wrap clock string
        wrap_dt = start_dt + timedelta(seconds=total_seconds)
        return total_scene_seconds, wrap_dt.strftime("%H:%M"), lunch_start, insert_index

    # --------------------------------------------------------
    # Populate the table with scene rows and summary rows (non-animated initial load)
    # --------------------------------------------------------
    def populate_table(self):
        # clear any existing merged spans and items
        self.table.clearSpans()
        self.table.clear()
        # remove lingering summary rows if any
        self.remove_summary_rows()
        # define headers (note "Camera Setups (Count)" header)
        headers = [
            "Scene Heading", "Actions", "Dialogue",
            "Length (pages+1/8s)", "Length (MM:SS)",
            "Camera Setups (Count)", "Shooting Time (HH:MM:SS)"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        # set number of rows to number of scenes
        self.table.setRowCount(len(self.scenes))
        # populate each scene row
        for i, sc in enumerate(self.scenes):
            heading = sc["heading"]
            # compute page length and mm:ss using current WPP
            page_len, mmss = self.calculate_scene_length(sc["content"])
            # create setups combo (1..20)
            setups_box = QComboBox()
            setups_box.addItems([str(n) for n in range(1, 21)])
            # default INT / EXT settings
            if heading.upper().startswith("INT"):
                setups_box.setCurrentText(str(DEFAULTS["setups_int"]))
            else:
                setups_box.setCurrentText(str(DEFAULTS["setups_ext"]))
            # connect change handler robustly referencing widget
            setups_box.currentTextChanged.connect(lambda t, box=setups_box: self.update_scene_row_for_box(box))
            # place heading, page_len, mmss
            self.table.setItem(i, 0, QTableWidgetItem(heading))
            self.table.setItem(i, 3, QTableWidgetItem(page_len))
            self.table.setItem(i, 4, QTableWidgetItem(mmss))
            # place setups widget in column 5
            self.table.setCellWidget(i, 5, setups_box)
            # compute initial shooting time and put into column 6
            self.table.setItem(i, 6, QTableWidgetItem(str(timedelta(seconds=self.compute_scene_time(i)))))
        # compute summaries
        total, wrap, lunch_start, insert_index = self.calculate_schedule()
        # insert lunch non-animated initially (we keep initial load fast)
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
        # append total and wrap rows non-animated
        self.insert_total_row(total, animate=False)
        self.insert_wrap_row(wrap, animate=False)
        # if lock setups toggle is on, enforce defaults/disable per-row combos
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)
        # update vertical numbers so only scene rows are numbered
        self.update_row_numbers()

    # --------------------------------------------------------
    # Helper: create a centered bold 12pt QTableWidgetItem with background color
    # --------------------------------------------------------
    def make_centered_item(self, text, color):
        item = QTableWidgetItem(text)
        item.setBackground(QBrush(QColor(color)))
        item.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    # -------------------------
    # Animate just the visual insertion of a row (overlay over that row)
    # -------------------------
    def animate_row(self, row):
        overlay = QWidget(self.table.viewport())   # overlay parented to table viewport
        rect = self.table.visualRect(self.table.model().index(row, 0))  # visual rect of row
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

    # --------------------------------------------------------
    # Insert lunch summary row at index, optionally animate
    # --------------------------------------------------------
    def insert_lunch_row(self, row_index, lunch_start_dt, lunch_minutes, animate=True):
        self.table.insertRow(row_index)
        text = f"LUNCH — Starts at {lunch_start_dt.strftime('%H:%M')} ({str(timedelta(minutes=lunch_minutes))})"
        item = self.make_centered_item(text, "orange")
        self.table.setItem(row_index, 0, item)
        self.table.setSpan(row_index, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row_index)

    # --------------------------------------------------------
    # Insert total shoot length row, optionally animate
    # --------------------------------------------------------
    def insert_total_row(self, total_seconds, animate=True):
        row = self.table.rowCount()
        self.table.insertRow(row)
        text = f"TOTAL SHOOT LENGTH — {str(timedelta(seconds=total_seconds))}"
        item = self.make_centered_item(text, "lightgreen")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row)

    # --------------------------------------------------------
    # Insert estimated wrap row, optionally animate
    # --------------------------------------------------------
    def insert_wrap_row(self, wrap_str, animate=True):
        row = self.table.rowCount()
        self.table.insertRow(row)
        text = f"ESTIMATED WRAP — {wrap_str}"
        item = self.make_centered_item(text, "lightblue")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        if animate:
            self.animate_row(row)

    # --------------------------------------------------------
    # Update vertical header numbering: only scene rows numbered
    # --------------------------------------------------------
    def update_row_numbers(self):
        for r in range(self.table.rowCount()):
            if not self.table.verticalHeaderItem(r):
                self.table.setVerticalHeaderItem(r, QTableWidgetItem())
            header_item = self.table.verticalHeaderItem(r)
            first_item = self.table.item(r, 0)
            if first_item and any(first_item.text().startswith(p) for p in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                header_item.setText("")   # summary rows: no number
            else:
                header_item.setText(str(r + 1))  # scene rows numbered from 1

    # --------------------------------------------------------
    # Gather table as list-of-lists for exports
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # Export dispatcher (CSV / PDF / Both)
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # CSV export to same folder as source .fountain
    # --------------------------------------------------------
    def export_csv(self):
        base = os.path.dirname(self.current_fountain_path)
        name = os.path.splitext(os.path.basename(self.current_fountain_path))[0]
        path = os.path.join(base, f"breakdown_{name}.csv")
        data = self.get_table_data()
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(data)

    # --------------------------------------------------------
    # PDF export preserving merged summary rows (SPANS) and colors
    # --------------------------------------------------------
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
# Run the application if executed directly
# ------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)         # create QApplication to manage the GUI app lifecycle
    window = ProducersToolkit()          # instantiate the main window
    window.show()                        # display the window
    sys.exit(app.exec())                 # enter Qt event loop and exit when the window closes
#FIRST WORKING TEST