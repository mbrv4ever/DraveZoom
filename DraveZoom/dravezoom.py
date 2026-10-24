#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DraveZoom - schermvergrootglas. Vergroot het stuk scherm rond je muis,
met filters (grijswaarden, kleuren omkeren, hoog contrast) voor wie slecht ziet.
Dravenlock-huisstijl. Lokaal, offline, toegankelijk.
"""
import os
import sys
import json

from PyQt6.QtCore import Qt, QTimer, QLocale, QUrl, QPoint, QEvent, pyqtSignal
from PyQt6.QtGui import (QPixmap, QImage, QIcon, QDesktopServices, QCursor,
                         QKeySequence, QShortcut, QAction, QPainter, QColor, QPen)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QComboBox, QFrame, QMessageBox, QDialog, QToolButton,
    QStatusBar, QPlainTextEdit, QSystemTrayIcon, QMenu)

APP_NAME = "DraveZoom"
APP_VERSION = "0.16.2"
DONATE_URL = "https://paypal.me/roger076"
SUPPORT_MAIL = "service@dravenlock.nl"

BG = "#0e0e11"
PANEL = "#16161b"
SILVER = "#d4d4d4"
MUTE = "#8a8a94"
ACCENT = "#6fa3d6"

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 1.0, 10.0, 0.5
FILTERS = [("Geen", "geen"), ("Grijswaarden", "grijs"),
           ("Kleuren omkeren", "omkeren"), ("Hoog contrast", "contrast")]
LENS_SIZES = [("Klein", 380, 280), ("Middel", 560, 410), ("Groot", 780, 560)]


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _config_path():
    return os.path.join(_app_dir(), "dravezoom_config.json")


DEFAULT_CONFIG = {"lang": "", "zoom": 2.0, "filter": "geen",
                  "smooth": True, "follow": True, "ontop": True,
                  "lens": False, "lenssize": 1}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Taal
# ---------------------------------------------------------------------------
_LANG = "nl"

TRANSLATIONS = {
    "en": {
        "Instellingen\u2026": "Settings\u2026", "Snelgids": "Quick guide",
        "Over": "About", "Sluiten": "Close", "Taal:": "Language:",
        "Automatisch (OS)": "Automatic (OS)", "Nederlands": "Dutch",
        "Engels": "English", "Donatie": "Donate",
        "Sommige instellingen gaan pas in na herstarten.":
            "Some settings apply after a restart.",
        "Inzoomen": "Zoom in", "Uitzoomen": "Zoom out",
        "Volg muis": "Follow mouse", "Bevriezen": "Freeze",
        "Filter:": "Filter:", "Geen": "None", "Grijswaarden": "Grayscale",
        "Kleuren omkeren": "Invert colors", "Hoog contrast": "High contrast",
        "Vloeiend": "Smooth", "Altijd bovenop": "Always on top",
        "Verbergen": "Hide", "Tonen": "Show", "Afsluiten": "Quit",
        "Zwevend": "Floating", "Grootte:": "Size:",
        "Volledig scherm": "Full screen",
        "Hele scherm vergroten; scroll = zoom, Esc = stoppen":
            "Magnify the whole screen; scroll = zoom, Esc = exit",
        "Klein": "Small", "Middel": "Medium", "Groot": "Large",
        "Het zwevende vergrootglas volgt je muis.":
            "The floating magnifier follows your mouse.",
        "DraveZoom draait nog in het systeemvak. Klik op het icoon om terug te keren.":
            "DraveZoom is still running in the tray. Click the icon to return.",
        "Beweeg je muis over wat je wilt vergroten.":
            "Move your mouse over what you want to magnify.",
        "Bevroren": "Frozen",
        "snelgids_titel": "DraveZoom - quick guide",
    }
}


def detect_lang(cfg):
    forced = (cfg.get("lang") or "").strip().lower()
    if forced in ("nl", "en"):
        return forced
    try:
        if QLocale.system().name().lower().startswith("nl"):
            return "nl"
        return "en"
    except Exception:
        return "nl"


def t(s, lang=None):
    lg = lang or _LANG
    if lg == "nl":
        return s
    return TRANSLATIONS.get(lg, {}).get(s, s)


def filter_label(code, lang):
    for nl, c in FILTERS:
        if c == code:
            return t(nl, lang)
    return code


# ---------------------------------------------------------------------------
# Logo
# ---------------------------------------------------------------------------
def _logo_path():
    dirs = [_app_dir()]
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        dirs.append(mp)
    dirs.append(os.path.join(_app_dir(), "_internal"))
    for d in dirs:
        for name in ("logo.ico", "logo.png"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    return None


def app_icon():
    p = _logo_path()
    if p:
        ic = QIcon(p)
        if not ic.isNull():
            return ic
    return QIcon()


def logo_pixmap(size=30):
    p = _logo_path()
    if p:
        pm = QPixmap(p)
        if not pm.isNull():
            return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
    return QPixmap()


# ---------------------------------------------------------------------------
# Beeldfilters
# ---------------------------------------------------------------------------
def _contrast_lut(factor=1.8):
    out = bytearray(256)
    for i in range(256):
        v = int((i - 128) * factor + 128)
        out[i] = 0 if v < 0 else (255 if v > 255 else v)
    return bytes(out)


_CONTRAST_TABLE = _contrast_lut()


def apply_filter(img, mode):
    if mode == "grijs":
        return img.convertToFormat(QImage.Format.Format_Grayscale8)
    if mode == "omkeren":
        im = img.convertToFormat(QImage.Format.Format_RGB32)
        im.invertPixels()
        return im
    if mode == "contrast":
        g = img.convertToFormat(QImage.Format.Format_Grayscale8)
        ptr = g.bits()
        ptr.setsize(g.sizeInBytes())
        buf = bytes(ptr)
        g2 = QImage(buf.translate(_CONTRAST_TABLE), g.width(), g.height(),
                    g.bytesPerLine(), QImage.Format.Format_Grayscale8)
        return g2.copy()
    return img


def render_zoom(src_img, target_w, target_h, smooth, mode):
    f = apply_filter(src_img, mode)
    tm = (Qt.TransformationMode.SmoothTransformation if smooth
          else Qt.TransformationMode.FastTransformation)
    return f.scaled(max(1, target_w), max(1, target_h),
                    Qt.AspectRatioMode.IgnoreAspectRatio, tm)


# ---------------------------------------------------------------------------
# Snelgids / Instellingen
# ---------------------------------------------------------------------------
GUIDE_NL = """DraveZoom - Snelgids

DraveZoom is een vergrootglas voor je scherm. Het toont het gebied rond je
muis vergroot, zodat kleine knopjes of tekst goed leesbaar worden.

Aan de slag
- Laat dit venster ergens op een rustige plek staan en beweeg je muis over
  wat je wilt vergroten (bijv. een tekst of een knop in een ander venster).
- Inzoomen / Uitzoomen met de knoppen, met + en - op je toetsenbord, of
  met het muiswiel op het DraveZoom-venster.
- Tip: Ctrl + +  en  Ctrl + -  zoomen vanuit ELK programma (ook als DraveZoom
  niet vooraan staat). Zo zoom je terwijl je met het lensje ergens anders werkt.
- 'Volg muis' aan: het volgt je muis. Uit: het beeld staat stil.
- 'Bevriezen' (of de F-toets) zet het beeld vast, handig om rustig te kijken.

Filters (voor minder goed zien)
- Grijswaarden: alles in grijstinten.
- Kleuren omkeren: licht wordt donker (vaak prettiger lezen).
- Hoog contrast: maakt het verschil tussen licht en donker sterker.
- 'Vloeiend' maakt het vergrote beeld zachter; uit = scherpere blokjes.

Zwevend vergrootglas (het handigst)
- Klik 'Zwevend' voor een klein los vergrootglas dat je muis volgt. Kies de
  Grootte (Klein/Middel/Groot). Zo zie je vergroot wat onder je muis zit,
  zonder dat een groot venster in de weg zit.
- Klik 'Verbergen' (of minimaliseer) om het bedieningsvenster naar het
  systeemvak te sturen; dan blijft ALLEEN het zwevende vergrootglas over.
  Klik op het draak-icoontje in het systeemvak om het venster terug te halen.
- Op recente Windows (10/11) vergroot DraveZoom zichzelf niet meer.

Volledig scherm (hele bureaublad vergroten)
- Klik 'Volledig scherm' om het HELE scherm te vergroten, zonder los venstertje.
  Het beeld volgt je muis en je zoomt met het muiswiel (of + / -).
- Dit is een LEESmodus: zolang hij aan staat kijk je vergroot rond. Druk op Esc
  om eruit te gaan en weer gewoon te klikken/typen.
- Een klein kruisje laat zien waar je muis precies staat.

Vragen of een tip? service@dravenlock.nl
"""

GUIDE_EN = """DraveZoom - Quick guide

DraveZoom is a magnifier for your screen. It shows the area around your
mouse enlarged, so small buttons or text become readable.

Getting started
- Leave this window somewhere out of the way and move your mouse over what
  you want to magnify (e.g. text or a button in another window).
- Zoom in / out with the buttons, with + and - on your keyboard, or with
  the mouse wheel over the DraveZoom window.
- Tip: Ctrl + +  and  Ctrl + -  zoom from ANY program (even when DraveZoom is
  not in front), so you can zoom while working elsewhere with the lens.
- 'Follow mouse' on: it follows your mouse. Off: the image stays still.
- 'Freeze' (or the F key) locks the image, handy for a calm look.

Filters (for low vision)
- Grayscale: everything in shades of gray.
- Invert colors: light becomes dark (often easier to read).
- High contrast: strengthens the difference between light and dark.
- 'Smooth' softens the enlarged image; off = sharper blocks.

Floating magnifier (most handy)
- Click 'Floating' for a small separate magnifier that follows your mouse.
  Pick the Size (Small/Medium/Large). You see what is under your mouse
  enlarged, without a big window getting in the way.
- Click 'Hide' (or minimize) to send the control window to the system tray;
  then ONLY the floating magnifier remains. Click the dragon icon in the
  tray to bring the window back.
- On recent Windows (10/11) DraveZoom no longer magnifies itself.

Full screen (magnify the whole desktop)
- Click 'Full screen' to magnify the WHOLE screen, without a separate window.
  The view follows your mouse and you zoom with the mouse wheel (or + / -).
- This is a READ mode: while it is on you look around magnified. Press Esc to
  exit and click/type normally again.
- A small crosshair shows exactly where your mouse is.

Questions or feedback? service@dravenlock.nl
"""


class GuideDialog(QDialog):
    def __init__(self, parent, lang):
        super().__init__(parent)
        self.setWindowTitle(t("snelgids_titel", lang))
        self.setWindowIcon(app_icon())
        self.resize(560, 560)
        lay = QVBoxLayout(self)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setObjectName("guide")
        box.setPlainText(GUIDE_NL if lang == "nl" else GUIDE_EN)
        lay.addWidget(box)
        row = QHBoxLayout()
        donate = QPushButton("\u2665 " + t("Donatie", lang))
        donate.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DONATE_URL)))
        row.addWidget(donate)
        row.addStretch(1)
        close = QPushButton(t("Sluiten", lang))
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)


class SettingsDialog(QDialog):
    def __init__(self, parent, cfg, lang):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle(t("Instellingen\u2026", lang))
        self.setWindowIcon(app_icon())
        self.resize(360, 160)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(t("Taal:", lang)))
        self.langbox = QComboBox()
        self.langbox.addItem(t("Automatisch (OS)", lang), "")
        self.langbox.addItem(t("Nederlands", lang), "nl")
        self.langbox.addItem(t("Engels", lang), "en")
        self.langbox.setCurrentIndex(
            {"": 0, "nl": 1, "en": 2}.get(cfg.get("lang", ""), 0))
        lay.addWidget(self.langbox)
        hint = QLabel(t("Sommige instellingen gaan pas in na herstarten.", lang))
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton("OK")
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)

    def result_cfg(self):
        self.cfg["lang"] = self.langbox.currentData()
        return self.cfg


# ---------------------------------------------------------------------------
# Zwevend lens-venster (volgt de muis, randloos, altijd bovenop)
# ---------------------------------------------------------------------------
class LensWindow(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool
                            | Qt.WindowType.WindowTransparentForInput)
        self.setObjectName("lenswin")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        self.view = QLabel()
        self.view.setObjectName("lensview")
        self.view.setScaledContents(True)
        lay.addWidget(self.view)
        self._aff = False
        self.setFixedSize(560, 410)

    def showEvent(self, ev):
        self._apply_exclude()
        super().showEvent(ev)

    def _apply_exclude(self):
        if self._aff or not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), 0x11)
            self._aff = True
        except Exception:
            pass


class FullScreenZoom(QWidget):
    """Volledig-scherm vergroter (leesmodus): hele scherm vergroot, volgt de
    muis, scrollwiel zoomt, Esc sluit. Geen lensje, geen gat, geen zwart."""
    wheelZoom = pyqtSignal(int)       # +1 = inzoomen, -1 = uitzoomen
    exitRequested = pyqtSignal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setObjectName("fszoom")
        self.setStyleSheet("#fszoom{background:#000;}")
        self.setCursor(Qt.CursorShape.BlankCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QLabel()
        self.view.setObjectName("fsview")
        self.view.setScaledContents(True)
        lay.addWidget(self.view)
        self._aff = False

    def showEvent(self, ev):
        self._apply_exclude()
        super().showEvent(ev)

    def _apply_exclude(self):
        if self._aff or not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            ctypes.windll.user32.SetWindowDisplayAffinity(int(self.winId()), 0x11)
            self._aff = True
        except Exception:
            pass

    def wheelEvent(self, ev):
        d = ev.angleDelta().y()
        if d != 0:
            self.wheelZoom.emit(1 if d > 0 else -1)
        ev.accept()

    def keyPressEvent(self, ev):
        k = ev.key()
        if k == Qt.Key.Key_Escape:
            self.exitRequested.emit()
        elif k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.wheelZoom.emit(1)
        elif k == Qt.Key.Key_Minus:
            self.wheelZoom.emit(-1)
        else:
            super().keyPressEvent(ev)


# ---------------------------------------------------------------------------
# Hoofdvenster
# ---------------------------------------------------------------------------
class DraveZoom(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.lang = _LANG
        self.zoom = float(cfg.get("zoom", 2.0))
        self.filter = cfg.get("filter", "geen")
        self.smooth = bool(cfg.get("smooth", True))
        self.follow = bool(cfg.get("follow", True))
        self.frozen = False
        self._last_pt = QPoint(0, 0)
        self._affinity_done = False
        self._tray_hinted = False
        self._quitting = False
        self.lens = LensWindow()
        self.lens_on = False
        self.fs = FullScreenZoom()
        self.fs_on = False
        self.fs.wheelZoom.connect(self._wheel_zoom)
        self.fs.exitRequested.connect(lambda: self.b_fs.setChecked(False))

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(760, 460)
        if cfg.get("ontop", True):
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._header())
        outer.addWidget(self._toolbar())

        self.info = QLabel()
        self.info.setObjectName("infopanel")
        self.info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info.setWordWrap(True)
        self.info.setText(t(
            "Kies hoe je wilt vergroten:\n\n"
            "\u25ce  Zwevend  \u2014  een vergrootglas dat je muis volgt.\n"
            "Je kunt gewoon doorklikken en typen.\n\n"
            "\u2922  Volledig scherm  \u2014  het hele scherm vergroot.\n"
            "Scroll = zoom, de muis stuurt, Esc om te stoppen.\n\n"
            "Zoomen kan ook met  +  en  \u2212 ,  of overal met  Ctrl + +  /  Ctrl + \u2212.",
            self.lang))
        outer.addWidget(self.info, 1)

        sb = QStatusBar()
        self.setStatusBar(sb)
        self.zoom_lbl = QLabel("")
        self.zoom_lbl.setObjectName("muted")
        sb.addWidget(self.zoom_lbl)
        sb.addPermanentWidget(QLabel("v" + APP_VERSION))
        donate = QToolButton()
        donate.setText("\u2665 " + t("Donatie", self.lang))
        donate.setObjectName("donate")
        donate.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(DONATE_URL)))
        sb.addPermanentWidget(donate)

        # systeemvak (taakbalk-icoon)
        self.tray = None
        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                self.tray = QSystemTrayIcon(app_icon(), self)
                self.tray.setToolTip(APP_NAME)
                menu = QMenu()
                act_show = QAction(t("Tonen", self.lang), self)
                act_show.triggered.connect(self._restore)
                act_quit = QAction(t("Afsluiten", self.lang), self)
                act_quit.triggered.connect(self._quit)
                menu.addAction(act_show)
                menu.addSeparator()
                menu.addAction(act_quit)
                self.tray.setContextMenu(menu)
                self.tray.activated.connect(self._tray_activated)
                self.tray.show()
        except Exception:
            self.tray = None

        # sneltoetsen
        QShortcut(QKeySequence(Qt.Key.Key_Plus), self, self.zoom_in)
        QShortcut(QKeySequence("="), self, self.zoom_in)
        QShortcut(QKeySequence(Qt.Key.Key_Minus), self, self.zoom_out)
        QShortcut(QKeySequence(Qt.Key.Key_F), self, self._toggle_freeze)

        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self._update_zoom_label()
        if self.cfg.get("lens"):
            self.b_lens.setChecked(True)
        # Globale zoom-toetsen: veilig MEEPEILEN in de timer (geen RegisterHotKey,
        # geen nativeEvent -> geen native crash).
        self._u32 = None
        self._was_in = False
        self._was_out = False
        if sys.platform.startswith("win"):
            try:
                import ctypes
                self._u32 = ctypes.windll.user32
                self._u32.GetAsyncKeyState.argtypes = [ctypes.c_int]
                self._u32.GetAsyncKeyState.restype = ctypes.c_short
            except Exception:
                self._u32 = None

    def _poll_keys(self):
        """Ctrl + + / Ctrl + - vanuit elk programma, via GetAsyncKeyState.
        Met Ctrl zodat je gewoon + en - kunt blijven typen."""
        u = self._u32
        if not u:
            return
        try:
            def down(vk):
                return bool(u.GetAsyncKeyState(vk) & 0x8000)
            ctrl = down(0x11)                       # VK_CONTROL
            plus = ctrl and (down(0xBB) or down(0x6B))   # OEM_PLUS / numpad +
            minus = ctrl and (down(0xBD) or down(0x6D))  # OEM_MINUS / numpad -
            if plus and not self._was_in:
                self.zoom_in()
            if minus and not self._was_out:
                self.zoom_out()
            self._was_in = plus
            self._was_out = minus
        except Exception:
            pass

    def _header(self):
        w = QWidget()
        w.setObjectName("header")
        w.setFixedHeight(54)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 8, 14, 8)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(32))
        lay.addWidget(logo)
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        lay.addWidget(title)
        ver = QLabel("v" + APP_VERSION)
        ver.setObjectName("ver")
        lay.addWidget(ver)
        lay.addStretch(1)
        for label, slot in [(t("Instellingen\u2026", self.lang), self._settings),
                            (t("Snelgids", self.lang), self._guide),
                            (t("Over", self.lang), self._about)]:
            b = QPushButton(label)
            b.setObjectName("headerbtn")
            b.setFixedHeight(34)
            b.clicked.connect(lambda _=False, s=slot: s())
            lay.addWidget(b)
        return w

    def _toolbar(self):
        w = QWidget()
        w.setObjectName("toolbar")
        w.setFixedHeight(96)  # twee-rijen-0.16.2
        _rijen = QVBoxLayout(w)
        _rijen.setContentsMargins(0, 0, 0, 0)
        _rijen.setSpacing(0)
        lay = QHBoxLayout()
        _rijen.addLayout(lay)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(8)

        self.b_zout = QToolButton()
        self.b_zout.setText("\u2212")
        self.b_zout.setToolTip(t("Uitzoomen", self.lang))
        self.b_zout.clicked.connect(self.zoom_out)
        lay.addWidget(self.b_zout)
        self.b_zin = QToolButton()
        self.b_zin.setText("+")
        self.b_zin.setToolTip(t("Inzoomen", self.lang))
        self.b_zin.clicked.connect(self.zoom_in)
        lay.addWidget(self.b_zin)

        lay.addWidget(self._sep())
        self.b_follow = QPushButton(t("Volg muis", self.lang))
        self.b_follow.setCheckable(True)
        self.b_follow.setChecked(self.follow)
        self.b_follow.toggled.connect(self._set_follow)
        lay.addWidget(self.b_follow)
        self.b_freeze = QPushButton(t("Bevriezen", self.lang))
        self.b_freeze.setCheckable(True)
        self.b_freeze.toggled.connect(self._set_freeze)
        lay.addWidget(self.b_freeze)

        lay.addWidget(self._sep())
        lay.addWidget(QLabel(t("Filter:", self.lang)))
        self.filterbox = QComboBox()
        for nl, code in FILTERS:
            self.filterbox.addItem(t(nl, self.lang), code)
        fi = max(0, self.filterbox.findData(self.filter))
        self.filterbox.setCurrentIndex(fi)
        self.filterbox.currentIndexChanged.connect(self._set_filter)
        lay.addWidget(self.filterbox)

        self.b_smooth = QPushButton(t("Vloeiend", self.lang))
        self.b_smooth.setCheckable(True)
        self.b_smooth.setChecked(self.smooth)
        self.b_smooth.toggled.connect(self._set_smooth)
        lay.addWidget(self.b_smooth)

        self.b_ontop = QPushButton(t("Altijd bovenop", self.lang))
        self.b_ontop.setCheckable(True)
        self.b_ontop.setChecked(self.cfg.get("ontop", True))
        self.b_ontop.toggled.connect(self._set_ontop)
        lay.addWidget(self.b_ontop)

        lay.addStretch(1)
        lay = QHBoxLayout()   # tweede regel: zwevend / volledig scherm / verbergen
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(8)
        _rijen.addLayout(lay)
        self.b_lens = QPushButton("\u25ce  " + t("Zwevend", self.lang))
        self.b_lens.setCheckable(True)
        self.b_lens.toggled.connect(self._set_lens)
        lay.addWidget(self.b_lens)
        lay.addWidget(QLabel(t("Grootte:", self.lang)))
        self.sizebox = QComboBox()
        for nl, _w, _h in LENS_SIZES:
            self.sizebox.addItem(t(nl, self.lang))
        self.sizebox.setCurrentIndex(int(self.cfg.get("lenssize", 1)))
        self.sizebox.currentIndexChanged.connect(self._set_lens_size)
        lay.addWidget(self.sizebox)

        self.b_fs = QPushButton("\u2922  " + t("Volledig scherm", self.lang))
        self.b_fs.setCheckable(True)
        self.b_fs.setToolTip(t("Hele scherm vergroten; scroll = zoom, Esc = stoppen",
                               self.lang))
        self.b_fs.toggled.connect(self._set_fullscreen)
        lay.addWidget(self.b_fs)

        lay.addWidget(self._sep())
        self.b_hide = QPushButton("\u2935  " + t("Verbergen", self.lang))
        self.b_hide.setToolTip(t("Verbergen", self.lang))
        self.b_hide.clicked.connect(self._hide_to_tray)
        lay.addWidget(self.b_hide)

        lay.addStretch(1)
        return w

    def _sep(self):
        s = QFrame()
        s.setFrameShape(QFrame.Shape.VLine)
        s.setObjectName("sep")
        return s

    # ---- vergroot-lus ----
    def _tick(self):
        self._poll_keys()
        if self.frozen:
            return
        use_fs = self.fs_on and self.fs.isVisible()
        use_lens = ((not use_fs) and self.lens_on and self.lens.isVisible())
        if not (use_fs or use_lens):
            return    # niets te vergroten -> geen schermopname, geen lus
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.geometry()
        gw = geo.width() or 1
        gh = geo.height() or 1
        # pak gericht ALLEEN dit scherm; grabWindow(0) zonder rechthoek pakt bij
        # multi-monitor soms het hele bureaublad -> verkeerde schaalfactor/vergroting
        full = screen.grabWindow(0, geo.x(), geo.y(), gw, gh)
        if full.isNull():
            full = screen.grabWindow(0)
        if full.isNull():
            return
        img = full.toImage()
        sx = img.width() / gw
        sy = img.height() / gh
        if self.follow:
            pt = QCursor.pos()
            self._last_pt = pt
        else:
            pt = self._last_pt
        if use_fs:
            dw = gw
            dh = gh
        else:
            dw = max(1, self.lens.width())
            dh = max(1, self.lens.height())
        # cropgebied (echte pixels); nooit groter dan het scherm
        crop_w = max(1, min(img.width(), int(dw * sx / self.zoom)))
        crop_h = max(1, min(img.height(), int(dh * sy / self.zoom)))
        cx = (pt.x() - geo.left()) * sx
        cy = (pt.y() - geo.top()) * sy
        if use_lens:
            # gebied gecentreerd op de muis; lensje aan de dichtstbijzijnde kant
            x, y = self._place_lens(pt, geo, cx, cy, crop_w, crop_h,
                                    sx, sy, img.width(), img.height())
        else:
            x = int(max(0, min(cx - crop_w / 2.0, img.width() - crop_w)))
            y = int(max(0, min(cy - crop_h / 2.0, img.height() - crop_h)))
        crop = apply_filter(img.copy(x, y, crop_w, crop_h), self.filter)
        tm = (Qt.TransformationMode.SmoothTransformation if self.smooth
              else Qt.TransformationMode.FastTransformation)
        if use_fs:
            out = crop.scaled(int(dw * sx), int(dh * sy),
                              Qt.AspectRatioMode.IgnoreAspectRatio, tm)
            pm = QPixmap.fromImage(out)
            # markeer waar de (verborgen) muiscursor staat
            fx = (cx - x) * (dw * sx) / crop_w
            fy = (cy - y) * (dh * sy) / crop_h
            self._draw_crosshair(pm, fx, fy)
            self.fs.view.setPixmap(pm)
        else:
            # op ECHTE schermresolutie schalen -> scherp (geen dubbele opschaling)
            out = crop.scaled(int(dw * sx), int(dh * sy),
                              Qt.AspectRatioMode.IgnoreAspectRatio, tm)
            pm = QPixmap.fromImage(out)
            # klein kruisje waar de muis staat (= het midden van het lensje)
            fx = (cx - x) * (dw * sx) / crop_w
            fy = (cy - y) * (dh * sy) / crop_h
            self._draw_crosshair(pm, fx, fy, r=10, width=2)
            self.lens.view.setPixmap(pm)

    def _draw_crosshair(self, pm, fx, fy, r=18, width=3):
        p = QPainter(pm)
        pen = QPen(QColor(ACCENT))
        pen.setWidth(width)
        p.setPen(pen)
        p.drawLine(int(fx - r), int(fy), int(fx + r), int(fy))
        p.drawLine(int(fx), int(fy - r), int(fx), int(fy + r))
        p.end()

    def _wheel_zoom(self, direction):
        if direction > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def _place_lens(self, pt, geo, cx, cy, crop_w, crop_h, sx, sy, imgw, imgh):
        """Toont wat ROND de muis zit (muis in het midden van het lensje) en zet
        het lensje aan de kant die het DICHTST bij de muis ligt: rechts, links,
        onder of boven. Bij een schermrand dus onder/boven i.p.v. ver weg.
        Geen overlap met het gebied = geen zwart. Geeft (crop-x, crop-y) terug."""
        lw = self.lens.width()
        lh = self.lens.height()
        m = 12
        x = int(max(0, min(cx - crop_w / 2.0, imgw - crop_w)))
        y = int(max(0, min(cy - crop_h / 2.0, imgh - crop_h)))
        cl = geo.left() + x / sx           # logische randen van het gebied
        cr = geo.left() + (x + crop_w) / sx
        ct = geo.top() + y / sy
        cb = geo.top() + (y + crop_h) / sy

        def cxp(v):
            return int(max(geo.left(), min(v, geo.right() - lw)))

        def cyp(v):
            return int(max(geo.top(), min(v, geo.bottom() - lh)))

        cands = [
            (cxp(cr + m), cyp(pt.y() - lh / 2)),      # rechts
            (cxp(cl - m - lw), cyp(pt.y() - lh / 2)),  # links
            (cxp(pt.x() - lw / 2), cyp(cb + m)),       # onder
            (cxp(pt.x() - lw / 2), cyp(ct - m - lh)),  # boven
        ]
        best = None
        bestd = None
        for lx, ly in cands:
            # mag het gebied [cl,cr]x[ct,cb] niet overlappen (anders zwart)
            if not (lx + lw <= cl or lx >= cr or ly + lh <= ct or ly >= cb):
                continue
            dx = max(lx - pt.x(), pt.x() - (lx + lw), 0)
            dy = max(ly - pt.y(), pt.y() - (ly + lh), 0)
            d = dx * dx + dy * dy
            if bestd is None or d < bestd:
                bestd = d
                best = (lx, ly)
        if best is None:
            best = (cxp(cr + m), cyp(pt.y() - lh / 2))
        self.lens.move(best[0], best[1])
        return x, y

    def _size_lens(self):
        idx = max(0, min(self.sizebox.currentIndex(), len(LENS_SIZES) - 1))
        _n, w, h = LENS_SIZES[idx]
        self.lens.setFixedSize(w, h)
        self.cfg["lenssize"] = idx
        save_config(self.cfg)

    def _set_lens_size(self, _i):
        self._size_lens()

    def _set_lens(self, on):
        self.lens_on = on
        if on:
            if self.b_fs.isChecked():
                self.b_fs.setChecked(False)   # niet samen met volledig scherm
            if self.zoom < 2.0:               # loep onder 2x is zinloos
                self.zoom = 2.0
                self._update_zoom_label()
            self._size_lens()
            self.lens.show()
        else:
            self.lens.hide()
        self.cfg["lens"] = on
        save_config(self.cfg)

    def _set_fullscreen(self, on):
        self.fs_on = on
        if on:
            if self.b_lens.isChecked():
                self.b_lens.setChecked(False)  # lensje uit
            screen = QApplication.primaryScreen()
            geo = screen.geometry() if screen else self.geometry()
            self.fs.setGeometry(geo)
            self.fs.showFullScreen()
            self.fs.raise_()
            self.fs.activateWindow()
            self.fs.setFocus()
            self._set_running(True)
            self.hide()   # hoofdvenster weg; overlay dekt toch alles
        else:
            self.fs.hide()
            self.showNormal()
            self.raise_()
            self.activateWindow()

    # ---- acties ----
    def _zoom_floor(self):
        # De loep onder 2x is zinloos; volledig scherm mag wel tot 1.0x (oriënteren).
        if self.fs_on:
            return 1.0
        return 2.0

    def zoom_in(self):
        self.zoom = min(ZOOM_MAX, round(self.zoom + ZOOM_STEP, 1))
        self._update_zoom_label()
        self._save()

    def zoom_out(self):
        self.zoom = max(self._zoom_floor(), round(self.zoom - ZOOM_STEP, 1))
        self._update_zoom_label()
        self._save()

    def _update_zoom_label(self):
        self.zoom_lbl.setText("%.1fx" % self.zoom)

    def _set_follow(self, on):
        self.follow = on
        self._save()

    def _set_freeze(self, on):
        self.frozen = on
        if self.statusBar():
            self.statusBar().showMessage(t("Bevroren", self.lang) if on else "", 0
                                         if on else 1)

    def _toggle_freeze(self):
        self.b_freeze.setChecked(not self.b_freeze.isChecked())

    def _set_filter(self, _idx):
        self.filter = self.filterbox.currentData()
        self._save()

    def _set_smooth(self, on):
        self.smooth = on
        self._save()

    def _set_ontop(self, on):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.show()
        self.cfg["ontop"] = on
        save_config(self.cfg)

    def _save(self):
        self.cfg.update({"zoom": self.zoom, "filter": self.filter,
                         "smooth": self.smooth, "follow": self.follow})
        save_config(self.cfg)

    def _settings(self):
        dlg = SettingsDialog(self, dict(self.cfg), self.lang)
        if dlg.exec():
            self.cfg = dlg.result_cfg()
            save_config(self.cfg)

    def _guide(self):
        GuideDialog(self, self.lang).exec()

    def _about(self):
        QMessageBox.information(
            self, t("Over", self.lang),
            "%s v%s\n\n%s\nDravenlock\n%s\n%s"
            % (APP_NAME, APP_VERSION,
               "Schermvergrootglas." if self.lang == "nl" else "Screen magnifier.",
               SUPPORT_MAIL, DONATE_URL))

    # ---- systeemvak / verbergen ----
    def showEvent(self, ev):
        self._set_running(True)
        super().showEvent(ev)

    def wheelEvent(self, ev):
        d = ev.angleDelta().y()
        if d > 0:
            self.zoom_in()
        elif d < 0:
            self.zoom_out()
        ev.accept()

    def _apply_capture_exclude(self):
        """Sluit dit venster uit van schermopname (Windows 10 2004+),
        zodat het vergrootglas zichzelf niet vergroot."""
        if self._affinity_done or not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            WDA_EXCLUDEFROMCAPTURE = 0x11
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
            self._affinity_done = True
        except Exception:
            pass

    def _set_running(self, on):
        if on:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def changeEvent(self, ev):
        if ev.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized and self.tray:
                QTimer.singleShot(0, self._hide_to_tray)
        super().changeEvent(ev)

    def _hide_to_tray(self):
        # forceer het zwevende vergrootglas aan, zodat ALLEEN dat overblijft
        if not self.b_lens.isChecked():
            self.b_lens.setChecked(True)   # -> _set_lens(True)
        else:
            self._set_lens(True)
        if not self.tray:
            self.showMinimized()
            return
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.hide()
        if not self._tray_hinted:
            self._tray_hinted = True
            try:
                self.tray.showMessage(
                    APP_NAME,
                    t("DraveZoom draait nog in het systeemvak. "
                      "Klik op het icoon om terug te keren.", self.lang),
                    app_icon(), 4000)
            except Exception:
                pass

    def _restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._set_lens(self.b_lens.isChecked())

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.isVisible():
                self._hide_to_tray()
            else:
                self._restore()

    def _quit(self):
        self._quitting = True
        QApplication.quit()

    def closeEvent(self, ev):
        try:
            self.timer.stop()
        except Exception:
            pass
        try:
            if self.tray:
                self.tray.hide()
        except Exception:
            pass
        try:
            self.lens.close()
            self.fs.close()
        except Exception:
            pass
        ev.accept()


QSS = """
* { font-family: 'Segoe UI', sans-serif; font-size: 14px; color: %(silver)s; }
QMainWindow, QWidget { background: %(bg)s; }
#header { background: %(panel)s; border-bottom: 1px solid #23232b; }
#title { font-size: 19px; font-weight: 700; }
#ver { color: %(mute)s; font-size: 12px; }
#toolbar { background: %(bg)s; border-bottom: 1px solid #23232b; }
#muted, #hint { color: %(mute)s; font-size: 12px; }
QFrame#sep { color: #2c2c36; }
QPushButton { background: %(panel)s; border: 1px solid #2c2c36; border-radius: 8px;
              padding: 7px 12px; color: %(silver)s; min-height: 34px; }
QPushButton:hover { border-color: %(accent)s; }
QPushButton#headerbtn { min-height: 0; padding: 5px 12px; font-size: 13px; }
QPushButton:checked { background: %(accent)s; color: #08131f; font-weight: 700;
                      border: none; }
QToolButton { background: %(panel)s; border: 1px solid #2c2c36; border-radius: 8px;
              padding: 5px 11px; color: %(silver)s; min-width: 26px; min-height: 30px;
              font-size: 16px; }
QToolButton:hover { border-color: %(accent)s; }
QToolButton#donate { border: none; background: transparent; color: %(accent)s;
                     font-size: 14px; }
QComboBox { background: #14141a; border: 1px solid #2c2c36; border-radius: 8px;
            padding: 6px 10px; min-height: 30px; }
QComboBox QAbstractItemView { background: #16161b; color: %(silver)s;
            selection-background-color: %(accent)s; selection-color: #08131f; }
QLabel#lens { background: #1c1c22; border: none; color: %(mute)s; font-size: 16px; }
QLabel#infopanel { background: #14141a; border: none; color: %(silver)s;
                   font-size: 16px; padding: 24px; line-height: 150%%; }
QWidget#lenswin { background: %(accent)s; }
QLabel#lensview { background: #1c1c22; border: none; }
QStatusBar { background: %(panel)s; }
QDialog { background: %(bg)s; }
QPlainTextEdit#guide { background: %(panel)s; border: 1px solid #2c2c36;
                       border-radius: 8px; padding: 10px; }
""" % {"bg": BG, "panel": PANEL, "silver": SILVER, "mute": MUTE, "accent": ACCENT}


def _install_excepthook():
    import traceback

    def hook(exctype, value, tb):
        msg = "".join(traceback.format_exception(exctype, value, tb))
        try:
            with open(os.path.join(_app_dir(), "dravezoom-fout.txt"),
                      "w", encoding="utf-8") as f:
                f.write(msg)
        except Exception:
            pass
        try:
            if QApplication.instance():
                QMessageBox.critical(None, "DraveZoom - fout",
                                     "Er ging iets mis:\n\n" + msg[-1500:]
                                     + "\n\n(Ook opgeslagen in dravezoom-fout.txt)")
        except Exception:
            pass
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = hook


def _enable_crashlog():
    """Vangt OOK harde (C-niveau) crashes op en schrijft een spoor weg.
    Python-fouten gaan naar dravezoom-fout.txt; harde crashes naar
    dravezoom-crash.txt (sys.excepthook kan die niet vangen)."""
    try:
        import faulthandler
        path = os.path.join(_app_dir(), "dravezoom-crash.txt")
        f = open(path, "w", encoding="utf-8")
        f.write("DraveZoom crash-log. Leeg = geen crash. "
                "Bij een harde (C-)crash staat hieronder het spoor.\n")
        f.flush()
        faulthandler.enable(file=f, all_threads=True)
        return f  # open houden zolang de app draait
    except Exception:
        return None


def main():
    global _LANG
    _crashf = _enable_crashlog()
    _install_excepthook()
    app = QApplication(sys.argv)
    try:
        cfg = load_config()
        _LANG = detect_lang(cfg)
        app.setStyleSheet(QSS)
        win = DraveZoom(cfg)
        win.show()
    except Exception:
        sys.excepthook(*sys.exc_info())
        return
    try:  # Dravenlock: stille update-check (uit te zetten; Ctrl+Shift+U = met de hand)
        import drave_update
        drave_update.start(win, 'DraveZoom', APP_VERSION)
    except Exception:
        pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
