"""Tarang Nav - multi-mode route finder (free OpenStreetMap / OSRM services only)."""
import itertools
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
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.spinner import SpinnerOption  # noqa: F401  (styled in KV)
from kivy.uix.widget import Widget
from kivy_garden.mapview import MapLayer, MapView

import algos
import geo
from modes import MODES, MODE_NAMES

HERE = os.path.dirname(os.path.abspath(__file__))

NAVY = (0.039, 0.122, 0.267, 1)        # #0A1F44
SEL_COLOR = (0.10, 0.45, 1.0, 1)       # selected route (bright blue)
ALT_COLOR = (0.45, 0.55, 0.72, 0.85)   # other routes

KV = """
#:set NAVY (0.039, 0.122, 0.267, 1)
#:set PANEL (0.067, 0.176, 0.369, 1)
#:set FIELD (0.094, 0.231, 0.463, 1)
#:set ACCENT (0.133, 0.827, 0.929, 1)
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
    spacing: dp(10)
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

<Form>:
    orientation: 'vertical'
    size_hint_y: None
    height: self.minimum_height
    padding: dp(10), dp(10), dp(10), dp(6)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: NAVY
        Rectangle:
            pos: self.pos
            size: self.size
    NavInput:
        id: a
        hint_text: 'From  (e.g. Bengaluru)'
    NavInput:
        id: b
        hint_text: 'To  (e.g. New Delhi)'
    NavInput:
        id: stops
        hint_text: 'Extra stops (optional), separated by ;'
    BoxLayout:
        size_hint_y: None
        height: dp(46)
        spacing: dp(8)
        NavSpinner:
            id: mode
            text: 'Car'
            values: root.mode_names
            size_hint_x: 0.55
        NavButton:
            text: 'Find routes'
            size_hint_x: 0.45
            on_release: root.go()

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
        text: 'Choose a mode, enter two places and tap Find routes.'
        size_hint_y: None
        height: dp(22)
        font_size: '12.5sp'
        color: MUTED
        halign: 'left'
        text_size: self.size
        shorten: True
        shorten_from: 'right'
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
    height: dp(62)
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
        font_size: '13sp'
        color: ACCENT if root.selected else MUTED
        halign: 'left'
        valign: 'top'
        text_size: self.size
        shorten: True
        shorten_from: 'right'
"""


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


class Form(BoxLayout):
    mode_names = MODE_NAMES

    def go(self):
        App.get_running_app().root.run()


class Results(BoxLayout):
    pass


class RouteCard(ButtonBehavior, BoxLayout):
    selected = BooleanProperty(False)
    title = StringProperty("")
    sub = StringProperty("")


class RouteLayer(MapLayer):
    """All candidate routes (thin) + the selected one (thick blue) + A/B/stop markers.
    Uses pre-simplified zoom levels and viewport culling so 2,000 km routes stay smooth."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.routes, self.markers = [], []

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
                est = r.get("est")
                for run in runs:
                    pts = []
                    for la, lo in run:
                        x, y = mv.get_window_xy_from(la, lo, z)
                        pts += [x, y]
                    if len(pts) < 4:
                        continue
                    pieces = dash_pieces(pts, dp(11), dp(7)) if est else [pts]
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


def solve(a_txt, b_txt, stops_txt, mode, push):
    """Worker thread. push(status, routes, markers, notes) updates the UI as each stage finishes."""
    t0 = time.time()
    spec = MODES[mode]
    labels = [a_txt] + [x for x in stops_txt.replace("\n", ";").split(";") if x.strip()] + [b_txt]
    names, pts = [], []
    for k, t in enumerate(labels):
        push(f"Finding places... ({k+1}/{len(labels)})", [], _mark(pts) if pts else [], "")
        la, lo, _ = geo.geocode(t.strip())          # sequential: Nominatim allows 1 request/second
        names.append(t.strip())
        pts.append((la, lo))
    n = len(pts)
    markers = _mark(pts)
    notes = spec["note"]
    push(f"Places found. Getting {mode.lower()} routes...", [], markers, notes)

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
        d = min(r["dist"] for r in routes)
        notes += f"\n\nDijkstra (shortest-path tree) A->B: 0 -> 1 = {fmt_km(d)}"
        push(f"Done in {time.time()-t0:.1f}s", routes, markers, notes)
        return

    # ---- several stops: tree + greedy + 2-opt tour search ----
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
    push(f"Done in {time.time()-t0:.1f}s", routes, markers, notes)


# ----------------------------------------------------------------------------- UI root
class Root(BoxLayout):
    busy = False

    def __init__(self, **kw):
        super().__init__(**kw)
        self.header, self.form, self.results = Header(), Form(), Results()
        self.loader = Loader()
        self.map = MapView(lat=22.5, lon=79.0, zoom=4)
        self.layer = RouteLayer()
        self.left = BoxLayout(orientation="vertical")
        self.routes, self.fast_i, self.short_i, self.sel = [], -1, -1, -1
        self._orient = None
        Clock.schedule_once(lambda dt: self.map.add_layer(self.layer), 0)
        self.bind(size=lambda *a: self.relayout())
        self.relayout()

    # --- responsive layout: portrait = stacked, landscape = side-by-side
    def relayout(self):
        land = self.width > self.height * 1.15 and self.width > 0
        if land == self._orient:
            return
        self._orient = land
        for w in (self.header, self.loader, self.form, self.results, self.map, self.left):
            if w.parent:
                w.parent.remove_widget(w)
        self.clear_widgets()
        if land:
            self.orientation = "horizontal"
            self.left.size_hint = (0.42, 1)
            self.left.clear_widgets()
            for w in (self.header, self.loader, self.form, self.results):
                self.left.add_widget(w)
            self.results.size_hint_y = 1
            self.map.size_hint = (0.58, 1)
            self.add_widget(self.left)
            self.add_widget(self.map)
        else:
            self.orientation = "vertical"
            self.results.size_hint_y = None
            self.results.height = dp(235)
            self.map.size_hint = (1, 1)
            for w in (self.header, self.loader, self.form, self.map, self.results):
                self.add_widget(w)

    # --- actions
    def run(self):
        if self.busy:
            return
        f = self.form.ids
        a, b, stops, mode = f.a.text, f.b.text, f.stops.text, f.mode.text
        if not a.strip() or not b.strip():
            self.results.ids.status.text = "Please enter both From and To."
            return
        self.busy = True
        self.loader.start()
        self.results.ids.status.text = "Working..."

        def push(status, routes, markers, notes):
            Clock.schedule_once(lambda dt: self.show(status, routes, markers, notes))

        def work():
            try:
                solve(a, b, stops, mode, push)
            except Exception as e:
                push(f"Error: {e}", [], [], "")
            finally:
                Clock.schedule_once(lambda dt: self._done())
        threading.Thread(target=work, daemon=True).start()

    def _done(self):
        self.busy = False
        self.loader.stop()

    def show(self, status, routes, markers, notes):
        self.results.ids.status.text = status
        if routes != self.routes:
            self.routes = routes
            self._tag()
            self.sel = self.fast_i if routes else -1
        self._rebuild_cards(notes)
        self._apply_selection(fit=True, markers=markers)

    def _tag(self):
        rs = self.routes
        if not rs:
            self.fast_i = self.short_i = -1
            return
        key_t = lambda i: rs[i]["dur"] if rs[i]["dur"] is not None else rs[i]["dist"]
        self.fast_i = min(range(len(rs)), key=key_t)
        self.short_i = min(range(len(rs)), key=lambda i: rs[i]["dist"])

    def _rebuild_cards(self, notes):
        box = self.results.ids.cards
        box.clear_widgets()
        order = sorted(range(len(self.routes)),
                       key=lambda i: (i != self.fast_i, i != self.short_i, self.routes[i]["dist"]))
        for i in order:
            r = self.routes[i]
            tags = [t for t, ix in (("Fastest", self.fast_i), ("Shortest", self.short_i)) if ix == i]
            multi = len(self.routes) > 1 and "order" in r and len(r["order"]) > 2
            title = " + ".join(tags) if tags else "Alternative"
            if multi:
                title += f"  [size=12sp][color=a8c4ee]{r['label']}[/color][/size]"
            sub = f"{fmt_time(r['dur'])}   |   {fmt_km(r['dist'])}"
            if r.get("est"):
                sub += "   |   estimate"
            if multi:
                sub += "   |   " + " > ".join(map(str, r["order"]))
            c = RouteCard(title=title, sub=sub, selected=(i == self.sel))
            c.idx = i
            c.bind(on_release=lambda w: self.select(w.idx))
            c.opacity = 0
            box.add_widget(c)
            Animation(opacity=1, d=0.25).start(c)
        if notes:
            n = Factory.NoteLabel(text=notes)
            box.add_widget(n)
        self._style_toggle()

    def _style_toggle(self):
        ids = self.results.ids
        from kivy.utils import get_color_from_hex
        acc, pan = (0.133, 0.827, 0.929, 1), (0.067, 0.176, 0.369, 1)
        ids.bfast.bg = acc if (self.sel >= 0 and self.sel == self.fast_i) else pan
        ids.bshort.bg = acc if (self.sel >= 0 and self.sel == self.short_i) else pan

    def select_kind(self, kind):
        i = self.fast_i if kind == "fast" else self.short_i
        if i >= 0:
            self.select(i)

    def select(self, i):
        self.sel = i
        for c in self.results.ids.cards.children:
            if isinstance(c, RouteCard):
                c.selected = (c.idx == i)
        self._style_toggle()
        self._apply_selection(fit=False)

    def _apply_selection(self, fit, markers=None):
        for i, r in enumerate(self.routes):
            r["selected"] = (i == self.sel)
        if markers is not None:
            self._markers = markers
        self.layer.set_data(self.routes, getattr(self, "_markers", []))
        if fit and (self.routes or getattr(self, "_markers", [])):
            self.fit()

    def fit(self):
        mv = self.map
        lats = [m[0] for m in self._markers]
        lons = [m[1] for m in self._markers]
        for r in self.routes:
            c = r["lods"][2][1]          # coarse level is plenty for bounds
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


if __name__ == "__main__":
    TarangNavApp().run()
