#!/usr/bin/env python3
"""Button-first fitness kiosk for a portrait Raspberry Pi display."""
import json
import logging
import os
import random
import signal
import subprocess
import sys
import time
import socket
import urllib.parse
import urllib.request
from pathlib import Path

from PyQt5.QtCore import QEvent, QObject, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QFont, QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

APP_DIR = Path(__file__).resolve().parent
STATE_FILE = APP_DIR / "state.json"
CONFIG_FILE = APP_DIR / "config.json"
LOG_FILE = APP_DIR / "fitness-app.log"
logging.basicConfig(filename=str(LOG_FILE), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

THEME = """
QWidget { background: #0b1015; color: #f4f7f8; font-family: DejaVu Sans; }
QLabel#eyebrow { color: #8aa0ad; font-size: 20px; font-weight: 700; letter-spacing: 2px; }
QLabel#title { font-size: 50px; font-weight: 800; }
QLabel#subtitle { color: #a8b8c2; font-size: 23px; }
QFrame#card { background: #141d24; border: 2px solid #263943; border-radius: 22px; }
QFrame#card[selected="true"] { background: #17393d; border: 4px solid #42e8b6; }
QLabel#cardTitle { font-size: 34px; font-weight: 800; background: transparent; }
QLabel#cardDetail { color: #9bb1bc; font-size: 20px; background: transparent; }
QPushButton { background: #17232b; border: 2px solid #31434f; border-radius: 14px; padding: 16px 22px; font-size: 23px; font-weight: 700; }
QPushButton:focus { background: #17393d; border: 3px solid #42e8b6; }
QLabel#hint { color: #91a4ae; font-size: 19px; }
QLabel#empty { color: #91a4ae; font-size: 27px; }
"""


def load_config():
    defaults = json.loads((APP_DIR / "config.example.json").read_text())
    if CONFIG_FILE.exists():
        defaults.update(json.loads(CONFIG_FILE.read_text()))
    return defaults


def pace_rows():
    rows = []
    for seconds in range(180, 421, 10):
        kmh = 3600 / seconds
        rows.append((f"{seconds // 60}:{seconds % 60:02d}", f"{kmh:.2f}"))
    return rows


class ButtonSignals(QObject):
    up = pyqtSignal()
    down = pyqtSignal()
    select = pyqtSignal()


class GPIOButtons:
    """GPIO17=Up, GPIO27=Down, GPIO22=Select. Buttons connect each pin to GND."""
    def __init__(self, signals):
        self.buttons = []
        try:
            from gpiozero import Button
            from gpiozero.pins.lgpio import LGPIOFactory
            factory = LGPIOFactory()
            for pin, callback in ((17, signals.up.emit), (27, signals.down.emit), (22, signals.select.emit)):
                button = Button(pin, pull_up=True, bounce_time=0.07, pin_factory=factory)
                button.when_pressed = callback
                self.buttons.append(button)
        except Exception as exc:
            logging.warning("GPIO disabled: %s", exc)

    def close(self):
        for button in self.buttons:
            button.close()


class SelectableCard(QFrame):
    def __init__(self, title, detail=""):
        super().__init__()
        self.setObjectName("card")
        self.setProperty("selected", False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        title_label = QLabel(title); title_label.setObjectName("cardTitle"); title_label.setWordWrap(True)
        layout.addWidget(title_label)
        if detail:
            detail_label = QLabel(detail); detail_label.setObjectName("cardDetail"); detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self); self.style().polish(self)


class ButtonItem:
    """Lets a real QPushButton participate in the GPIO selection ring."""
    def __init__(self, button): self.button = button
    def set_selected(self, selected):
        if selected: self.button.setFocus(Qt.OtherFocusReason)
        else: self.button.clearFocus()


class Kiosk(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.state = self.read_state()
        self.index = 0
        self.items = []
        self.last_video = None
        self.last_video_needs_choice = False
        self.video_order_initialized = False
        self.mpv = None
        self.mpv_socket = "/tmp/fitness-mpv.sock"
        self.brave = None
        self.browser_mode = False
        self.cursor_timer = QTimer(self); self.cursor_timer.setSingleShot(True)
        self.cursor_timer.timeout.connect(lambda: self.setCursor(Qt.BlankCursor))
        self.setWindowTitle("Fitness")
        self.setStyleSheet(THEME)
        self.pages = QStackedWidget(); self.setCentralWidget(self.pages)
        self.home = self.make_home(); self.pages.addWidget(self.home)
        self.signals = ButtonSignals()
        self.signals.up.connect(self.on_up); self.signals.down.connect(self.on_down); self.signals.select.connect(self.on_select)
        self.gpio = GPIOButtons(self.signals)
        self.setMouseTracking(True)
        self.home_view()

    def read_state(self):
        try: return json.loads(STATE_FILE.read_text())
        except Exception: return {"positions": {}}

    def save_state(self):
        STATE_FILE.write_text(json.dumps(self.state))

    def event(self, event):
        if event.type() == QEvent.MouseMove:
            self.unsetCursor(); self.cursor_timer.start(1800)
        return super().event(event)

    def make_page(self, eyebrow, title, subtitle=""):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(82, 68, 82, 54); layout.setSpacing(18)
        e = QLabel(eyebrow); e.setObjectName("eyebrow"); layout.addWidget(e)
        t = QLabel(title); t.setObjectName("title"); layout.addWidget(t)
        if subtitle:
            s = QLabel(subtitle); s.setObjectName("subtitle"); s.setWordWrap(True); layout.addWidget(s)
        return page, layout

    def make_home(self):
        page, layout = self.make_page("FITNESS STATION", "READY WHEN YOU ARE", "Use the three physical buttons to choose a section.")
        self.home_cards = []
        for title, detail in (("Fitness Videos", "Your offline workout library"), ("Strength Training", "Live maximum-weight overview"), ("YouTube Music", "Workout music in Brave"), ("Pace / KMH", "Running pace conversion"), ("System", "Restart, power, or return to desktop")):
            card = SelectableCard(title, detail); layout.addWidget(card); self.home_cards.append(card)
        layout.addStretch()
        hint = QLabel("UP / DOWN  Navigate     •     SELECT  Open"); hint.setObjectName("hint"); hint.setAlignment(Qt.AlignCenter); layout.addWidget(hint)
        return page

    def set_items(self, items):
        self.items = items; self.index = 0; self.paint_selection()

    def paint_selection(self):
        for position, item in enumerate(self.items): item.set_selected(position == self.index)
        if getattr(self, "scroll_area", None) and self.current_view == "videos" and self.index < len(self.video_cards):
            self.scroll_area.ensureWidgetVisible(self.video_cards[self.index], 0, 90)

    def home_view(self):
        self.browser_mode = False
        self.current_view = "home"
        self.pages.setCurrentWidget(self.home)
        self.set_items(self.home_cards)

    def add_home_button(self, layout):
        layout.addStretch()
        row = QHBoxLayout(); row.addStretch()
        button = QPushButton("Home"); button.setFixedWidth(175); row.addWidget(button)
        layout.addLayout(row)
        return button

    def video_view(self, focus_last=False):
        self.current_view = "videos"
        page, layout = self.make_page("OFFLINE LIBRARY", "FITNESS VIDEOS", "Select a video to play. The order changes on each app launch.")
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget(); videos_layout = QVBoxLayout(content); videos_layout.setSpacing(14)
        directory = Path(self.cfg["video_directory"])
        available = {p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".mp4"} if directory.is_dir() else set()
        # Preserve this session's order, but pick up shared-folder uploads on return.
        existing = self.videos if self.video_order_initialized else []
        self.videos = [p for p in existing if p in available]
        added = sorted(available.difference(self.videos))
        random.shuffle(added)
        self.videos.extend(added)
        self.video_order_initialized = True
        self.video_cards = []
        if not self.videos:
            empty = QLabel(f"No MP4 files found in\n{directory}"); empty.setObjectName("empty"); empty.setAlignment(Qt.AlignCenter); videos_layout.addWidget(empty)
        for video in self.videos:
            card = SelectableCard(video.stem, "MP4 video"); videos_layout.addWidget(card); self.video_cards.append(card)
        videos_layout.addStretch(); scroll.setWidget(content); layout.addWidget(scroll, 1)
        self.scroll_area = scroll
        self.video_home = self.add_home_button(layout)
        self.pages.addWidget(page); self.pages.setCurrentWidget(page)
        self.set_items(self.video_cards + [self.wrap_button(self.video_home)])
        if focus_last and self.last_video in self.videos:
            self.index = self.videos.index(self.last_video)
            self.paint_selection()

    def wrap_button(self, button):
        return ButtonItem(button)

    def strength_view(self):
        self.current_view = "strength"
        page, layout = self.make_page("LIVE FROM GOOGLE SHEETS", "STRENGTH TRAINING", "Maximum weights • refreshed every 5 seconds")
        self.strength_content = QVBoxLayout(); layout.addLayout(self.strength_content, 1)
        self.strength_home = self.add_home_button(layout); self.pages.addWidget(page); self.pages.setCurrentWidget(page)
        self.set_items([self.wrap_button(self.strength_home)])
        self.refresh_strength()
        self.strength_timer = QTimer(page); self.strength_timer.timeout.connect(self.refresh_strength); self.strength_timer.start(self.cfg["sheets"].get("refresh_seconds", 5) * 1000)

    def refresh_strength(self):
        while self.strength_content.count():
            child = self.strength_content.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
            settings = self.cfg["sheets"]
            credentials = APP_DIR / settings.get("credentials_file", "credentials.json")
            creds = Credentials.from_service_account_file(str(credentials), scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
            service = build("sheets", "v4", credentials=creds, cache_discovery=False)
            rows = service.spreadsheets().values().get(spreadsheetId=settings["spreadsheet_id"], range=settings["range"]).execute().get("values", [])
            active = [i for i, v in enumerate(rows[0])] if rows else []
            grid = QGridLayout(); grid.setSpacing(3)
            for r, row in enumerate(rows):
                for c, source in enumerate(active):
                    value = row[source] if source < len(row) else ""
                    label = QLabel(value); label.setAlignment(Qt.AlignCenter); label.setWordWrap(True)
                    label.setStyleSheet("background: #17232b; border: 1px solid #36515c; padding: 9px; font-size: %dpx; font-weight: %s;" % (25 if r == 0 else 22, "800" if r == 0 else "500"))
                    grid.addWidget(label, r, c)
            holder = QWidget(); holder.setLayout(grid); self.strength_content.addWidget(holder)
        except Exception as exc:
            logging.exception("Sheets refresh failed")
            label = QLabel("Could not update strength data.\nCheck Wi-Fi, credentials.json, and Sheet sharing."); label.setObjectName("empty"); label.setAlignment(Qt.AlignCenter); self.strength_content.addWidget(label)

    def pace_view(self):
        self.current_view = "pace"
        page, layout = self.make_page("RUNNING REFERENCE", "PACE / KMH", "Minutes per kilometre to kilometres per hour")
        grid = QGridLayout(); grid.setHorizontalSpacing(5); grid.setVerticalSpacing(5)
        for i, (pace, kmh) in enumerate(pace_rows()):
            r, c = divmod(i, 2)
            label = QLabel(f"{pace} min/km     {kmh} km/h"); label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("background:#17232b; border:1px solid #36515c; border-radius:10px; padding:13px; font-size:25px; font-weight:700;")
            grid.addWidget(label, r, c)
        layout.addLayout(grid, 1); home = self.add_home_button(layout); self.pages.addWidget(page); self.pages.setCurrentWidget(page); self.set_items([self.wrap_button(home)])

    def system_view(self):
        self.current_view = "system"
        page, layout = self.make_page("SYSTEM", "SYSTEM CONTROLS", "Select an option. A confirmation is always required.")
        self.system_actions = [("Restart App", self.restart_app), ("Reboot Pi", lambda: self.confirm("Reboot Raspberry Pi?", ["Cancel", "Reboot"], "reboot")), ("Shut Down Pi", lambda: self.confirm("Shut down Raspberry Pi?", ["Cancel", "Shut Down"], "shutdown")), ("Close App", lambda: self.confirm("Return to the Raspberry Pi desktop?", ["Cancel", "Close App"], "close"))]
        cards=[]
        for name, _ in self.system_actions: card=SelectableCard(name); layout.addWidget(card); cards.append(card)
        home=self.add_home_button(layout); self.pages.addWidget(page); self.pages.setCurrentWidget(page); self.set_items(cards+[self.wrap_button(home)])

    def confirm(self, prompt, choices, command):
        self.current_view = "confirm"
        page, layout = self.make_page("CONFIRM ACTION", prompt, "Use Up / Down to choose, then Select.")
        actions=[]; cards=[]
        for choice in choices:
            card=SelectableCard(choice); layout.addWidget(card); cards.append(card)
            actions.append(self.home_view if choice == "Cancel" else lambda c=command: self.run_command(c))
        self.confirm_actions=actions; self.pages.addWidget(page); self.pages.setCurrentWidget(page); self.set_items(cards)

    def run_command(self, command):
        if command == "close": self.close()
        elif command == "reboot": subprocess.Popen(["sudo", "/usr/bin/systemctl", "reboot"])
        elif command == "shutdown": subprocess.Popen(["sudo", "/usr/bin/systemctl", "poweroff"])

    def restart_app(self):
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def youtube_view(self):
        term = random.choice(self.cfg["youtube"]["search_terms"])
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(term)
        opts = self.cfg["youtube"]
        command = [opts.get("brave_binary", "brave-browser"), "--kiosk", f"--remote-debugging-port={opts.get('debugging_port', 9222)}", "--remote-allow-origins=*", f"--user-data-dir={opts.get('brave_profile')}", url]
        self.brave = subprocess.Popen(command)
        self.browser_mode = True
        self.hide()
        QTimer.singleShot(6000, self.install_youtube_navigation)

    def browser_eval(self, source):
        try:
            port = self.cfg["youtube"].get("debugging_port", 9222)
            tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1).read())
            tab = next(t for t in tabs if t.get("type") == "page" and "youtube" in t.get("url", ""))
            import websocket
            ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=2, origin="http://localhost")
            ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": source}})); ws.close()
        except Exception as exc: logging.warning("Brave control unavailable: %s", exc)

    def install_youtube_navigation(self):
        self.browser_eval("""(() => { if(window.__fitnessNav)return; window.__fitnessNav=1; let i=0; const cards=()=>[...document.querySelectorAll('a#video-title')].filter(x=>x.offsetParent); const mark=()=>cards().forEach((x,n)=>{x.style.outline=n===i?'5px solid #42e8b6':'';x.style.outlineOffset='5px'}); document.addEventListener('keydown',e=>{const p=location.pathname.includes('/watch'); if(p){if(e.key==='Enter'||e.key===' '){e.preventDefault();document.querySelector('video')?.click()}else if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();history.back()}return} if(e.key==='ArrowDown'){e.preventDefault();i=Math.min(i+1,cards().length-1);mark()} if(e.key==='ArrowUp'){e.preventDefault();i=Math.max(i-1,0);mark()} if(e.key==='Enter'){e.preventDefault();cards()[i]?.click()}}); mark() })()""")

    def browser_key(self, key):
        self.browser_eval("document.dispatchEvent(new KeyboardEvent('keydown',{key:'%s',bubbles:true}));" % key)

    def play_video(self, video, resume=False):
        position = self.state["positions"].get(str(video), 0) if resume else 0
        self.last_video = video
        self.last_video_needs_choice = False
        self.video_interrupted = False
        self.hide()
        try: os.unlink(self.mpv_socket)
        except FileNotFoundError: pass
        self.mpv = subprocess.Popen(["mpv", "--fs", "--keep-open=no", "--save-position-on-quit=no", "--osd-level=1", f"--input-ipc-server={self.mpv_socket}", f"--start={position}", str(video)])
        QTimer.singleShot(400, self.watch_mpv)

    def mpv_command(self, command):
        """Send one JSON IPC command to mpv and return its JSON response."""
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(0.35); client.connect(self.mpv_socket)
            client.sendall((json.dumps({"command": command}) + "\n").encode())
            response = json.loads(client.recv(4096).decode()); client.close()
            return response
        except Exception as exc:
            logging.debug("mpv IPC unavailable: %s", exc)
            return {}

    def stop_video(self):
        if not self.mpv or self.mpv.poll() is not None: return
        response = self.mpv_command(["get_property", "time-pos"])
        position = response.get("data")
        if isinstance(position, (float, int)):
            self.state["positions"][str(self.last_video)] = round(position, 1)
            self.save_state()
        self.video_interrupted = True
        self.last_video_needs_choice = True
        self.mpv.terminate()

    def watch_mpv(self):
        if self.mpv and self.mpv.poll() is None: QTimer.singleShot(500, self.watch_mpv)
        else:
            # A natural end must replay from the beginning, not offer a stale resume point.
            if self.last_video and not self.video_interrupted:
                self.state["positions"][str(self.last_video)] = 0
                self.save_state()
            self.showFullScreen(); self.video_view(focus_last=True)

    def video_return_menu(self):
        # Only the immediately previous video receives these choices during this session.
        page, layout = self.make_page("VIDEO PAUSED OR FINISHED", self.last_video.stem, "What would you like to do?")
        self.current_view = "video_return"
        saved = self.state["positions"].get(str(self.last_video), 0)
        actions = []
        if self.video_interrupted and saved > 0:
            actions.append(("Resume", lambda: self.play_video(self.last_video, True)))
        actions.extend([("Restart", lambda: self.play_video(self.last_video, False)), ("Back to videos", lambda: self.video_view(focus_last=True))])
        cards=[]; self.return_actions=[]
        for name, action in actions: card=SelectableCard(name); layout.addWidget(card); cards.append(card); self.return_actions.append(action)
        self.pages.addWidget(page); self.pages.setCurrentWidget(page); self.set_items(cards)

    def on_up(self):
        if self.mpv and self.mpv.poll() is None:
            self.stop_video(); return
        if self.browser_mode: self.browser_key("ArrowUp"); return
        self.index = (self.index - 1) % len(self.items) if self.items else 0; self.paint_selection()

    def on_down(self):
        if self.mpv and self.mpv.poll() is None:
            self.stop_video(); return
        if self.browser_mode: self.browser_key("ArrowDown"); return
        self.index = (self.index + 1) % len(self.items) if self.items else 0; self.paint_selection()

    def on_select(self):
        if self.mpv and self.mpv.poll() is None:
            self.mpv_command(["cycle", "pause"]); return
        if self.browser_mode: self.browser_key("Enter"); return
        if self.current_view == "home":
            (self.video_view, self.strength_view, self.youtube_view, self.pace_view, self.system_view)[self.index]()
        elif self.current_view == "video_return":
            self.return_actions[self.index]()
        elif self.current_view == "confirm":
            self.confirm_actions[self.index]()
        elif self.current_view in ("strength", "pace"):
            self.home_view()
        elif self.current_view == "system":
            if self.index == len(self.system_actions):
                self.home_view(); return
            self.system_actions[self.index][1]()
        elif self.current_view == "videos":
            if self.index == len(self.video_cards):
                self.home_view()
            elif self.videos:
                video = self.videos[self.index]
                if video == self.last_video and self.last_video_needs_choice:
                    self.video_return_menu()
                else:
                    self.play_video(video)

    def closeEvent(self, event):
        self.gpio.close()
        if self.brave and self.brave.poll() is None: self.brave.terminate()
        if self.mpv and self.mpv.poll() is None: self.mpv.terminate()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOverrideCursor(QCursor(Qt.BlankCursor))
    window = Kiosk(); window.showFullScreen()
    sys.exit(app.exec_())
