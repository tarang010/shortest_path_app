import itertools
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy_garden.mapview import MapLayer, MapView  # noqa: F401  (MapView is used from KV)

import algos
import geo

KV = """
<Root>:
    orientation: 'vertical'
    padding: dp(8)
    spacing: dp(6)
    TextInput:
        id: a
        hint_text: 'Point A (e.g. India Gate, New Delhi)'
        multiline: False
        size_hint_y: None
        height: dp(42)
    TextInput:
        id: b
        hint_text: 'Point B (e.g. Qutub Minar, New Delhi)'
        multiline: False
        size_hint_y: None
        height: dp(42)
    TextInput:
        id: stops
        hint_text: 'Optional extra stops, one per line'
        size_hint_y: None
        height: dp(64)
    Button:
        text: 'Find shortest path'
        size_hint_y: None
        height: dp(46)
        on_release: root.run(a.text, b.text, stops.text)
    MapView:
        id: map
        lat: 28.6139
        lon: 77.2090
        zoom: 10
        size_hint_y: 1.2
    ScrollView:
        size_hint_y: 0.8
        Label:
            id: out
            text: 'Enter two places and tap the button.'
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
            halign: 'left'
            valign: 'top'
            markup: True
"""

BEST_COLOR = (0.05, 0.65, 0.2, 1)
OTHER_COLOR = (0.35, 0.5, 0.85, 0.75)


class RouteLayer(MapLayer):
    """Draws every candidate route (thin blue) and the shortest one (thick green) + markers."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.routes = []
        self.markers = []   # (lat, lon, label, rgb)

    def set_data(self, routes, markers):
        self.routes, self.markers = routes, markers
        self.reposition()

    def reposition(self):
        mv = self.parent
        if mv is None:
            return
        self.canvas.clear()
        z = mv.zoom
        with self.canvas:
            for r in sorted(self.routes, key=lambda r: r["best"]):   # best drawn last = on top
                pts = []
                for la, lo in r["coords"]:
                    x, y = mv.get_window_xy_from(la, lo, z)
                    pts += [x, y]
                if len(pts) < 4:
                    continue
                if r["best"]:
                    Color(1, 1, 1, 1)
                    Line(points=pts, width=dp(4.5), joint="round", cap="round")
                    Color(*BEST_COLOR)
                    Line(points=pts, width=dp(3), joint="round", cap="round")
                else:
                    Color(*OTHER_COLOR)
                    Line(points=pts, width=dp(2), joint="round", cap="round")
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


def km(x):
    return f"{x/1000:.2f} km"


def _mark(pts):
    n = len(pts)
    out = []
    for i, p in enumerate(pts):
        rgb = (0.1, 0.6, 0.2) if i == 0 else (0.85, 0.15, 0.15) if i == n - 1 else (0.2, 0.3, 0.8)
        out.append((p[0], p[1], "A" if i == 0 else "B" if i == n - 1 else str(i), rgb))
    return out


def _flag_best(routes):
    best = min(range(len(routes)), key=lambda i: routes[i]["dist"])
    for i, r in enumerate(routes):
        r["best"] = (i == best)


def _report(names, routes, n, dijkstra_line, status=""):
    L = []
    for i, nm in enumerate(names):
        L.append(f"[{i}] {nm}")
    L += ["", dijkstra_line, "", "Candidate routes (green = shortest):"]
    for r in sorted(routes, key=lambda r: r["dist"]):
        mins = f", {r['dur']/3600:.1f} h" if r["dur"] else ""
        tag = "[b][color=0aa633]SHORTEST[/color][/b] " if r["best"] else ""
        seq = " -> ".join(map(str, r["order"])) if n > 2 else ""
        kind = "" if r["road"] else " (straight-line, road service unavailable)"
        L.append(f"  {tag}{r['label']}: {km(r['dist'])}{mins} {seq}{kind}")
    if status:
        L += ["", status]
    return "\n".join(L)


def solve(a_txt, b_txt, stops_txt, push):
    """Runs in a worker thread. push(text, routes, markers) updates the UI as stages finish."""
    t0 = time.time()
    labels = [a_txt] + [x for x in stops_txt.splitlines() if x.strip()] + [b_txt]
    names, pts = [], []
    for k, t in enumerate(labels):
        push(f"Finding places... ({k+1}/{len(labels)})", [], _mark(pts) if pts else [])
        la, lo, _ = geo.geocode(t.strip())          # sequential on purpose: Nominatim allows 1 req/s
        names.append(t.strip())
        pts.append((la, lo))
    n = len(pts)
    markers = _mark(pts)
    push("Places found. Getting road routes...", [], markers)

    if n == 2:
        # one fast request first (no alternatives) -> show the main route immediately
        first = geo.route_options(pts, alternatives=False)
        routes = [dict(first[0], label="Route 1", order=[0, 1])]
        _flag_best(routes)
        d = routes[0]["dist"]
        dline = f"Dijkstra (shortest-path tree) A->B: 0 -> 1 = {km(d)}"
        push(_report(names, routes, n, dline, "Looking for alternative routes..."), routes, markers)
        opts = geo.route_options(pts, alternatives=True, timeout=40)
        if len(opts) > 1:
            routes = [dict(o, label=f"Route {i+1}", order=[0, 1]) for i, o in enumerate(opts)]
            _flag_best(routes)
            dline = f"Dijkstra (shortest-path tree) A->B: 0 -> 1 = {km(min(r['dist'] for r in routes))}"
        status = f"Done in {time.time()-t0:.1f}s" + ("" if len(opts) > 1 else " (no alternative routes found)")
        push(_report(names, routes, n, dline, status), routes, markers)
        return

    A, B = 0, n - 1
    m, src = geo.road_matrix(pts)
    adj = algos.knn_graph(m, k=min(3, n - 1))
    dist, parent = algos.dijkstra(adj, A)
    path = algos.path_from_tree(parent, B)
    dline = ("Dijkstra (shortest-path tree) A->B: " + " -> ".join(map(str, path)) + f" = {km(dist[B])}"
             + f"   [distances: {src}]")

    g = algos.greedy_nn(m, A, B)
    t = algos.mst_tsp(m, A, B)
    o2 = algos.two_opt(min((g, t), key=lambda o: algos.tour_len(o, m)), m)
    cands = [("Greedy/MST + 2-opt", o2), ("Greedy tour", g), ("MST-tree tour", t)]
    mid = list(range(1, n - 1))
    if len(mid) <= 6:   # small case: also try every visiting order, keep the best few
        allp = sorted(([A] + list(p) + [B] for p in itertools.permutations(mid)),
                      key=lambda o: algos.tour_len(o, m))
        cands += [(f"Alternative order #{i+1}", o) for i, o in enumerate(allp[:4])]
    uniq, seen = [], set()
    for label, order in cands:
        if tuple(order) not in seen and len(seen) < 5:
            seen.add(tuple(order))
            uniq.append((label, order))

    # best candidate first -> show it right away; the rest are fetched in parallel
    label, order = uniq[0]
    o = geo.route_options([pts[i] for i in order])[0]
    routes = [dict(o, label=label, order=order)]
    _flag_best(routes)
    push(_report(names, routes, n, dline, "Loading other candidate routes..."), routes, markers)
    if len(uniq) > 1:
        with ThreadPoolExecutor(max_workers=4) as ex:
            res = list(ex.map(lambda lo: geo.route_options([pts[i] for i in lo[1]])[0], uniq[1:]))
        for (label, order), o in zip(uniq[1:], res):
            routes.append(dict(o, label=label, order=order))
        _flag_best(routes)
    push(_report(names, routes, n, dline, f"Done in {time.time()-t0:.1f}s"), routes, markers)


class Root(BoxLayout):
    busy = False

    def __init__(self, **kw):
        super().__init__(**kw)
        self.layer = RouteLayer()
        Clock.schedule_once(lambda dt: self.ids.map.add_layer(self.layer), 0)

    def run(self, a, b, stops):
        if self.busy:
            return
        if not a.strip() or not b.strip():
            self.ids.out.text = "Please fill both Point A and Point B."
            return
        self.busy = True
        self.ids.out.text = "Working..."

        def push(text, routes, markers):
            Clock.schedule_once(lambda dt: self.show(text, routes, markers))

        def work():
            try:
                solve(a, b, stops, push)
            except Exception as e:
                push(f"Error: {e}", [], [])
            finally:
                Clock.schedule_once(lambda dt: setattr(self, "busy", False))
        threading.Thread(target=work, daemon=True).start()

    def show(self, text, routes, markers):
        self.ids.out.text = text
        self.layer.set_data(routes, markers)
        if routes or markers:
            self.fit(routes, markers)

    def fit(self, routes, markers):
        mv = self.ids.map
        lats = [c[0] for r in routes for c in r["coords"]] + [m[0] for m in markers]
        lons = [c[1] for r in routes for c in r["coords"]] + [m[1] for m in markers]
        clat, clon = (min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2
        dlon = max(max(lons) - min(lons), 1e-4)
        dlat = max((max(lats) - min(lats)) / max(math.cos(math.radians(clat)), 0.2), 1e-4)
        zl = math.log2(max(mv.width, 100) * 360 / (256 * dlon))
        zt = math.log2(max(mv.height, 100) * 360 / (256 * dlat))
        mv.zoom = int(max(3, min(17, math.floor(min(zl, zt) - 0.4))))
        mv.center_on(clat, clon)
        Clock.schedule_once(lambda dt: self.layer.reposition(), 0.2)


class PathApp(App):
    def build(self):
        Builder.load_string(KV)
        return Root()


if __name__ == "__main__":
    PathApp().run()