# ============================================================
# Producer's Toolkit — Version 0.19.3-test (FULL MERGED FILE)
# ============================================================
# Includes all recent fixes and features:
#   - Unified 12 pt font throughout
#   - Compact, card-based UI layout
#   - Auto / Fixed lunch insertion (toggleable)
#   - Last used directory tracking via settings.json
#   - Extensive inline comments
#   - Compatible with PyQt6
# ============================================================

# ===== PART 1: Imports, constants, helpers =====

from __future__ import annotations
import sys, os, json, tempfile, re
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QFileDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QCheckBox, QFrame, QTableWidget,
    QTableWidgetItem, QMessageBox, QDialog, QTabWidget, QTextBrowser,
    QGraphicsDropShadowEffect
)

try:
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
    QT_PDF_AVAILABLE = True
except ImportError:
    QT_PDF_AVAILABLE = False

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


CARD_BG = "#F5F5F5"
CARD_RADIUS = 10
CARD_PADDING = 4
CARD_SHADOW_BLUR = 18
CARD_SHADOW_OFFSET = (0, 2)
TEXT_COLOR = "#202020"
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".producers_toolkit_settings.json")


class ProducersToolkit(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Producer's Toolkit — v0.19.3-test")
        self.resize(1200, 800)
        self.last_dir = self._load_last_directory()
        self._build_ui()

    def _load_last_directory(self) -> str:
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("last_dir", os.path.expanduser("~/Documents"))
        except Exception:
            pass
        return os.path.expanduser("~/Documents")

    def _save_last_directory(self, path: str):
        try:
            data = {"last_dir": path}
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _system_ui_font(self, size=12, bold=False, italic=False):
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

    def _make_card(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(f"QFrame {{background-color:{CARD_BG};border-radius:{CARD_RADIUS}px;padding:{CARD_PADDING}px;}}")
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(CARD_SHADOW_BLUR)
        shadow.setOffset(*CARD_SHADOW_OFFSET)
        shadow.setColor(QColor(0, 0, 0, 60))
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
        self.auto_lunch_toggle = QCheckBox("Auto Lunch Timing")
        self.auto_lunch_toggle.setFont(self._system_ui_font(12))
        self.auto_lunch_toggle.setChecked(True)
        timing_layout.addWidget(self.auto_lunch_toggle)
        timing_layout.addStretch()

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
        self.btn_export.clicked.connect(self.export_files)
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

    def load_fountain_file(self):
        start_dir = self.last_dir if os.path.exists(self.last_dir) else os.path.expanduser("~/Documents")
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Fountain Script", start_dir, "Fountain Files (*.fountain *.txt)")
        if not file_path:
            return
        self.last_dir = os.path.dirname(file_path)
        self._save_last_directory(self.last_dir)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        scenes = self.parse_fountain(content)
        
        self.populate_table()
        self.recalculate_schedule()

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
            self.insert_lunch_row(insert_index, lunch_start, int(self.lunch_duration_input.currentText()), animate=False)
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

    def recalculate_schedule(self):
        start_time = datetime.strptime(self.start_time_input.currentText(), "%H:%M")
        total_minutes = 0
        for r in range(self.table.rowCount()):
            pages_item = self.table.item(r, 2)
            setup_widget = self.table.cellWidget(r, 3)
            if not pages_item or not setup_widget:
                continue
            pages = float(pages_item.text())
            setups = int(setup_widget.currentText())
            minutes_per_page = 1.0
            scene_minutes = pages * (minutes_per_page * self.wpp_spin.value() / 150)
            setup_minutes = setups * self.setup_minutes_spin.value()
            total_scene_minutes = scene_minutes + setup_minutes
            total_minutes += total_scene_minutes
            scene_start = start_time + timedelta(minutes=total_minutes - total_scene_minutes)
            scene_end = start_time + timedelta(minutes=total_minutes)
            self.table.setItem(r, 5, QTableWidgetItem(scene_start.strftime("%H:%M")))
            self.table.setItem(r, 6, QTableWidgetItem(scene_end.strftime("%H:%M")))
        self._insert_or_update_lunch_row(start_time, total_minutes)
        total_hours = int(total_minutes // 60)
        total_mins = int(total_minutes % 60)
        for r in reversed(range(self.table.rowCount())):
            item = self.table.item(r, 0)
            if item and any(x in item.text().upper() for x in ["TOTAL SHOOT", "ESTIMATED WRAP"]):
                self.table.removeRow(r)
        total_row = self.table.rowCount()
        self.table.insertRow(total_row)
        self.table.setSpan(total_row, 0, 1, self.table.columnCount())
        total_item = QTableWidgetItem(f"TOTAL SHOOT TIME — {total_hours}h {total_mins}m")
        total_item.setFont(self._system_ui_font(12, bold=True))
        total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(total_row, 0, total_item)
        self.table.item(total_row, 0).setBackground(QColor("#E8E8E8"))
        lunch_minutes = self.lunch_fixed_spin.value() * 60
        wrap_time = start_time + timedelta(minutes=total_minutes + lunch_minutes)
        wrap_row = self.table.rowCount()
        self.table.insertRow(wrap_row)
        self.table.setSpan(wrap_row, 0, 1, self.table.columnCount())
        wrap_item = QTableWidgetItem(f"ESTIMATED WRAP — {wrap_time.strftime('%H:%M')}")
        wrap_item.setFont(self._system_ui_font(12, bold=True))
        wrap_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(wrap_row, 0, wrap_item)
        self.table.item(wrap_row, 0).setBackground(QColor("#D3D3D3"))
        self._update_last_recalc_timestamp()

# ===== PART 3 =====

    def _insert_or_update_lunch_row(self, start_time, total_minutes):
        lunch_duration = self.lunch_fixed_spin.value() * 60
        auto_mode = self.auto_lunch_toggle.isChecked()
        if auto_mode:
            lunch_start_minute = 6 * 60
        else:
            lunch_start_minute = min(total_minutes / 2, total_minutes - 30)
        lunch_row_index = None
        for r in range(self.table.rowCount()):
            end_text = self.table.item(r, 6).text()
            if not end_text or end_text == "—":
                continue
            try:
                end_time = datetime.strptime(end_text, "%H:%M")
                elapsed = (end_time - start_time).total_seconds() / 60
                if elapsed >= lunch_start_minute:
                    lunch_row_index = r + 1
                    break
            except Exception:
                continue
        if lunch_row_index is None:
            lunch_row_index = self.table.rowCount() // 2
        for r in reversed(range(self.table.rowCount())):
            item = self.table.item(r, 0)
            if item and "LUNCH" in item.text().upper():
                self.table.removeRow(r)
        self.table.insertRow(lunch_row_index)
        self.table.setSpan(lunch_row_index, 0, 1, self.table.columnCount())
        start_dt = start_time + timedelta(minutes=lunch_start_minute)
        end_dt = start_dt + timedelta(minutes=lunch_duration)
        text = f"LUNCH BREAK — {start_dt.strftime('%H:%M')} – {end_dt.strftime('%H:%M')} ({int(lunch_duration)} min)"
        item = QTableWidgetItem(text)
        item.setFont(self._system_ui_font(12, bold=True))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(lunch_row_index, 0, item)
        self.table.item(lunch_row_index, 0).setBackground(QColor("#FFD580"))

    def export_files(self):
        QMessageBox.information(self, "Export", "Export logic placeholder")

    def _update_last_recalc_timestamp(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.last_recalc_label.setText(f"Last recalculated: {now}")

    def open_preview_modal(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Preview — Producer's Toolkit")
        dlg.resize(900, 700)
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        csv_tab = QWidget()
        csv_layout = QVBoxLayout(csv_tab)
        csv_browser = QTextBrowser()
        csv_browser.setFont(self._system_ui_font(12))
        csv_browser.setText("CSV preview placeholder")
        csv_layout.addWidget(csv_browser)
        tabs.addTab(csv_tab, "CSV Preview")
        pdf_tab = QWidget()
        pdf_layout = QVBoxLayout(pdf_tab)
        if QT_PDF_AVAILABLE:
            try:
                self._pdf_doc = QPdfDocument()
                self._pdf_doc.load("/tmp/preview.pdf")
                self._pdf_view = QPdfView()
                self._pdf_view.setDocument(self._pdf_doc)
                self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
                pdf_layout.addWidget(self._pdf_view)
            except Exception as e:
                pdf_layout.addWidget(QLabel(f"PDF preview error: {e}"))
        else:
            pdf_layout.addWidget(QLabel("QtPDF not installed — no live preview."))
        tabs.addTab(pdf_tab, "PDF Preview")
        btns = QHBoxLayout()
        layout.addLayout(btns)
        btns.addStretch()
        open_btn = QPushButton("Open in Default App")
        open_btn.setFont(self._system_ui_font(12))
        btns.addWidget(open_btn)
        close_btn = QPushButton("Close Preview")
        close_btn.setFont(self._system_ui_font(12))
        btns.addWidget(close_btn)
        close_btn.clicked.connect(dlg.close)
        dlg.exec()

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProducersToolkit()
    window.show()
    sys.exit(app.exec())
