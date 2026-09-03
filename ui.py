import sys, os, logging, subprocess
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
from subprocess import DEVNULL
from gpiozero import Button
from gpiozero.pins.lgpio import LGPIOFactory

# ---- Logging ----
logging.basicConfig(filename='/home/Stefan/FitnessUI/ui.log',
                    level=logging.INFO, format='[%(asctime)s] %(message)s')

# ---- GPIO (Pi 5) ----
BUTTON_PIN = 17

class ButtonSignal(QObject):
    pressed = pyqtSignal()

btn_signal = ButtonSignal()

# Pi 5-friendly button (pull-up)
_factory = LGPIOFactory()
_hw_button = Button(BUTTON_PIN, pull_up=True, pin_factory=_factory)

# Emit Qt signal on press
_hw_button.when_pressed = lambda: btn_signal.pressed.emit()

def fan_boost():
    subprocess.Popen(["sudo", "/usr/local/bin/fan_boost.sh"],
                     stdout=DEVNULL, stderr=DEVNULL)

def wake_display():
    """
    Wake the screen under Wayland or X11. Tries several non-blocking nops.
    """
    try:
        # Wayland path (Pi 5 desktop default). Output name is usually XWAYLAND0.
        if os.environ.get("WAYLAND_DISPLAY"):
            subprocess.run(
                ["wlr-randr", "--output", "XWAYLAND0", "--on"],
                stdout=DEVNULL, stderr=DEVNULL, check=False
            )
        else:
            # X11 path
            subprocess.run(
                ["xset", "-display", ":0", "dpms", "force", "on"],
                stdout=DEVNULL, stderr=DEVNULL, check=False
            )
            subprocess.run(
                ["xset", "-display", ":0", "s", "reset"],
                stdout=DEVNULL, stderr=DEVNULL, check=False
            )
        # Extra nudge (works on many setups even with KMS)
        subprocess.run(
            ["/usr/bin/vcgencmd", "display_power", "1"],
            stdout=DEVNULL, stderr=DEVNULL, check=False
        )
    except Exception:
        # Don’t crash UI if waking fails
        pass

# Hook the button to wake the display (or chain your own handler)
# btn_signal.pressed.connect(wake_display)
btn_signal.pressed.connect(lambda: (wake_display(), fan_boost()))

# Cleanup on exit
def _cleanup_gpio():
    try:
        _hw_button.close()
    except Exception:
        pass

# ---- Google Sheets Setup ----
SHEET_ID = '1HYfVOL1ksEItPQ0E-o9ck3Y-vkFe9AY29xZbqzlWihs'
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
sheet = build('sheets', 'v4', credentials=creds).spreadsheets()

# ---- UI ----
app = QApplication(sys.argv)
window = QWidget()
window.setStyleSheet("background-color: white;")
app.aboutToQuit.connect(_cleanup_gpio)

main_layout = QVBoxLayout()
main_layout.setContentsMargins(80, 80, 80, 60)
main_layout.setSpacing(20)
window.setLayout(main_layout)

table_top = QTableWidget()
table_bot = QTableWidget()
for t in (table_top, table_bot):
    t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setVisible(False)
    t.setShowGrid(True)
    t.setStyleSheet("QTableWidget { gridline-color: black; border: 1px solid black; }")
    t.setFrameStyle(0)

main_layout.addSpacing(0)   # adjust if you want fixed top padding
main_layout.addWidget(table_top, stretch=1)
main_layout.addWidget(table_bot, stretch=1)

# ---- Constants ----
ROW_HEIGHT = 30
COL_WIDTH_FIRST_TOP = 80
COL_WIDTH_OTHERS_TOP = 80
COL_WIDTH_FIRST_BOT = 180
COL_WIDTH_OTHERS_BOT = 50
FONT_NORMAL = QFont("Arial", 12)
FONT_HEADER = QFont("Arial", 14); FONT_HEADER.setBold(True)

def _filter_active_columns(rows):
    if not rows:
        return [], []
    first = rows[0]
    active_cols = [i for i, v in enumerate(first) if str(v).strip()]
    values = []
    for r in rows:
        r_ext = r + [""] * ( (max(active_cols) + 1) - len(r) )
        values.append([r_ext[i] for i in active_cols])
    return values, active_cols

def _render_table(widget, values, col0w, colw):
    row_count = len(values)
    col_count = len(values[0]) if values else 0
    widget.setRowCount(row_count)
    widget.setColumnCount(col_count)
    for c in range(col_count):
        widget.setColumnWidth(c, col0w if c == 0 else colw)
    for r in range(row_count):
        widget.setRowHeight(r, ROW_HEIGHT)
        for c in range(col_count):
            txt = values[r][c] if c < len(values[r]) else ""
            it = QTableWidgetItem(txt)
            it.setTextAlignment(Qt.AlignCenter)
            it.setFont(FONT_HEADER if r == 0 else FONT_NORMAL)
            widget.setItem(r, c, it)
    total_w = sum(col0w if c == 0 else colw for c in range(col_count))
    total_h = row_count * ROW_HEIGHT
    widget.setFixedSize(total_w, total_h)

def refresh_table():
    try:
        r1 = sheet.values().get(spreadsheetId=SHEET_ID, range='Sheet1!A1:Z100').execute()
        rows1 = r1.get('values', [])
        v1, _ = _filter_active_columns(rows1)

        r2 = sheet.values().get(spreadsheetId=SHEET_ID, range='Sheet2!A1:Z100').execute()
        rows2 = r2.get('values', [])
        v2, _ = _filter_active_columns(rows2)

        _render_table(table_top, v2, COL_WIDTH_FIRST_TOP, COL_WIDTH_OTHERS_TOP)  # upper third: Sheet2
        _render_table(table_bot, v1, COL_WIDTH_FIRST_BOT, COL_WIDTH_OTHERS_BOT)  # lower third: Sheet1
    except Exception as e:
        logging.info(f"refresh_table error: {e}")

# ---- Start ----
refresh_table()
timer = QTimer(); timer.timeout.connect(refresh_table); timer.start(30000)

window.showFullScreen()
sys.exit(app.exec_())