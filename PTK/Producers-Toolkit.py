# ------------------------------------------------------------
# PRODUCER'S TOOLKIT - Version v0.17-pre
# ------------------------------------------------------------
# Single-file application (PyQt6) with heavy inline comments.
#
# Notable:
#   - Adds "Minutes per Setup" spinbox (1..30 minutes, default 5)
#   - All setup-time math uses self.lx_setup_minutes
#   - Changing Minutes-per-Setup auto-recalculates (no fade)
#   - Recalculate button still triggers fade + recalc as before
#   - "Use and Lock Default Number of Setups (INT=3, EXT=5)" locks combos (visible but disabled)
#   - Global Controls Bar uses pale gray background (#f2f2f2)
#   - All code heavily commented, spaced for readability
# ------------------------------------------------------------

# --- standard library imports ---
import sys                                     # system-level functions (argv, exit)
import os                                      # file path helpers for export naming
import re                                      # regular expressions for parsing text
import csv                                     # CSV export support
from datetime import timedelta, datetime      # time arithmetic and formatting

# --- PyQt6 imports ---
from PyQt6.QtWidgets import (                   # GUI widget classes
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox, QLabel,
    QSpinBox, QCheckBox, QMessageBox, QFileDialog, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QPropertyAnimation  # alignment constants and animations
from PyQt6.QtGui import QBrush, QColor, QFont     # styling helpers for table cells

# --- ReportLab imports for PDF export ---
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ------------------------------------------------------------
# Default and UI constants
# ------------------------------------------------------------
DEFAULTS = {                                    # configuration defaults
    "words_per_page": 150,                      # default words per script page (WPP)
    "lx_setup_minutes": 5,                      # default minutes added per setup
    "setups_int": 3,                            # default setups for INT scenes
    "setups_ext": 5,                            # default setups for EXT scenes
    "default_move_duration": 10,                # minutes per company move
    "default_lunch_duration": 60,               # default lunch length minutes
    "default_start_time": "08:00"               # default shoot start time (24h)
}

# fade animation duration (milliseconds) used for recalc button UX
FADE_DURATION_MS = 500

# pale gray color for the global controls bar background
GLOBAL_BAR_COLOR = "#f2f2f2"

# ------------------------------------------------------------
# Main application class
# ------------------------------------------------------------
class ProducersToolkit(QMainWindow):
    # -------------------------
    # Initialize the main window and all controls
    # -------------------------
    def __init__(self):
        # call the base class constructor
        super().__init__()                         # initialize QMainWindow internals

        # set the window title
        self.setWindowTitle("Producer's Toolkit  v0.17-pre")

        # set an initial window size (width x height)
        self.resize(1400, 820)

        # application state variables initialization
        self.scenes = []                            # list to hold parsed scenes (dicts)
        self.current_fountain_path = ""             # path to the currently loaded fountain file
        self.words_per_page = DEFAULTS["words_per_page"]  # active words-per-page value
        self.lx_setup_minutes = DEFAULTS["lx_setup_minutes"]    # active minutes per setup (now dynamic)

        # create the central widget that will contain layouts and widgets
        central = QWidget()                         # main central container widget
        self.setCentralWidget(central)              # attach as the central widget

        # create top-level vertical layout
        self.main_layout = QVBoxLayout(central)     # vertical layout for stacking UI sections

        # -------------------------
        # Top row: Load button
        # -------------------------
        top_row = QHBoxLayout()                     # horizontal layout for top row
        self.main_layout.addLayout(top_row)         # add top row to main layout

        # create and add the Load Fountain button
        self.load_btn = QPushButton("Load Fountain File")
        self.load_btn.clicked.connect(self.load_fountain_file)  # connect click -> file loader
        top_row.addWidget(self.load_btn,alignment=Qt.AlignmentFlag.AlignHCenter) # place load button on top row

        # spacer label for visual balance
        top_row.addWidget(QLabel(""))               # small spacer widget

        # -------------------------
        # Global Controls Bar (pale gray background)
        # Two stacked rows: timing row and calculation row
        # -------------------------
        self.global_bar = QWidget()                 # container for grouped global controls
        # apply pale gray background and some padding via stylesheet
        self.global_bar.setStyleSheet(f"background-color: {GLOBAL_BAR_COLOR}; padding: 8px;")
        self.main_layout.addWidget(self.global_bar) # add to main layout

        # vertical layout inside the global bar (to hold two horizontal rows)
        self.global_bar_layout = QVBoxLayout(self.global_bar)

        # ---------- Global Bar - Row A: Timing Inputs ----------
        self.label = QLabel("Basic Schedule Info:")
        self.label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.timing_row = QHBoxLayout()             # horizontal layout for timing inputs
        self.global_bar_layout.addWidget(self.label)
        self.global_bar_layout.addLayout(self.timing_row)  # add timing row to global bar
        

        # Start time ComboBox (24h in 15-minute increments)
        self.start_time_input = QComboBox()         # combo for start times
        times = [f"{h:02}:{m:02}" for h in range(24) for m in (0, 15, 30, 45)]
        self.start_time_input.addItems(times)       # populate times
        self.start_time_input.setCurrentText(DEFAULTS["default_start_time"])  # default
        self.timing_row.addWidget(QLabel("Shoot start time:"))  # label
        self.timing_row.addWidget(self.start_time_input)  # add control

        # Company moves ComboBox (0..20)
        self.company_moves_input = QComboBox()      # create the combo
        self.company_moves_input.addItems([str(i) for i in range(0, 21)])  # populate 0..20
        self.timing_row.addWidget(QLabel("Company moves:"))  # label
        self.timing_row.addWidget(self.company_moves_input)  # add control

        # Move duration ComboBox (0..120 minutes)
        self.move_duration_input = QComboBox()      # combo for minutes per move
        self.move_duration_input.addItems([str(i) for i in range(0, 121)]) # 0..120
        self.move_duration_input.setCurrentText(str(DEFAULTS["default_move_duration"]))  # default
        self.timing_row.addWidget(QLabel("Move duration (min):"))  # label
        self.timing_row.addWidget(self.move_duration_input)        # add control

        # Lunch duration ComboBox (0..180 minutes)
        self.lunch_duration_input = QComboBox()     # combo for lunch minutes
        self.lunch_duration_input.addItems([str(i) for i in range(0, 181)])  # 0..180
        self.lunch_duration_input.setCurrentText(str(DEFAULTS["default_lunch_duration"]))  # default
        self.timing_row.addWidget(QLabel("Lunch duration (min):"))  # label
        self.timing_row.addWidget(self.lunch_duration_input)        # add control

        

        # Include moves & lunch toggle (checkbox)
        self.include_moves_lunch_toggle = QCheckBox("Include moves && lunch in totals?")
        self.include_moves_lunch_toggle.setChecked(True)  # default ON
        self.timing_row.addWidget(self.include_moves_lunch_toggle)  # add toggle

        # add a stretch (pushes following widgets to the left)
        self.timing_row.addStretch()

        # ---------- Global Bar - Row B: Calculation & WPP Controls ----------
        self.calc_row = QHBoxLayout()               # horizontal layout for calc controls
        self.global_bar_layout.addLayout(self.calc_row)  # add second row to global bar

        # Custom WPP toggle (checkbox)
        self.custom_wpp_toggle = QCheckBox("Use Custom Words Per Page")
        self.custom_wpp_toggle.setChecked(False)     # default OFF
        self.custom_wpp_toggle.stateChanged.connect(self.toggle_custom_wpp_changed)  # handler
        self.calc_row.addWidget(self.custom_wpp_toggle)  # add to calc row

        # WPP spinbox (100..250)
        self.wpp_spin = QSpinBox()                   # create spinbox control
        self.wpp_spin.setRange(100, 250)             # allowed range
        self.wpp_spin.setValue(DEFAULTS["words_per_page"])  # default value 150
        self.wpp_spin.setEnabled(False)              # disabled until toggle on
        self.wpp_spin.valueChanged.connect(self.wpp_value_changed)  # handler
        self.calc_row.addWidget(QLabel("Words Per Page:"))  # label
        self.calc_row.addWidget(self.wpp_spin)        # add spinbox

        # New: Minutes per Setup spinbox (1..30), default self.lx_setup_minutes (5)
        self.lx_setup_minutes_spin = QSpinBox()          # spinbox for minutes per setup
        self.lx_setup_minutes_spin.setRange(1, 30)       # allowed values 1..30
        self.lx_setup_minutes_spin.setValue(self.lx_setup_minutes)  # default 5
        # When this value changes, we will auto-recalculate (no fade)
        self.lx_setup_minutes_spin.valueChanged.connect(self.lx_setup_minutes_changed)
        self.calc_row.addWidget(QLabel("LX & Camera Setup (mins per setup):"))  # label
        self.calc_row.addWidget(self.lx_setup_minutes_spin)        # add control

        # Use and Lock Default Number of Setups toggle (visible but locks combos)
        self.lock_setups_toggle = QCheckBox("Use and Lock Default Number of Setups (INT=3, EXT=5)")
        self.lock_setups_toggle.setChecked(False)      # default OFF
        self.lock_setups_toggle.stateChanged.connect(self.toggle_default_setups_lock)  # handler
        self.calc_row.addWidget(self.lock_setups_toggle)  # add to calc row

        # push the recalc button to the far right
        self.calc_row.addStretch()

        # Recalculate Schedule button (manual trigger with fade UX)
        self.recalc_button = QPushButton("Recalculate Schedule")
        self.recalc_button.clicked.connect(self.trigger_recalc_with_fade)  # preferred UX
        self.calc_row.addWidget(self.recalc_button)  # add to UI

        # -------------------------
        # Main Table Widget (below the global bar)
        # -------------------------
        self.table = QTableWidget()                  # create table widget
        self.main_layout.addWidget(self.table)       # add to main layout

        # -------------------------
        # Export row below table (CSV / PDF)
        # -------------------------
        export_row = QHBoxLayout()                   # layout for export controls
        self.export_dropdown = QComboBox()           # dropdown for export choice
        self.export_dropdown.addItems(["Export CSV", "Export PDF", "Export Both"])
        self.export_button = QPushButton("Export")   # export button
        self.export_button.clicked.connect(self.export_file)  # attach handler
        export_row.addWidget(self.export_dropdown)   # add dropdown
        export_row.addWidget(self.export_button)     # add button
        export_row.addStretch()
        self.main_layout.addLayout(export_row)       # attach export row to main layout

    # -------------------------
    # Helper: Return the active WPP (words per page)
    # -------------------------
    def get_current_wpp(self):
        # If the custom WPP toggle is checked, return the spinbox value; else return default
        if self.custom_wpp_toggle.isChecked():
            return int(self.wpp_spin.value())
        return int(DEFAULTS["words_per_page"])

    # -------------------------
    # Event: custom WPP toggle changed
    # -------------------------
    def toggle_custom_wpp_changed(self, state):
        # If checked, enable spinbox and update words_per_page
        if state:
            self.wpp_spin.setEnabled(True)
            self.words_per_page = int(self.wpp_spin.value())
        else:
            # If unchecked, disable spinbox and revert to default
            self.wpp_spin.setEnabled(False)
            self.words_per_page = DEFAULTS["words_per_page"]

        # Trigger recalculation with fade to reflect change
        self.trigger_recalc_with_fade()

    # -------------------------
    # Event: WPP spin value changed
    # -------------------------
    def wpp_value_changed(self, val):
        # Update internal WPP and recalc with fade for visual confirmation
        self.words_per_page = int(val)
        self.trigger_recalc_with_fade()

    # -------------------------
    # Event: Minutes-per-setup spinbox changed (auto-recalc, no fade)
    # -------------------------
    def lx_setup_minutes_changed(self, val):
        # Update the internal lx_setup_minutes variable
        self.lx_setup_minutes = int(val)

        # Immediately recalculate schedule without animation for speed
        self.recalculate_schedule()

    # -------------------------
    # Handler: toggling lock/default setups behavior
    # -------------------------
    def toggle_default_setups_lock(self, state):
        # Convert state to boolean (nonzero == True)
        lock_on = bool(state)

        # Iterate all rows and apply lock/default logic
        for r in range(self.table.rowCount()):
            # get widget in column 5 (setups combo) if present
            widget = self.table.cellWidget(r, 5)

            # If there is a widget (combo box), act on it
            if widget is not None:
                try:
                    if lock_on:
                        # Get heading text safely
                        item = self.table.item(r, 0)
                        heading_text = item.text() if item else ""

                        # Apply default based on INT/EXT and disable widget
                        if heading_text.upper().startswith("INT"):
                            widget.setCurrentText(str(DEFAULTS["setups_int"]))
                        else:
                            widget.setCurrentText(str(DEFAULTS["setups_ext"]))

                        # Disable combo so it's visible but locked
                        widget.setEnabled(False)
                    else:
                        # Unlock: enable for manual editing
                        widget.setEnabled(True)
                except Exception:
                    # If unexpected error, skip this widget gracefully
                    continue

        # After applying lock/unlock, recalc (use fade UX to show change)
        self.trigger_recalc_with_fade()

    # -------------------------
    # Load fountain file and parse it
    # -------------------------
    def load_fountain_file(self):
        # Open file dialog filtered for .fountain files
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Fountain", "", "Fountain Files (*.fountain)")
        if not file_path:
            # If user canceled, do nothing
            return

        # Save path for exports
        self.current_fountain_path = file_path

        # Read file contents as UTF-8
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Parse into scenes
        self.scenes = self.parse_fountain(content)

        # Populate the table UI
        self.populate_table()

        # If lock-setups toggle is on, enforce lock immediately
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

    # -------------------------
    # Simple fountain parser that splits on INT./EXT.
    # -------------------------
    def parse_fountain(self, content):
        scenes = []                        # list to collect scenes
        current = None                     # placeholder for current scene
        for line in content.splitlines():
            stripped = line.strip()        # trim whitespace
            if re.match(r"^(INT\.|EXT\.)", stripped, re.I):
                if current:
                    scenes.append(current) # save previous scene
                current = {"heading": stripped, "content": []}  # start new scene
            elif current is not None:
                current["content"].append(stripped)  # add content lines
        if current:
            scenes.append(current)          # append final scene
        return scenes                       # return parsed scenes

    # -------------------------
    # Calculate scene length (page string, mm:ss) using current WPP
    # -------------------------
    def calculate_scene_length(self, scene_text):
        # Count words via regex tokenization
        words = len(re.findall(r"\w+", " ".join(scene_text)))

        # Use get_current_wpp() so the toggle/spinbox is respected
        wpp = self.get_current_wpp()

        # Compute pages as float (guard divide-by-zero)
        pages = (words / wpp) if wpp > 0 else 0.0

        # integer part and fractional eighths
        full = int(pages)
        eighths = int(round((pages - full) * 8))
        if eighths == 8:
            full += 1
            eighths = 0

        # format human-friendly page string
        if full == 0 and eighths > 0:
            page_str = f"{eighths}/8"
        elif eighths > 0:
            page_str = f"{full} {eighths}/8"
        else:
            page_str = f"{full}"

        # convert pages to seconds (1 page ≈ 60s)
        seconds = int(round(pages * 60))
        mm, ss = divmod(seconds, 60)
        mmss = f"{mm:02}:{ss:02}"
        return page_str, mmss

    # -------------------------
    # Compute shooting seconds for a given scene row index using self.lx_setup_minutes
    # -------------------------
    def compute_scene_time(self, row):
        # retrieve the setups widget in column 5
        setups_widget = self.table.cellWidget(row, 5)

        # retrieve the mm:ss text in column 4
        length_item = self.table.item(row, 4)

        # if either is missing, safe fallback to 0 seconds
        if setups_widget is None or length_item is None:
            return 0

        # parse setups number with fallback
        try:
            setups_val = int(setups_widget.currentText())
        except Exception:
            setups_val = 0

        # parse mm:ss into minutes/seconds with fallback
        try:
            mm, ss = map(int, length_item.text().split(":"))
        except Exception:
            mm, ss = 0, 0

        # base minutes from scene length
        base_minutes = mm + ss / 60.0

        # add setups penalty using dynamic self.lx_setup_minutes
        total_minutes = base_minutes + setups_val * self.lx_setup_minutes

        # return integer seconds
        return int(round(total_minutes * 60))

    # -------------------------
    # Handler for per-row setups combo change (robust to shifting rows)
    # -------------------------
    def update_scene_row_for_box(self, box):
        # find box's current row via indexAt using widget position
        idx = self.table.indexAt(box.pos())
        row = idx.row()

        # fallback: scan the table for the widget
        if row == -1:
            for r in range(self.table.rowCount()):
                if self.table.cellWidget(r, 5) is box:
                    row = r
                    break

        # if not found, return safely
        if row == -1:
            return

        # compute seconds and update column 6 display
        secs = self.compute_scene_time(row)
        self.table.setItem(row, 6, QTableWidgetItem(str(timedelta(seconds=secs))))

        # also trigger a recalc (with fade) to update summary rows visually
        self.trigger_recalc_with_fade()

    # -------------------------
    # Remove summary rows to avoid duplicates (LUNCH / TOTAL / ESTIMATED WRAP)
    # -------------------------
    def remove_summary_rows(self):
        # iterate rows backward to safely remove
        for r in reversed(range(self.table.rowCount())):
            item = self.table.item(r, 0)
            if item is None:
                continue
            text = item.text()
            if any(text.startswith(prefix) for prefix in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                self.table.removeRow(r)

    # -------------------------
    # Centralized fade + recalc UX function (used by recalc button & other UX flows)
    # -------------------------
    def trigger_recalc_with_fade(self):
        # create overlay covering the table viewport
        overlay = QWidget(self.table.viewport())

        # set geometry to cover viewport fully
        overlay.setGeometry(0, 0, self.table.viewport().width(), self.table.viewport().height())

        # create opacity effect and attach
        eff = QGraphicsOpacityEffect()
        overlay.setGraphicsEffect(eff)

        # fade-in animation
        anim = QPropertyAnimation(eff, b"opacity", overlay)
        anim.setDuration(FADE_DURATION_MS)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        # show overlay and start fade-in
        overlay.show()
        anim.start()

        # what to do when fade-in completes
        def on_fade_in_finished():
            # remove prior summary rows
            self.remove_summary_rows()

            # compute schedule summary values
            total, wrap, lunch_start, insert_index = self.calculate_schedule()

            # insert lunch if applicable
            if lunch_start is not None and insert_index is not None:
                self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()))

            # append total and wrap rows
            self.insert_total_row(total)
            self.insert_wrap_row(wrap)

            # refresh numbering
            self.update_row_numbers()

            # fade out overlay (slightly quicker)
            anim2 = QPropertyAnimation(eff, b"opacity", overlay)
            anim2.setDuration(FADE_DURATION_MS // 2)
            anim2.setStartValue(1.0)
            anim2.setEndValue(0.0)
            anim2.finished.connect(overlay.deleteLater)
            anim2.start()

        # connect finished signal to handler
        anim.finished.connect(on_fade_in_finished)

    # -------------------------
    # Recalculate schedule without fade (used by minutes-per-setup change)
    # -------------------------
    def recalculate_schedule(self):
        # remove old summary rows
        self.remove_summary_rows()

        # compute schedule values
        total, wrap, lunch_start, insert_index = self.calculate_schedule()

        # insert lunch if present
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()))

        # append total and wrap rows
        self.insert_total_row(total)
        self.insert_wrap_row(wrap)

        # update row numbering
        self.update_row_numbers()

    # -------------------------
    # Calculate schedule: returns totals and lunch insertion info
    # -------------------------
    def calculate_schedule(self):
        # total seconds for scenes (excluding lunch/moves)
        total_scene_seconds = 0

        # read GUI inputs for extras
        lunch_min = int(self.lunch_duration_input.currentText())
        lunch_dur = lunch_min * 60
        move_min = int(self.move_duration_input.currentText()) * 60
        move_count = int(self.company_moves_input.currentText())
        include = self.include_moves_lunch_toggle.isChecked()

        # durations list holds seconds per scene
        durations = []
        for i in range(len(self.scenes)):
            s = self.compute_scene_time(i)   # compute for row i using current lx_setup_minutes
            durations.append(s)
            total_scene_seconds += s

        # find midpoint to place lunch
        midpoint = total_scene_seconds // 2
        running = 0
        lunch_start = None
        insert_index = None

        # parse start time into datetime
        start_dt = datetime.strptime(self.start_time_input.currentText(), "%H:%M")

        # iterate durations to locate lunch insertion index
        for i, secs in enumerate(durations):
            running += secs
            if running >= midpoint and include and lunch_start is None:
                insert_index = i + 1                       # insert after scene i
                lunch_start = start_dt + timedelta(seconds=running)
                break

        # compute total seconds including extras if included
        total_seconds = total_scene_seconds
        if include:
            total_seconds += lunch_dur + (move_min * move_count)

        # compute wrap time clock
        wrap_dt = start_dt + timedelta(seconds=total_seconds)
        return total_scene_seconds, wrap_dt.strftime("%H:%M"), lunch_start, insert_index

    # -------------------------
    # Populate table: scenes and summary rows
    # -------------------------
    def populate_table(self):
        # clear any existing spans (merged cells)
        self.table.clearSpans()

        # clear items and headers
        self.table.clear()

        # ensure no leftover summary rows
        self.remove_summary_rows()

        # define headers
        headers = [
            "Scene Heading", "Actions", "Dialogue",
            "Length (pages+1/8s)", "Length (MM:SS)",
            "Setups", "Shooting Time (HH:MM:SS)"
        ]

        # apply headers to table
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        # set number of rows equal to number of scenes
        self.table.setRowCount(len(self.scenes))

        # populate each scene row
        for i, sc in enumerate(self.scenes):
            # heading text (e.g., "INT. OFFICE - DAY")
            heading = sc["heading"]

            # calculate page/time for scene
            page_len, mmss = self.calculate_scene_length(sc["content"])

            # create setups combo widget with options 1..20
            setups_box = QComboBox()
            setups_box.addItems([str(n) for n in range(1, 21)])

            # set reasonable default based on INT/EXT
            if heading.upper().startswith("INT"):
                setups_box.setCurrentText(str(DEFAULTS["setups_int"]))
            else:
                setups_box.setCurrentText(str(DEFAULTS["setups_ext"]))

            # connect combo to robust handler that takes the widget reference
            setups_box.currentTextChanged.connect(lambda t, box=setups_box: self.update_scene_row_for_box(box))

            # place items in table columns
            self.table.setItem(i, 0, QTableWidgetItem(heading))    # heading
            self.table.setItem(i, 3, QTableWidgetItem(page_len))   # pages
            self.table.setItem(i, 4, QTableWidgetItem(mmss))       # mm:ss
            self.table.setCellWidget(i, 5, setups_box)             # setups widget

            # initial shooting time for row
            self.table.setItem(i, 6, QTableWidgetItem(str(timedelta(seconds=self.compute_scene_time(i)))))

        # compute schedule summaries
        total, wrap, lunch_start, insert_index = self.calculate_schedule()

        # insert lunch row if applicable
        if lunch_start is not None and insert_index is not None:
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()))

        # append total and wrap rows
        self.insert_total_row(total)
        self.insert_wrap_row(wrap)

        # if lock_setups toggle is ON, enforce lock on the newly created rows
        if self.lock_setups_toggle.isChecked():
            self.toggle_default_setups_lock(1)

        # update row numbers (scene rows numbered, summary rows not)
        self.update_row_numbers()

    # -------------------------
    # Create a centered, bold, 12pt table item with background color
    # -------------------------
    def make_centered_item(self, text, color):
        item = QTableWidgetItem(text)                  # create item with given text
        item.setBackground(QBrush(QColor(color)))      # set background color
        item.setFont(QFont("Helvetica", 12, QFont.Weight.Bold))  # bold 12pt font
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)     # center text
        return item                                    # return prepared item

    # -------------------------
    # Simple overlay fade for a row
    # -------------------------
    def animate_row(self, row):
        overlay = QWidget(self.table.viewport())       # create overlay in table viewport
        rect = self.table.visualRect(self.table.model().index(row, 0))  # get row rect
        overlay.setGeometry(0, rect.y(), self.table.viewport().width(), rect.height())  # position
        eff = QGraphicsOpacityEffect()                 # create opacity effect
        overlay.setGraphicsEffect(eff)                 # attach effect
        anim = QPropertyAnimation(eff, b"opacity", overlay)  # animate opacity
        anim.setDuration(FADE_DURATION_MS)             # duration
        anim.setStartValue(0.0)                        # from transparent
        anim.setEndValue(1.0)                          # to opaque
        anim.finished.connect(overlay.deleteLater)     # cleanup after finish
        overlay.show()                                 # show overlay
        anim.start()                                   # start animation

    # -------------------------
    # Insert lunch summary row at index (merged across columns)
    # -------------------------
    def insert_lunch_row(self, row_index, lunch_start_dt, lunch_minutes):
        self.table.insertRow(row_index)                # insert new row at index
        text = f"LUNCH — Starts at {lunch_start_dt.strftime('%H:%M')} ({str(timedelta(minutes=lunch_minutes))})"
        item = self.make_centered_item(text, "orange") # style as orange bold center
        self.table.setItem(row_index, 0, item)         # set item in first column
        self.table.setSpan(row_index, 0, 1, self.table.columnCount())  # span across all cols
        self.animate_row(row_index)                    # animate insertion

    # -------------------------
    # Insert total shoot length summary at bottom
    # -------------------------
    def insert_total_row(self, total_seconds):
        row = self.table.rowCount()                    # row index at end
        self.table.insertRow(row)                      # append row
        text = f"TOTAL SHOOT LENGTH — {str(timedelta(seconds=total_seconds))}"
        item = self.make_centered_item(text, "lightgreen")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        self.animate_row(row)

    # -------------------------
    # Insert estimated wrap summary at bottom (after total)
    # -------------------------
    def insert_wrap_row(self, wrap_str):
        row = self.table.rowCount()                    # append row index
        self.table.insertRow(row)
        text = f"ESTIMATED WRAP — {wrap_str}"
        item = self.make_centered_item(text, "lightblue")
        self.table.setItem(row, 0, item)
        self.table.setSpan(row, 0, 1, self.table.columnCount())
        self.animate_row(row)

    # -------------------------
    # Number scene rows vertically, but leave summary rows unnumbered
    # -------------------------
    def update_row_numbers(self):
        for r in range(self.table.rowCount()):
            if not self.table.verticalHeaderItem(r):
                self.table.setVerticalHeaderItem(r, QTableWidgetItem())
            header_item = self.table.verticalHeaderItem(r)
            first_item = self.table.item(r, 0)
            if first_item and any(first_item.text().startswith(p) for p in ("LUNCH", "TOTAL SHOOT LENGTH", "ESTIMATED WRAP")):
                header_item.setText("")    # no number for summary rows
            else:
                header_item.setText(str(r + 1))  # scene rows numbered from 1

    # -------------------------
    # Gather table contents into list-of-lists for export
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
    # Export handler
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
    # Export CSV to same folder as source
    # -------------------------
    def export_csv(self):
        base = os.path.dirname(self.current_fountain_path)
        name = os.path.splitext(os.path.basename(self.current_fountain_path))[0]
        path = os.path.join(base, f"breakdown_{name}.csv")
        data = self.get_table_data()
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(data)

    # -------------------------
    # Export PDF using ReportLab; preserve merged summary rows
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
# Run the application
# ------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)         # create Qt application
    window = ProducersToolkit()          # instantiate the toolkit window
    window.show()                        # show window
    sys.exit(app.exec())                 # run event loop and exit on close
