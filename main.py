import threading
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout

import algos
import geo

KV = """
<Root>:
    orientation: 'vertical'
    padding: dp(10)
    spacing: dp(8)
    Label:
        text: 'Shortest Path Finder'
        font_size: '22sp'
        size_hint_y: None
        height: dp(40)
    TextInput:
        id: a
        hint_text: 'Point A (e.g. India Gate, New Delhi)'
        multiline: False
        size_hint_y: None
        height: dp(44)
    TextInput:
        id: b
        hint_text: 'Point B (e.g. Qutub Minar, New Delhi)'
        multiline: False
        size_hint_y: None
        height: dp(44)
    TextInput:
        id: stops
        hint_text: 'Optional extra stops, one per line (for TSP)'
        size_hint_y: None
        height: dp(90)
    Button:
        text: 'Find shortest path'
        size_hint_y: None
        height: dp(50)
        on_release: root.run(a.text, b.text, stops.text)
    ScrollView:
        Label:
            id: out
            text: 'Enter two places and tap the button.'
            size_hint_y: None
            height: self.texture_size[1]
            text_size: self.width, None
            halign: 'left'
            valign: 'top'
"""


def km(x):
    return f"{x/1000:.2f} km"


def solve(a_txt, b_txt, stops_txt):
    names, pts = [], []
    for t in [a_txt] + [s for s in stops_txt.splitlines() if s.strip()] + [b_txt]:
        la, lo, disp = geo.geocode(t.strip())
        names.append(t.strip())
        pts.append((la, lo))
    n = len(pts)
    A, B = 0, n - 1
    m, src = geo.road_matrix(pts)
    L = []
    L.append(f"Distance source: {src}\n")
    for i, (nm, p) in enumerate(zip(names, pts)):
        L.append(f"[{i}] {nm}  ({p[0]:.4f}, {p[1]:.4f})")
    L.append("")
    d, dur = geo.road_route(pts[A], pts[B])
    if d:
        L.append(f"Direct road route A->B: {km(d)}, {dur/60:.0f} min\n")

    # 1. Dijkstra on k-nearest graph (shortest-path TREE)
    adj = algos.knn_graph(m, k=min(3, n - 1))
    dist, parent = algos.dijkstra(adj, A)
    path = algos.path_from_tree(parent, B)
    L.append("1) Dijkstra (shortest path tree) A->B:")
    L.append("   " + " -> ".join(map(str, path)) + f"   = {km(dist[B])}\n")

    if n > 2:
        # 2. Greedy nearest neighbour TSP
        g = algos.greedy_nn(m, A, B)
        L.append("2) Greedy nearest-neighbour tour (visit all, end at B):")
        L.append("   " + " -> ".join(map(str, g)) + f"   = {km(algos.tour_len(g, m))}\n")
        # 3. MST (tree) based TSP
        t = algos.mst_tsp(m, A, B)
        L.append("3) MST-tree preorder tour (2-approx):")
        L.append("   " + " -> ".join(map(str, t)) + f"   = {km(algos.tour_len(t, m))}\n")
        # 4. 2-opt improvement of best
        best = min((g, t), key=lambda o: algos.tour_len(o, m))
        o = algos.two_opt(best, m)
        L.append("4) Best tour after 2-opt improvement:")
        L.append("   " + " -> ".join(f"{names[i]}" for i in o) + f"\n   = {km(algos.tour_len(o, m))}")
    return "\n".join(L)


class Root(BoxLayout):
    def run(self, a, b, stops):
        if not a.strip() or not b.strip():
            self.ids.out.text = "Please fill both Point A and Point B."
            return
        self.ids.out.text = "Working..."

        def work():
            try:
                res = solve(a, b, stops)
            except Exception as e:
                res = f"Error: {e}"
            Clock.schedule_once(lambda dt: setattr(self.ids.out, "text", res))
        threading.Thread(target=work, daemon=True).start()


class PathApp(App):
    def build(self):
        Builder.load_string(KV)
        return Root()


if __name__ == "__main__":
    PathApp().run()
