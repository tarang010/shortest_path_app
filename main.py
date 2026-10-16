"""Tarang Nav - multi-mode routing with live traffic, GPS trip tracking and address suggestions.
Free services only: OpenStreetMap (OSRM routing, Nominatim, Photon) and a free TomTom traffic key."""
import itertools
import json
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.factory import Factory
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import SpinnerOption  # noqa: F401  (styled in KV)
from kivy.uix.widget import Widget
from kivy_garden.mapview import MapLayer, MapView

import algos
import geo
import places
import traffic
import tracker as trk
from gps import GPSProvider, keep_screen_on
from modes import MODES, MODE_NAMES

HERE = os.path.dirname(os.path.abspath(__file__))
NAVY = (0.039, 0.122, 0.267, 1)
ACCENT = (0.133, 0.827, 0.929, 1)
FIELD = (0.094, 0.231, 0.463, 1)
PANEL = (0.067, 0.176, 0.369, 1)
SEL_COLOR = (0.10, 0.45, 1.0, 1)
ALT_COLOR = (0.45, 0.55, 0.72, 0.85)
TRAIL_COLOR = (0.10, 0.75, 0.35, 1)
MAX_STOPS = 8
DAILY_TRAFFIC_BUDGET = 2400          # TomTom free tier is 2,500 non-tile requests/day

KV = """
#:set NAVY (0.039, 0.122, 0.267, 1)
#:set PANEL (0.067, 0.176, 0.369, 1)
#:set FIELD (0.094, 0.231, 0.463, 1)
#:set ACCENT (0.133, 0.827, 0.929, 1)
#:set DANGER (0.78, 0.22, 0.27, 1)
#:set MUTED (0.66, 0.77, 0.93, 1)

<NavInput@TextInput>:
    background_normal: ''
    background_active: ''
    background_color: FIELD
    foreground_color: 1, 1, 1, 1
    hint_text_color: MUTED
    cursor_color: ACCENT
    selection_color: 0.13, 0.83, 0.93, 0.35
    padding: [dp(14), dp(13), dp(14), dp(10)]
    multiline: False
    write_tab: False
    size_hint_y: None
    height: dp(46)
    font_size: '15sp'

<NavButton>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: (0.039, 0.122, 0.267, 1) if self.bg[1] > 0.5 else (1, 1, 1, 1)
    bold: True
    font_size: '15sp'
    canvas.before:
        Color:
            rgba: self.bg if self.state == 'normal' else (self.bg[0] * 0.75, self.bg[1] * 0.75, self.bg[2] * 0.75, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]

<NavSpinner@Spinner>:
    background_normal: ''
    background_down: ''
    background_color: 0, 0, 0, 0
    color: 1, 1, 1, 1
    bold: True
    font_size: '15sp'
    halign: 'left'
    text_size: self.width - dp(44), None
    option_cls: 'SpinnerOption'
    canvas.before:
        Color:
            rgba: FIELD
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
    canvas.after:
        Color:
            rgba: ACCENT
        Triangle:
            points: self.right - dp(30), self.center_y + dp(4), self.right - dp(14), self.center_y + dp(4), self.right - dp(22), self.center_y - dp(5)

<SpinnerOption>:
    background_normal: ''
    background_down: ''
    background_color: ACCENT if self.state == 'down' else FIELD
    color: (0.039, 0.122, 0.267, 1) if self.state == 'down' else (1, 1, 1, 1)
    size_hint_y: None
    height: dp(46)
    font_size: '15sp'
    halign: 'left'
    text_size: self.width - dp(24), None

<NoteLabel@Label>:
    size_hint_y: None
    height: self.texture_size[1] + dp(8)
    text_size: self.width, None
    font_size: '11.5sp'
    color: MUTED
    halign: 'left'
    valign: 'top'
    markup: True

<Loader>:
    size_hint_y: None
    height: dp(3)
    canvas:
        Color:
            rgba: 0.067, 0.176, 0.369, 1
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: 0.133, 0.827, 0.929, self.alpha
        Rectangle:
            pos: self.x + self.frac * self.width * 0.75, self.y
            size: self.width * 0.25, self.height

<Header>:
    size_hint_y: None
    height: dp(60)
    padding: dp(12), dp(6)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: PANEL
        Rectangle:
            pos: self.pos
            size: self.size
    Image:
        source: root.logo
        size_hint: None, 1
        width: dp(44)
        fit_mode: 'contain'
    BoxLayout:
        orientation: 'vertical'
        Label:
            text: 'Tarang Nav'
            font_size: '21sp'
            bold: True
            color: 1, 1, 1, 1
            halign: 'left'
            valign: 'bottom'
            text_size: self.size
        Label:
            text: 'Navigate every route'
            font_size: '11sp'
            color: ACCENT
            halign: 'left'
            valign: 'top'
            text_size: self.size
    NavButton:
        text: 'Trips'
        font_size: '12sp'
        bg: FIELD
        size_hint: None, None
        size: dp(56), dp(34)
        pos_hint: {'center_y': 0.5}
        on_release: app.root.open_trips()
    NavButton:
        text: 'Settings'
        font_size: '12sp'
        bg: FIELD
        size_hint: None, None
        size: dp(72), dp(34)
        pos_hint: {'center_y': 0.5}
        on_release: app.root.open_settings()

<SuggestItem>:
    background_normal: ''
    background_down: ''
    background_color: ACCENT if self.state == 'down' else FIELD
    color: (0.039, 0.122, 0.267, 1) if self.state == 'down' else (1, 1, 1, 1)
    size_hint_y: None
    height: dp(42)
    font_size: '13.5sp'
    halign: 'left'
    valign: 'middle'
    padding: dp(14), 0
    text_size: self.width - dp(28), None
    shorten: True
    shorten_from: 'right'

<PlaceField>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    BoxLayout:
        id: row
        size_hint_y: None
        height: dp(46)
        spacing: dp(6)
        NavInput:
            id: ti
            hint_text: root.hint
            on_text: root.on_text(self.text)
            on_focus: root.on_focus(self.focus)
        NavButton:
            id: gpsb
            text: 'GPS'
            font_size: '13sp'
            size_hint_x: None
            width: dp(50)
            on_release: root.use_gps()
        NavButton:
            id: delb
            text: 'X'
            bg: DANGER
            size_hint_x: None
            width: dp(50)
            on_release: root.remove()
    BoxLayout:
        id: sugg
        orientation: 'vertical'
        size_hint_y: None
        height: self.minimum_height
        canvas.before:
            Color:
                rgba: ACCENT
            Rectangle:
                pos: self.x, self.y
                size: self.width, (dp(1.5) if self.height > 0 else 0)

<Form>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(10), dp(8), dp(10), dp(6)
    spacing: dp(6)
    canvas.before:
        Color:
            rgba: NAVY
        Rectangle:
            pos: self.pos
            size: self.size
    PlaceField:
        id: a
        hint: 'From  (type a place)'
        gps_button: True
    BoxLayout:
        id: stops_box
        orientation: 'vertical'
        size_hint_y: None
        height: self.minimum_height
        spacing: dp(6)
    PlaceField:
        id: b
        hint: 'To  (type a place)'
    BoxLayout:
        size_hint_y: None
        height: dp(46)
        spacing: dp(8)
        NavButton:
            id: addstop
            text: '+ Add stop'
            bg: FIELD
            size_hint_x: 0.42
            on_release: root.add_stop()
        NavSpinner:
            id: mode
            text: 'Car'
            values: root.mode_names
            size_hint_x: 0.58
    NavButton:
        text: 'Find routes'
        size_hint_y: None
        height: dp(48)
        on_release: root.go()

<Stat>:
    orientation: 'vertical'
    Label:
        text: root.value
        bold: True
        font_size: '15sp'
        color: 1, 1, 1, 1
    Label:
        text: root.caption
        font_size: '10sp'
        color: MUTED

<Results>:
    orientation: 'vertical'
    padding: dp(10), dp(4), dp(10), dp(6)
    spacing: dp(6)
    canvas.before:
        Color:
            rgba: NAVY
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        id: status
        text: 'Type a place, pick a suggestion, choose a mode and tap Find routes.'
        size_hint_y: None
        height: dp(34)
        font_size: '12sp'
        color: MUTED
        halign: 'left'
        valign: 'middle'
        text_size: self.size
        max_lines: 2
        markup: True
    BoxLayout:
        size_hint_y: None
        height: dp(46)
        spacing: dp(6)
        NavButton:
            id: tripbtn
            text: 'Start trip'
            bg: FIELD
            size_hint_x: None
            width: dp(104)
            on_release: app.root.toggle_trip()
        Stat:
            id: s_dist
            value: '0 m'
            caption: 'covered'
        Stat:
            id: s_time
            value: '0:00'
            caption: 'time'
        Stat:
            id: s_avg
            value: '0 km/h'
            caption: 'avg speed'
    BoxLayout:
        size_hint_y: None
        height: dp(38)
        spacing: dp(8)
        NavButton:
            id: bfast
            text: 'Fastest'
            bg: PANEL
            on_release: app.root.select_kind('fast')
        NavButton:
            id: bshort
            text: 'Shortest'
            bg: PANEL
            on_release: app.root.select_kind('short')
    ScrollView:
        bar_color: ACCENT
        bar_width: dp(3)
        do_scroll_x: False
        BoxLayout:
            id: cards
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(6)

<RouteCard>:
    orientation: 'vertical'
    size_hint_y: None
    height: dp(70)
    padding: dp(14), dp(6)
    canvas.before:
        Color:
            rgba: ACCENT if self.selected else FIELD
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(12)]
        Color:
            rgba: (0.08, 0.22, 0.46, 1) if self.selected else PANEL
        RoundedRectangle:
            pos: self.x + dp(2), self.y + dp(2)
            size: self.width - dp(4), self.height - dp(4)
            radius: [dp(10)]
    Label:
        text: root.title
        markup: True
        bold: True
        font_size: '15sp'
        color: 1, 1, 1, 1
        halign: 'left'
        valign: 'bottom'
        text_size: self.size
    Label:
        text: root.sub
        markup: True
        font_size: '12.5sp'
        color: ACCENT if root.selected else MUTED
        halign: 'left'
        valign: 'top'
        text_size: self.size
        max_lines: 2
"""


# ----------------------------------------------------------------------------- small widgets
class NavButton(Button):
    bg = ListProperty([0.133, 0.827, 0.929, 1])


class Loader(Widget):
    frac = NumericProperty(0)
    alpha = NumericProperty(0)

    def start(self):
        self.stop()
        self.alpha = 1
        self._anim = Animation(frac=1, d=0.9, t="in_out_quad") + Animation(frac=0, d=0.9, t="in_out_quad")
        self._anim.repeat = True
        self._anim.start(self)

    def stop(self):
        a = getattr(self, "_anim", None)
        if a:
            a.cancel(self)
        self.alpha = 0


class Header(BoxLayout):
    logo = StringProperty(os.path.join(HERE, "logo.png"))


class Stat(BoxLayout):
    value = StringProperty("")
    caption = StringProperty("")


class SuggestItem(Button):
    place = ObjectProperty(None)


class RouteCard(ButtonBehavior, BoxLayout):
    selected = BooleanProperty(False)
    title = StringProperty("")
    sub = StringProperty("")


class Results(BoxLayout):
    pass


class FormScroll(ScrollView):
    pass


class PlaceField(BoxLayout):
    """Text box with live address suggestions (Photon), optional GPS and delete buttons."""
    hint = StringProperty("")
    gps_button = BooleanProperty(False)
    removable = BooleanProperty(False)
    lat = ObjectProperty(None, allownone=True)
    lon = ObjectProperty(None, allownone=True)

    def __init__(self, **kw):
        super().__init__(**kw)
        self._silent, self._seq, self._ev = False, 0, None
        self.on_removed = None
        Clock.schedule_once(self._setup, 0)

    def _setup(self, dt):
        row = self.ids.row
        if not self.gps_button and self.ids.gpsb.parent:
            row.remove_widget(self.ids.gpsb)
        if not self.removable and self.ids.delb.parent:
            row.remove_widget(self.ids.delb)

    @property
    def text(self):
        return self.ids.ti.text.strip()

    def set_place(self, text, lat, lon):
        self._silent = True
        self.ids.ti.text = text
        self._silent = False
        self.lat, self.lon = lat, lon
        self.clear_suggestions()

    def on_text(self, text):
        if self._silent:
            return
        self.lat = self.lon = None                       # edited by hand: coordinates no longer valid
        if self._ev:
            self._ev.cancel()
        if len(text.strip()) < 3:
            self._seq += 1
            self.clear_suggestions()
            return
        self._ev = Clock.schedule_once(lambda dt: self._query(text.strip()), 0.5)   # debounce

    def _query(self, q):
        self._seq += 1
        seq = self._seq
        bias = App.get_running_app().root.bias()

        def work():
            try:
                res = places.suggest(q, bias)
            except Exception:
                res = []
            Clock.schedule_once(lambda dt: self._show(seq, res))
        threading.Thread(target=work, daemon=True).start()

    def _show(self, seq, res):
        if seq != self._seq:
            return                                       # stale answer
        box = self.ids.sugg
        box.clear_widgets()
        for p in res[:5]:
            it = SuggestItem(text=p["label"], place=p)
            it.bind(on_press=lambda w: self.pick(w.place))
            box.add_widget(it)

    def pick(self, p):
        self.set_place(p["label"], p["lat"], p["lon"])
        self.ids.ti.focus = False

    def clear_suggestions(self):
        self.ids.sugg.clear_widgets()

    def on_focus(self, focused):
        if not focused:
            self._seq += 1                               # drop pending answers
            Clock.schedule_once(lambda dt: self.clear_suggestions(), 0.25)

    def use_gps(self):
        App.get_running_app().root.use_my_location(self)

    def remove(self):
        if self.on_removed:
            self.on_removed(self)


class Form(BoxLayout):
    mode_names = MODE_NAMES

    def fields(self):
        return [self.ids.a] + list(reversed(self.ids.stops_box.children)) + [self.ids.b]

    def add_stop(self):
        box = self.ids.stops_box
        if len(box.children) >= MAX_STOPS:
            App.get_running_app().root.results.ids.status.text = f"Maximum {MAX_STOPS} stops."
            return
        pf = PlaceField(removable=True)
        pf.on_removed = self.remove_stop
        box.add_widget(pf, index=0)                       # index 0 = bottom = last stop
        self._renumber()
        Clock.schedule_once(lambda dt: setattr(pf.ids.ti, "focus", True), 0.1)

    def remove_stop(self, pf):
        self.ids.stops_box.remove_widget(pf)
        self._renumber()

    def _renumber(self):
        for i, pf in enumerate(reversed(self.ids.stops_box.children), 1):
            pf.hint = f"Stop {i}  (type a place)"

    def go(self):
        App.get_running_app().root.run()


# ----------------------------------------------------------------------------- map layer
def dash_pieces(pts, dash, gap):
    """Split a flat [x0,y0,x1,y1,...] polyline into dash segments (Kivy cannot dash thick lines)."""
    out, drawing, remain = [], True, dash
    x0, y0 = pts[0], pts[1]
    cur = [x0, y0]
    for i in range(2, len(pts), 2):
        x1, y1 = pts[i], pts[i + 1]
        seg = math.hypot(x1 - x0, y1 - y0)
        while seg > 1e-6:
            if seg >= remain:
                t = remain / seg
                xm, ym = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                if drawing:
                    cur += [xm, ym]
                    out.append(cur)
                    cur = []
                else:
                    cur = [xm, ym]
                drawing = not drawing
                seg -= remain
                x0, y0 = xm, ym
                remain = dash if drawing else gap
            else:
                if drawing:
                    cur += [x1, y1]
                remain -= seg
                seg = 0
                x0, y0 = x1, y1
    if drawing and len(cur) >= 4:
        out.append(cur)
    return out


class RouteLayer(MapLayer):
    """Candidate routes, selected route, A/B/stop markers, GPS dot and the trip trail."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.routes, self.markers, self.trail, self.me = [], [], [], None

    def set_data(self, routes, markers):
        self.routes, self.markers = routes, markers
        self.reposition()

    @staticmethod
    def _lod(route, zoom):
        for z, c in route["lods"]:
            if z >= zoom:
                return c
        return route["coords"]

    @staticmethod
    def _runs(coords, bb):
        la0, lo0, la1, lo1 = bb
        dla, dlo = (la1 - la0) * 0.5, (lo1 - lo0) * 0.5
        la0, la1, lo0, lo1 = la0 - dla, la1 + dla, lo0 - dlo, lo1 + dlo
        runs, cur = [], []
        for i, p in enumerate(coords):
            if la0 <= p[0] <= la1 and lo0 <= p[1] <= lo1:
                if not cur and i > 0:
                    cur.append(coords[i - 1])
                cur.append(p)
            elif cur:
                cur.append(p)
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        return runs

    def reposition(self):
        mv = self.parent
        if mv is None:
            return
        self.canvas.clear()
        z = mv.zoom
        try:
            bb = tuple(mv.get_bbox())
        except Exception:
            bb = None
        with self.canvas:
            for r in sorted(self.routes, key=lambda r: r.get("selected", False)):
                coords = self._lod(r, z)
                runs = self._runs(coords, bb) if (bb and len(coords) > 1200) else [coords]
                for run in runs:
                    pts = []
                    for la, lo in run:
                        x, y = mv.get_window_xy_from(la, lo, z)
                        pts += [x, y]
                    if len(pts) < 4:
                        continue
                    pieces = dash_pieces(pts, dp(11), dp(7)) if r.get("est") else [pts]
                    for pc in pieces:
                        if len(pc) < 4:
                            continue
                        if r.get("selected"):
                            Color(1, 1, 1, 1)
                            Line(points=pc, width=dp(5.5), joint="round", cap="round")
                            Color(*SEL_COLOR)
                            Line(points=pc, width=dp(3.6), joint="round", cap="round")
                        else:
                            Color(*ALT_COLOR)
                            Line(points=pc, width=dp(2.4), joint="round", cap="round")
            if len(self.trail) > 1:                       # where you have actually been
                tr = self.trail if len(self.trail) < 1500 else self.trail[:: len(self.trail) // 1500 + 1]
                pts = []
                for la, lo in tr:
                    x, y = mv.get_window_xy_from(la, lo, z)
                    pts += [x, y]
                Color(1, 1, 1, 1)
                Line(points=pts, width=dp(4.5), joint="round", cap="round")
                Color(*TRAIL_COLOR)
                Line(points=pts, width=dp(3), joint="round", cap="round")
            rad = dp(11)
            for la, lo, label, rgb in self.markers:
                x, y = mv.get_window_xy_from(la, lo, z)
                Color(1, 1, 1, 1)
                Ellipse(pos=(x - rad - 1.5, y - rad - 1.5), size=(2 * rad + 3, 2 * rad + 3))
                Color(*rgb, 1)
                Ellipse(pos=(x - rad, y - rad), size=(2 * rad, 2 * rad))
                cl = CoreLabel(text=label, font_size=dp(13), bold=True)
                cl.refresh()
                tex = cl.texture
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(x - tex.width / 2, y - tex.height / 2), size=tex.size)
            if self.me:                                   # blue GPS dot with accuracy halo
                x, y = mv.get_window_xy_from(self.me["lat"], self.me["lon"], z)
                mpp = 156543.03392 * math.cos(math.radians(self.me["lat"])) / (2 ** z)
                ar = max(dp(8), min(dp(70), (self.me.get("acc") or 20) / max(mpp, 0.01)))
                Color(0.1, 0.45, 1, 0.18)
                Ellipse(pos=(x - ar, y - ar), size=(2 * ar, 2 * ar))
                Color(1, 1, 1, 1)
                Ellipse(pos=(x - dp(9), y - dp(9)), size=(dp(18), dp(18)))
                Color(0.1, 0.45, 1, 1)
                Ellipse(pos=(x - dp(6.5), y - dp(6.5)), size=(dp(13), dp(13)))


# ----------------------------------------------------------------------------- helpers
def fmt_km(m):
    return f"{m/1000:,.1f} km" if m >= 1000 else f"{m:.0f} m"


def fmt_time(s):
    if s is None:
        return "-"
    m = int(round(s / 60.0))
    if m < 60:
        return f"{m} min"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h} h {m} min" if m else f"{h} h"
    d, h = divmod(h, 24)
    return f"{d} d {h} h" if h else f"{d} d"


def fmt_clock(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def traffic_text(r):
    t = r.get("traffic")
    if not t or t["level"] is None:
        return ""
    if t["closed"]:
        return "[color=f87171]road closure ahead[/color]"
    col = {"Light": "4ade80", "Moderate": "fbbf24", "Heavy": "f87171"}[t["level"]]
    extra = f"+{fmt_time(t['delay'])}, " if t["delay"] >= 60 else ""
    return f"[color={col}]{extra}{t['level'].lower()} traffic[/color]"


def _mark(pts):
    n = len(pts)
    out = []
    for i, p in enumerate(pts):
        rgb = (0.1, 0.6, 0.2) if i == 0 else (0.85, 0.15, 0.15) if i == n - 1 else (0.2, 0.3, 0.8)
        out.append((p[0], p[1], "A" if i == 0 else "B" if i == n - 1 else str(i), rgb))
    return out


def get_routes(mode, pts, alternatives=False, timeout=30):
    spec = MODES[mode]
    if spec["kind"] == "road":
        opts = geo.route_options(pts, spec["profile"], alternatives, timeout)
        for o in opts:
            if o["dur"] is not None:
                o["dur"] *= spec["dur_factor"]
        return opts
    return [geo.estimate_route(pts, spec)]


class Settings:
    """Tiny JSON settings/trips file kept in the app's private storage."""

    def __init__(self, path):
        self.path, self.d = path, {}
        try:
            with open(path) as f:
                self.d = json.load(f)
        except Exception:
            pass

    def get(self, k, default=None):
        return self.d.get(k, default)

    def put(self, k, v):
        self.d[k] = v
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.d, f)
        except Exception:
            pass


class Ctx:
    """What the worker thread needs: traffic key/radius/quota and the reference position."""

    def __init__(self, settings, ref):
        self.s, self.ref = settings, ref

    @property
    def key(self):
        return (self.s.get("tomtom_key", "") or "").strip()

    @property
    def radius_km(self):
        try:
            return max(5.0, min(200.0, float(self.s.get("radius_km", 50))))
        except Exception:
            return 50.0

    def budget(self):
        q = self.s.get("quota", {})
        used = q.get("used", 0) if q.get("date") == time.strftime("%Y-%m-%d") else 0
        return DAILY_TRAFFIC_BUDGET - used

    def add_usage(self, n):
        today = time.strftime("%Y-%m-%d")
        q = self.s.get("quota", {})
        used = (q.get("used", 0) if q.get("date") == today else 0) + n
        self.s.put("quota", {"date": today, "used": used})


def live_traffic(routes, mode, ctx, push, markers, notes):
    """Adds live delay to every road candidate; returns a one-line message for the status bar."""
    spec = MODES[mode]
    if spec["kind"] != "road" or spec["profile"] != "car":
        return ""
    if not ctx.key:
        return "Tip: add a free TomTom key in Settings to use live traffic."
    push(f"Checking live traffic within {ctx.radius_km:.0f} km...", routes, markers, notes)
    try:
        used = traffic.apply_traffic(routes, ctx.ref, ctx.key, ctx.radius_km * 1000, ctx.budget())
    except traffic.TrafficError as e:
        return f"Live traffic unavailable: {e}."
    except Exception:
        return "Live traffic unavailable (network problem)."
    ctx.add_usage(used)
    fb = min(range(len(routes)), key=lambda i: routes[i]["dur_free"])
    lb = min(range(len(routes)), key=lambda i: routes[i]["dur"])
    if len(routes) > 1 and lb != fb:
        saved = routes[fb]["dur"] - routes[lb]["dur"]
        return (f"Traffic ahead on {routes[fb]['label']}. {routes[lb]['label']} has less traffic "
                f"and is now fastest (saves {fmt_time(saved)}).")
    t = routes[lb].get("traffic") or {}
    if t.get("level"):
        return f"Live traffic (next {ctx.radius_km:.0f} km): {t['level'].lower()} on the fastest route."
    return "No live traffic data for this stretch."


def solve(plan, mode, ctx, push):
    """Worker thread. push(status, routes, markers, notes) updates the UI as each stage finishes."""
    t0 = time.time()
    spec = MODES[mode]
    names, pts = [], []
    for k, item in enumerate(plan):
        push(f"Finding places... ({k+1}/{len(plan)})", [], _mark(pts) if pts else [], "")
        if item["lat"] is not None:
            la, lo = item["lat"], item["lon"]             # picked from suggestions: no lookup needed
        else:
            la, lo, _ = geo.geocode(item["text"])          # typed by hand: Nominatim fallback (1 req/s)
        names.append(item["text"])
        pts.append((la, lo))
    n = len(pts)
    markers = _mark(pts)
    notes = spec["note"]
    ctx.ref = ctx.ref or pts[0]
    push(f"Places found. Getting {mode.lower()} routes...", [], markers, notes)

    def finish(routes, notes):
        for r in routes:                                   # coarse copy used for fast trip progress
            r["pcoords"] = r["lods"][3][1]
            r["pcum"] = trk.cumulative(r["pcoords"])
        msg = live_traffic(routes, mode, ctx, push, markers, notes)
        push(f"Done in {time.time()-t0:.1f}s. {msg}".strip(), routes, markers, notes)

    if n == 2:
        first = get_routes(mode, pts, False)
        routes = [dict(first[0], label="Route 1", order=[0, 1])]
        extra = " Looking for alternatives..." if spec["kind"] == "road" else ""
        push(f"Route found.{extra}", routes, markers, notes)
        if spec["kind"] == "road":
            opts = get_routes(mode, pts, True, timeout=40)
            if len(opts) > 1:
                routes = [dict(o, label=f"Route {i+1}", order=[0, 1]) for i, o in enumerate(opts)]
        if routes and not routes[0]["road"]:
            notes += "\n[color=ffb454]Road service unavailable - showing straight-line distance.[/color]"
        notes += f"\n\nDijkstra (shortest-path tree) A->B: 0 -> 1 = {fmt_km(min(r['dist'] for r in routes))}"
        finish(routes, notes)
        return

    if spec["kind"] == "road":
        m, src = geo.road_matrix(pts, spec["profile"])
    else:
        m, src = [[algos.haversine(a, b) for b in pts] for a in pts], "great-circle"
    A, B = 0, n - 1
    adj = algos.knn_graph(m, k=min(3, n - 1))
    dist, parent = algos.dijkstra(adj, A)
    path = algos.path_from_tree(parent, B)
    notes += (f"\n\nDijkstra (shortest-path tree) A->B: {' -> '.join(map(str, path))} = {fmt_km(dist[B])}"
              f"\nDistances: {src}")
    g = algos.greedy_nn(m, A, B)
    t = algos.mst_tsp(m, A, B)
    o2 = algos.two_opt(min((g, t), key=lambda o: algos.tour_len(o, m)), m)
    cands = [("Best tour (greedy/MST + 2-opt)", o2), ("Greedy tour", g), ("MST-tree tour", t)]
    mid = list(range(1, n - 1))
    if len(mid) <= 6:
        allp = sorted(([A] + list(p) + [B] for p in itertools.permutations(mid)),
                      key=lambda o: algos.tour_len(o, m))
        cands += [(f"Alternative order #{i+1}", o) for i, o in enumerate(allp[:4])]
    uniq, seen = [], set()
    for label, order in cands:
        if tuple(order) not in seen and len(seen) < 5:
            seen.add(tuple(order))
            uniq.append((label, order))
    label, order = uniq[0]
    o = get_routes(mode, [pts[i] for i in order])[0]
    routes = [dict(o, label=label, order=order)]
    push("Best tour found. Loading other orders...", routes, markers, notes)
    if len(uniq) > 1:
        with ThreadPoolExecutor(max_workers=4) as ex:
            res = list(ex.map(lambda lo_: get_routes(mode, [pts[i] for i in lo_[1]])[0], uniq[1:]))
        for (label, order), o in zip(uniq[1:], res):
            routes.append(dict(o, label=label, order=order))
    finish(routes, notes)


# ----------------------------------------------------------------------------- UI root
class Root(BoxLayout):
    busy = False

    def __init__(self, **kw):
        super().__init__(**kw)
        app = App.get_running_app()
        self.settings = Settings(os.environ.get("TARANG_DATA") or os.path.join(app.user_data_dir, "tarang.json"))
        self.header, self.form, self.results = Header(), Form(), Results()
        self.loader = Loader()
        self.fscroll = FormScroll(size_hint_y=None, do_scroll_x=False, bar_color=ACCENT, bar_width=dp(3))
        self.fscroll.add_widget(self.form)
        self.summary = NavButton(text="", bg=FIELD, size_hint_y=None, height=0, opacity=0, disabled=True,
                                 font_size="13sp", halign="left", shorten=True, shorten_from="right")
        self.summary.bind(on_release=lambda *_: self.set_collapsed(False),
                          size=lambda w, s: setattr(w, "text_size", (s[0] - dp(24), None)))
        self.map = MapView(lat=22.5, lon=79.0, zoom=4)
        self.layer = RouteLayer()
        self.left = BoxLayout(orientation="vertical")
        self.routes, self.fast_i, self.short_i, self.sel = [], -1, -1, -1
        self.manual_sel, self.collapsed, self._orient = False, False, None
        self._markers, self._notes, self._fitkey = [], "", None
        self.me, self.pending_from = None, None
        self.tracking, self.tracker = False, None
        self.gps = GPSProvider(self.on_fix, self.on_gps_status)
        Clock.schedule_once(lambda dt: self.map.add_layer(self.layer), 0)
        self.form.bind(height=lambda *a: self._fit_form())
        self.bind(size=lambda *a: (self.relayout(), self._fit_form()))
        self.relayout()
        Clock.schedule_once(lambda dt: self.gps.start(), 1.0)

    # ---- layout
    def relayout(self):
        land = self.width > self.height * 1.15 and self.width > 0
        if land == self._orient:
            return
        self._orient = land
        for w in (self.header, self.loader, self.summary, self.fscroll, self.results, self.map, self.left):
            if w.parent:
                w.parent.remove_widget(w)
        self.clear_widgets()
        if land:
            self.orientation = "horizontal"
            self.left.size_hint = (0.44, 1)
            self.left.clear_widgets()
            for w in (self.header, self.loader, self.summary, self.fscroll, self.results):
                self.left.add_widget(w)
            self.results.size_hint_y = 1
            self.map.size_hint = (0.56, 1)
            self.add_widget(self.left)
            self.add_widget(self.map)
        else:
            self.orientation = "vertical"
            self.results.size_hint_y = None
            self.results.height = dp(300)
            self.map.size_hint = (1, 1)
            for w in (self.header, self.loader, self.summary, self.fscroll, self.map, self.results):
                self.add_widget(w)

    def _fit_form(self):
        if self.collapsed:
            self.fscroll.height, self.fscroll.opacity, self.fscroll.disabled = 0, 0, True
            return
        cap = Window.height * (0.62 if self._orient else 0.46)
        self.fscroll.height = min(self.form.height, cap)
        self.fscroll.opacity, self.fscroll.disabled = 1, False

    def set_collapsed(self, c):
        self.collapsed = c
        self.summary.height, self.summary.opacity, self.summary.disabled = (dp(42), 1, False) if c else (0, 0, True)
        self._fit_form()

    def bias(self):
        if self.me:
            return (self.me["lat"], self.me["lon"])
        return (self.map.lat, self.map.lon)

    # ---- GPS
    def on_gps_status(self, text):
        if not self.busy and not self.tracking:
            self.results.ids.status.text = text

    def on_fix(self, fix):
        first = self.me is None
        self.me = fix
        self.layer.me = fix
        if first and not self.routes:
            self.map.center_on(fix["lat"], fix["lon"])
            self.map.zoom = 12
            self.results.ids.status.text = "GPS fix acquired."
        if self.pending_from is not None:
            pf, self.pending_from = self.pending_from, None
            self.use_my_location(pf)
        if self.tracking:
            self.tracker.add_fix(fix["lat"], fix["lon"], fix["t"], fix.get("acc"))
            self.layer.trail = self.tracker.path
            self._update_stats(fix)
        self.layer.reposition()

    def use_my_location(self, pf):
        if self.me:
            pf.set_place(f"My location ({self.me['lat']:.4f}, {self.me['lon']:.4f})", self.me["lat"], self.me["lon"])
            self.map.center_on(self.me["lat"], self.me["lon"])
        else:
            self.pending_from = pf
            self.results.ids.status.text = "Waiting for a GPS fix..."
            self.gps.start()

    # ---- trip tracking
    def toggle_trip(self):
        self.stop_trip() if self.tracking else self.start_trip()

    def start_trip(self):
        if not self.me:
            self.results.ids.status.text = "No GPS fix yet. Go outside or wait a few seconds, then try again."
            self.gps.start()
            return
        self.tracker = trk.Tracker()
        self.tracker.add_fix(self.me["lat"], self.me["lon"], time.time(), self.me.get("acc"))
        self.tracking = True
        self.layer.trail = self.tracker.path
        self.results.ids.tripbtn.text, self.results.ids.tripbtn.bg = "Stop trip", (0.78, 0.22, 0.27, 1)
        self._tick_ev = Clock.schedule_interval(lambda dt: self._update_stats(None), 1.0)
        self._traffic_ev = Clock.schedule_interval(lambda dt: self.refresh_traffic(), 600)
        keep_screen_on(True)
        self.results.ids.status.text = "Trip started. Keep the app open while travelling."

    def stop_trip(self):
        self.tracking = False
        for ev in (getattr(self, "_tick_ev", None), getattr(self, "_traffic_ev", None)):
            if ev:
                ev.cancel()
        keep_screen_on(False)
        mode = self.form.ids.mode.text
        s = self.tracker.summary(mode)
        if s["distance_m"] > 20:
            trips = self.settings.get("trips", [])
            trips.append(s)
            self.settings.put("trips", trips[-50:])
        self.results.ids.tripbtn.text, self.results.ids.tripbtn.bg = "Start trip", FIELD
        self.results.ids.status.text = (f"Trip saved: {fmt_km(s['distance_m'])} in {fmt_clock(s['duration_s'])} "
                                        f"(avg {s['avg_kmh']:.0f} km/h).")

    def _update_stats(self, fix):
        tr, now = self.tracker, time.time()
        ids = self.results.ids
        ids.s_dist.value = fmt_km(tr.dist)
        ids.s_time.value = fmt_clock(tr.elapsed(now))
        ids.s_avg.value = f"{tr.avg_kmh(now):.0f} km/h"
        me = fix or self.me
        if me and 0 <= self.sel < len(self.routes) and "pcum" in self.routes[self.sel]:
            r = self.routes[self.sel]
            done, rem, off = trk.locate(r["pcoords"], r["pcum"], (me["lat"], me["lon"]))
            frac = done / r["pcum"][-1] if r["pcum"][-1] else 0
            left_m = r["dist"] * (1 - frac)
            v = tr.avg_kmh(now) / 3.6 if (tr.elapsed(now) > 180 and tr.dist > 500) else None
            eta = left_m / v if v else (r["dur"] or 0) * (1 - frac)
            ids.status.text = (f"{frac*100:.0f}% done  |  {fmt_km(left_m)} to go  |  ETA {fmt_time(eta)}"
                               + ("  |  [color=fbbf24]off route[/color]" if off > 600 else ""))

    def refresh_traffic(self):
        ctx = Ctx(self.settings, (self.me["lat"], self.me["lon"]) if self.me else None)
        if self.busy or not self.routes or not ctx.key or not self.routes[0].get("road"):
            return
        routes, markers, notes = self.routes, self._markers, self._notes
        mode = self.form.ids.mode.text

        def work():
            msg = live_traffic(routes, mode, ctx, lambda *a: None, markers, notes)
            Clock.schedule_once(lambda dt: self.show(msg, routes, markers, notes))
        threading.Thread(target=work, daemon=True).start()

    # ---- popups
    def _popup(self, title, content, height):
        p = Popup(title=title, content=content, size_hint=(0.92, None), height=height, background="",
                  background_color=(0.04, 0.12, 0.27, 0.98), separator_color=ACCENT, title_color=(1, 1, 1, 1))
        p.open()
        return p

    def open_settings(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(4), size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        box.add_widget(Factory.NoteLabel(text=(
            "[b]Live traffic[/b] needs a free TomTom key (no card): sign up at developer.tomtom.com, "
            "create a key and paste it here. Free tier: 2,500 requests/day. Each search uses about 8-24.")))
        key = Factory.NavInput(text=self.settings.get("tomtom_key", ""), hint_text="TomTom API key")
        rad = Factory.NavInput(text=str(self.settings.get("radius_km", 50)), hint_text="Traffic radius in km (default 50)",
                               input_filter="float")
        box.add_widget(key)
        box.add_widget(rad)
        q = self.settings.get("quota", {})
        used = q.get("used", 0) if q.get("date") == time.strftime("%Y-%m-%d") else 0
        box.add_widget(Factory.NoteLabel(text=f"Traffic requests used today: {used} / 2,500"))
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        cancel, save = NavButton(text="Cancel", bg=FIELD), NavButton(text="Save")
        row.add_widget(cancel)
        row.add_widget(save)
        box.add_widget(row)
        pop = self._popup("Settings", box, dp(300))
        box.bind(height=lambda w, h: setattr(pop, "height", h + dp(92)))

        def do_save(*_):
            self.settings.put("tomtom_key", key.text.strip())
            try:
                self.settings.put("radius_km", float(rad.text or 50))
            except ValueError:
                pass
            pop.dismiss()
            self.results.ids.status.text = "Settings saved."
        save.bind(on_release=do_save)
        cancel.bind(on_release=lambda *_: pop.dismiss())

    def open_trips(self):
        trips = list(reversed(self.settings.get("trips", [])))
        col = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        col.bind(minimum_height=col.setter("height"))
        if not trips:
            col.add_widget(Factory.NoteLabel(text="No trips yet. Tap Start trip while travelling."))
        for t in trips:
            when = time.strftime("%d %b %Y, %H:%M", time.localtime(t["when"])) if t.get("when") else ""
            col.add_widget(Factory.NoteLabel(text=(
                f"[b][color=ffffff]{fmt_km(t['distance_m'])}[/color][/b] in {fmt_clock(t['duration_s'])}   "
                f"avg {t['avg_kmh']:.0f} km/h   {t.get('mode','')}\n{when}"), height=dp(46)))
        sv = ScrollView()
        sv.add_widget(col)
        self._popup("Past trips", sv, dp(420))

    # ---- searching
    def run(self):
        if self.busy:
            return
        fields = [pf for pf in self.form.fields() if pf.text or pf in (self.form.ids.a, self.form.ids.b)]
        if not self.form.ids.a.text or not self.form.ids.b.text:
            self.results.ids.status.text = "Please enter both From and To."
            return
        plan = [{"text": pf.text, "lat": pf.lat, "lon": pf.lon} for pf in fields]
        mode = self.form.ids.mode.text
        ctx = Ctx(self.settings, (self.me["lat"], self.me["lon"]) if self.me else None)
        self.busy, self.manual_sel = True, False
        self.loader.start()
        stops = len(plan) - 2
        short = lambda t: t.split(",")[0].strip()[:24]
        self.summary.text = (f"{short(plan[0]['text'])}  >  {short(plan[-1]['text'])}"
                             + (f"  +{stops} stop{'s' if stops != 1 else ''}" if stops else "") + f"   |   {mode}   (tap to edit)")
        self.set_collapsed(True)
        for pf in self.form.fields():
            pf.ids.ti.focus = False
        self.results.ids.status.text = "Working..."

        def push(status, routes, markers, notes):
            Clock.schedule_once(lambda dt: self.show(status, routes, markers, notes))

        def work():
            try:
                solve(plan, mode, ctx, push)
            except Exception as e:
                push(f"Error: {e}", [], [], "")
            finally:
                Clock.schedule_once(lambda dt: self._done())
        threading.Thread(target=work, daemon=True).start()

    def _done(self):
        self.busy = False
        self.loader.stop()

    # ---- showing results
    def show(self, status, routes, markers, notes):
        if not self.tracking or "Trip" not in status:
            self.results.ids.status.text = status
        self._markers, self._notes = markers, notes
        self.routes = routes
        self._tag()
        if routes and (not self.manual_sel or not 0 <= self.sel < len(routes)):
            self.sel = self.fast_i                       # live traffic can change which one is fastest
        self._rebuild_cards(notes)
        self._apply_selection(fit=(id(routes), len(markers)) != self._fitkey)
        self._fitkey = (id(routes), len(markers))

    def _tag(self):
        rs = self.routes
        if not rs:
            self.fast_i = self.short_i = -1
            return
        self.fast_i = min(range(len(rs)), key=lambda i: rs[i]["dur"] if rs[i]["dur"] is not None else rs[i]["dist"])
        self.short_i = min(range(len(rs)), key=lambda i: rs[i]["dist"])

    def _rebuild_cards(self, notes):
        box = self.results.ids.cards
        box.clear_widgets()
        order = sorted(range(len(self.routes)),
                       key=lambda i: (i != self.fast_i, i != self.short_i, self.routes[i]["dist"]))
        for i in order:
            r = self.routes[i]
            tags = [t for t, ix in (("Fastest", self.fast_i), ("Shortest", self.short_i)) if ix == i]
            multi = len(self.routes) > 1 and len(r.get("order", [])) > 2
            title = " + ".join(tags) if tags else "Alternative"
            if len(self.routes) > 1 and not multi:
                title += f"  [size=12sp][color=a8c4ee]{r.get('label','')}[/color][/size]"
            if multi:
                title += f"  [size=12sp][color=a8c4ee]{r['label']}[/color][/size]"
            sub = f"{fmt_time(r['dur'])}   |   {fmt_km(r['dist'])}"
            tt = traffic_text(r)
            if tt:
                sub += "   |   " + tt
            if r.get("est"):
                sub += "   |   estimate"
            if multi:
                sub += "\n" + " > ".join(map(str, r["order"]))
            c = RouteCard(title=title, sub=sub, selected=(i == self.sel))
            c.idx = i
            c.bind(on_release=lambda w: self.select(w.idx, manual=True))
            c.opacity = 0
            box.add_widget(c)
            Animation(opacity=1, d=0.25).start(c)
        if notes:
            box.add_widget(Factory.NoteLabel(text=notes))
        self._style_toggle()

    def _style_toggle(self):
        ids = self.results.ids
        ids.bfast.bg = ACCENT if (self.sel >= 0 and self.sel == self.fast_i) else PANEL
        ids.bshort.bg = ACCENT if (self.sel >= 0 and self.sel == self.short_i) else PANEL

    def select_kind(self, kind):
        i = self.fast_i if kind == "fast" else self.short_i
        if i >= 0:
            self.select(i, manual=True)

    def select(self, i, manual=False):
        self.sel = i
        self.manual_sel = self.manual_sel or manual
        for c in self.results.ids.cards.children:
            if isinstance(c, RouteCard):
                c.selected = (c.idx == i)
        self._style_toggle()
        self._apply_selection(fit=False)

    def _apply_selection(self, fit):
        for i, r in enumerate(self.routes):
            r["selected"] = (i == self.sel)
        self.layer.set_data(self.routes, self._markers)
        if fit and (self.routes or self._markers):
            self.fit()

    def fit(self):
        mv = self.map
        lats = [m[0] for m in self._markers]
        lons = [m[1] for m in self._markers]
        for r in self.routes:
            c = r["lods"][2][1]
            lats += [p[0] for p in c]
            lons += [p[1] for p in c]
        if not lats:
            return
        clat, clon = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
        dlon = max(max(lons) - min(lons), 1e-4)
        dlat = max((max(lats) - min(lats)) / max(math.cos(math.radians(clat)), 0.2), 1e-4)
        zl = math.log2(max(mv.width, 100) * 360 / (256 * dlon))
        zt = math.log2(max(mv.height, 100) * 360 / (256 * dlat))
        mv.zoom = int(max(3, min(17, math.floor(min(zl, zt) - 0.4))))
        mv.center_on(clat, clon)
        Clock.schedule_once(lambda dt: self.layer.reposition(), 0.2)


class TarangNavApp(App):
    title = "Tarang Nav"
    icon = os.path.join(HERE, "icon.png")

    def build(self):
        Window.clearcolor = NAVY
        Window.softinput_mode = "below_target"
        Builder.load_string(KV)
        return Root()

    def on_pause(self):
        return True                                       # keep running (and tracking) when minimised


if __name__ == "__main__":
    TarangNavApp().run()
