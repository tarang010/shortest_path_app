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


def met_for(kmh, mode=""):
    """Metabolic-equivalent value for the current pace, used to estimate calories."""
    if "Bicycle" in mode:
        if kmh < 16:
            return 4.0
        if kmh < 19:
            return 6.0
        if kmh < 22:
            return 8.0
        if kmh < 25:
            return 10.0
        return 12.0
    # walking / running
    if kmh < 3.2:
        return 2.0
    if kmh < 4.0:
        return 2.8
    if kmh < 4.8:
        return 3.5
    if kmh < 5.6:
        return 4.3
    if kmh < 6.4:
        return 5.0
    if kmh < 8.0:
        return 7.0
    if kmh < 9.7:
        return 9.0
    return 11.0


def calories(moving_s, dist_m, gain_m, weight_kg=70.0, mode=""):
    """kcal from MET x weight x moving-hours, plus the work of climbing the elevation gained."""
    hours = max(0.0, moving_s) / 3600.0
    kmh = (dist_m / moving_s * 3.6) if moving_s > 0 else 0.0
    base = met_for(kmh, mode) * max(1.0, weight_kg) * hours
    climb = max(0.0, weight_kg) * max(0.0, gain_m) * 0.0098     # m*g*h, ~23% muscle efficiency
    return base + climb


class Tracker:
    MAX_ACC = 50.0      # ignore fixes worse than 50 m
    MAX_SPEED = 70.0    # m/s: bigger jumps are GPS glitches
    MIN_STEP = 2.0      # metres: smaller moves are jitter while standing still
    ELE_EMA = 0.3       # smoothing on noisy GPS altitude
    ELE_THRESH = 2.0    # metres: ignore smaller altitude wiggles

    def __init__(self):
        self.t0 = self.t_last = None
        self.last = None
        self.dist = 0.0
        self.moving = 0.0
        self.speed = 0.0          # smoothed m/s
        self.path = []
        self.gain = 0.0           # total metres climbed
        self.loss = 0.0           # total metres descended
        self.alt_cur = None       # latest raw altitude
        self.alt_min = self.alt_max = None
        self._alt_s = None        # smoothed altitude
        self._alt_ref = None      # last altitude we counted a gain/loss from

    def feed_altitude(self, alt):
        """Feed an altitude reading from a dedicated sensor (barometer) outside GPS fixes."""
        self._update_alt(alt)

    def _update_alt(self, alt):
        if alt is None:
            return
        self.alt_cur = alt
        if self._alt_s is None:
            self._alt_s = self._alt_ref = self.alt_min = self.alt_max = alt
            return
        self._alt_s = (1 - self.ELE_EMA) * self._alt_s + self.ELE_EMA * alt
        self.alt_min = min(self.alt_min, self._alt_s)
        self.alt_max = max(self.alt_max, self._alt_s)
        d = self._alt_s - self._alt_ref
        if d >= self.ELE_THRESH:
            self.gain += d
            self._alt_ref = self._alt_s
        elif d <= -self.ELE_THRESH:
            self.loss += -d
            self._alt_ref = self._alt_s

    def add_fix(self, lat, lon, t, acc=None, alt=None):
        if acc is not None and acc > self.MAX_ACC:
            return False
        if self.last is None:
            self.t0 = self.t_last = t
            self.last = (lat, lon, t)
            self.path.append((lat, lon))
            self._update_alt(alt)
            return True
        d = haversine(self.last[:2], (lat, lon))
        dt = t - self.last[2]
        if dt <= 0 or d / dt > self.MAX_SPEED:
            return False            # rejected fixes must not advance the clock
        self.t_last = t
        self._update_alt(alt)
        if d < max(self.MIN_STEP, (acc or 0) * 0.35):
            return True             # measured from the last recorded point, so slow walking still adds up
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

    def calories(self, weight_kg=70.0, mode=""):
        return calories(self.moving, self.dist, self.gain, weight_kg, mode)

    def summary(self, mode="", now=None, weight_kg=70.0):
        return {"when": self.t0, "distance_m": round(self.dist), "duration_s": round(self.elapsed(now)),
                "avg_kmh": round(self.avg_kmh(now), 1), "moving_s": round(self.moving), "mode": mode,
                "gain_m": round(self.gain), "loss_m": round(self.loss),
                "calories": round(self.calories(weight_kg, mode))}
