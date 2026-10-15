"""Transport modes.

kind 'road'  : real road/path geometry from free OSRM servers (car / bicycle / foot profiles).
               Bus, truck and motorcycle reuse the car road network, with a documented
               travel-time factor (OSRM has no free bus/truck profile).
kind 'train' / 'air': no free routing API exists for rail, and planes don't follow roads, so
               these are *estimates* drawn as a dashed arc (great-circle) and flagged as such.
"""

MODES = {
    "Car": dict(kind="road", profile="car", dur_factor=1.00,
                note="Real road route (OpenStreetMap data)."),
    "Bike (motorcycle)": dict(kind="road", profile="car", dur_factor=0.90,
                note="Road route on the car network; time x0.90 for a two-wheeler. Avoid expressways that ban bikes."),
    "Bicycle": dict(kind="road", profile="bike", dur_factor=1.00,
                note="Cycling route (bicycle-friendly roads and paths)."),
    "Walk": dict(kind="road", profile="foot", dur_factor=1.00,
                note="Walking route (footpaths and roads, about 5 km/h)."),
    "Bus": dict(kind="road", profile="car", dur_factor=1.50,
                note="Road route; time x1.5 for stops. Estimate only: no timetable data."),
    "Truck": dict(kind="road", profile="car", dur_factor=1.35,
                note="Road route on the car network; time x1.35 for slower speeds. No weight/height restrictions applied."),
    "Train": dict(kind="train", circuity=1.20, speed_kmh=65.0, overhead_s=0,
                note="ESTIMATE: no free rail-routing service exists. Straight corridor x1.2 at 65 km/h average."),
    "Airplane": dict(kind="air", circuity=1.00, speed_kmh=800.0, overhead_s=5400,
                note="ESTIMATE: great-circle flight at 800 km/h plus 1.5 h for airport procedures."),
}
MODE_NAMES = list(MODES.keys())
