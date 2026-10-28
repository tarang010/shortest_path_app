"""Transport modes.

kind 'road'  : real road/path geometry from free OSRM servers (car / bicycle / foot profiles).
               Bus and motorcycle reuse the car road network, with a documented
               travel-time factor (OSRM has no free bus profile).
kind 'air'   : planes don't follow roads. The app routes you by road to the nearest
               airport, draws the great-circle flight, then routes by road from the
               destination airport to the final destination (see geo.plane_route).

Train and Truck are intentionally disabled (see DISABLED_MODES).
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
    "Airplane": dict(kind="air", circuity=1.00, speed_kmh=800.0, overhead_s=5400,
                note="Road to the nearest airport, great-circle flight at 800 km/h (plus 1.5 h for "
                     "airport procedures), then road from the arrival airport to your destination."),
}

# Deliberately removed from the picker. Kept here as a record of what was disabled.
DISABLED_MODES = ("Train", "Truck")

MODE_NAMES = list(MODES.keys())
