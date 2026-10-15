"""Trip tracking maths (pure python): distance covered, time, speed, progress along a route."""
import math
from algos import haversine


def nearest_index(coords, ref):
    """Index of the route point nearest to ref=(lat,lon) and the approximate distance in metres."""
    la0, lo0 = ref
    c = math.cos(math.radians(la0))
    best, bi = 1e18, 0
    for i, (la, lo) in enumerate(coords):
        d = (la - la0) ** 2 + ((lo - lo0) * c) ** 2
        if d < best:
            best, bi = d, i
    return bi, math.sqrt(best) * 111320.0


def cumulative(coords):
    cum = [0.0]
    for i in range(1, len(coords)):
        cum.append(cum[-1] + haversine(coords[i - 1], coords[i]))
    return cum


def locate(coords, cum, pos):
    """(distance already covered along the route, distance remaining, metres off the route)."""
    i, off = nearest_index(coords, pos)
    return cum[i], cum[-1] - cum[i], off


class Tracker:
    MAX_ACC = 60.0      # ignore fixes worse than 60 m
    MAX_SPEED = 70.0    # m/s: bigger jumps are GPS glitches
    MIN_STEP = 3.0      # metres: smaller moves are jitter while standing still

    def __init__(self):
        self.t0 = self.t_last = None
        self.last = None
        self.dist = 0.0
        self.moving = 0.0
        self.speed = 0.0          # smoothed m/s
        self.path = []

    def add_fix(self, lat, lon, t, acc=None):
        if acc is not None and acc > self.MAX_ACC:
            return False
        if self.t0 is None:
            self.t0 = t
        self.t_last = t
        if self.last is None:
            self.last = (lat, lon, t)
            self.path.append((lat, lon))
            return True
        d = haversine(self.last[:2], (lat, lon))
        dt = t - self.last[2]
        if dt <= 0 or d / dt > self.MAX_SPEED:
            return False
        if d < max(self.MIN_STEP, (acc or 0) * 0.5):
            return True
        self.dist += d
        self.moving += dt
        v = d / dt
        self.speed = v if self.speed == 0 else 0.6 * self.speed + 0.4 * v
        self.path.append((lat, lon))
        self.last = (lat, lon, t)
        return True

    def elapsed(self, now=None):
        if self.t0 is None:
            return 0.0
        return max(0.0, (now if now is not None else self.t_last) - self.t0)

    def avg_kmh(self, now=None):
        e = self.elapsed(now)
        return self.dist / e * 3.6 if e > 1 else 0.0

    def summary(self, mode="", now=None):
        return {"when": self.t0, "distance_m": round(self.dist), "duration_s": round(self.elapsed(now)),
                "avg_kmh": round(self.avg_kmh(now), 1), "moving_s": round(self.moving), "mode": mode}
