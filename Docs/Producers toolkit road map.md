# 🎬 Producer's Toolkit — Development Roadmap

### 🧱 Current Stable Baseline
**Version:** v0.14.4  
**Status:** ✅ Verified Stable  
**Platform:** Cross-platform (Windows / macOS / Linux)  
**Python:** 3.12+  
**Core Dependencies:** PyQt5, ReportLab, re, datetime  

**Key Capabilities**
- Fountain parsing → scene table generation  
- Scene length (pages + time) estimation  
- Per-scene setup tracking  
- Automatic lunch, total, and wrap summary rows  
- Animated and merged summary rows  
- CSV + PDF export (preserving formatting)  
- Live recalculation after setup edits  
- Correct numbering and row handling  
- No duplicates on load or recalculation  

---

## 🗓️ v0.15 — Precision & User Experience Polish

**Goal:** Improve accuracy, clarity, and usability.  

**Features:**
1. 🎚 Adjustable *Words per Page (WPP)* setting in GUI  
   - Default 150 WPP  
   - Updates all scene lengths in real time  
2. 🕒 Adjustable "Page Time" ratio  
   - Allow user to define “1 page = X seconds” (default 60s)  
3. 🎨 Visual Enhancements  
   - Sticky table header  
   - Alternating row colors for readability  
   - Light/Dark mode toggle  
4. 💾 Auto-save and load last project state (.json file)  

---

## 🗓️ v0.16 — Company Moves & Shooting Day Structure

**Goal:** Represent physical movement and day divisions.  

**Features:**
1. 🚚 Company Move Rows  
   - Auto-insert between locations  
   - Configurable durations, distinct color (gray)  
2. 📆 Multi-Day Breakdown  
   - Split script into days by page count or location  
   - Each day has its own lunch, total, and wrap summary  
3. 🧮 Running Day Clock  
   - Display time-of-day for each scene based on cumulative duration  

---

## 🗓️ v0.17 — Exporting & Reporting

**Goal:** Produce professional-grade outputs.  

**Features:**
1. 🧾 Enhanced PDF layout with header/footer and logo  
2. 📊 Summary Report  
   - Page totals, INT/EXT ratios, setups per day  
3. 📤 Excel (.xlsx) export with preserved colors and merged cells  

---

## 🗓️ v0.18 — Themes & Customization

**Goal:** Align with industry visual standards.  

**Features:**
1. 🎨 Industry Color Themes  
   - Orange = Lunch, Green = Totals, Blue = Wrap, Gray = Moves  
   - Custom palette selector  
2. 🧱 Column Reordering and Visibility Toggles  
3. 🖥 Persistent UI Layout  
   - Save window size, column widths, and scroll position  

---

## 🗓️ v0.19 — Distribution & Command-Line Tools

**Goal:** Package for use by others.  

**Features:**
1. 🪄 PyInstaller builds (.exe / .app)  
2. 🧰 CLI Mode  
   - e.g., `python producers_toolkit.py script.fountain --export pdf`  
3. 🧪 Regression Testing  
   - Automated output comparison to prevent logic regressions  

---

## 🗓️ v0.20 — Intelligence & Collaboration

**Goal:** Smart automation and optional shared tools.  

**Features:**
1. 🧠 Auto-Setup Estimation  
   - Detect INT/EXT, DAY/NIGHT, and guess setups  
2. 💬 Scene Notes System  
   - Add comments or notes per scene  
3. 🌐 Optional Cloud Sync  
   - Sync JSON project data for teams (local-first design)  

---

## 🧩 Development Philosophy

- Keep everything **in one file** until v0.17, then modularize into:  
  - `ui.py` (interface)  
  - `logic.py` (core calculations)  
  - `export.py` (PDF/CSV/Excel output)  
- Prioritize **stability** and **clarity** before adding complexity.  
- Maintain **cross-platform parity**.  
- Increment version only when logic changes (visual tweaks = minor rev).  

---

**Next Active Version:** v0.15  
**Next Tasks:**  
- Add adjustable *Words per Page* (WPP) input field  
- Auto-recalculate scene lengths when changed  
- Preserve all current stable functionality  

---
