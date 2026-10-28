"""Fuel / energy estimates for a planned trip.

Pure python, no network. Given a road distance and the vehicle's mileage
(entered by the user in Advanced Settings), work out how much fuel is needed to
reach the destination and to come back again.
"""


def litres_needed(dist_m, mileage_kmpl):
    """Litres of fuel for `dist_m` metres at `mileage_kmpl` km per litre."""
    if not mileage_kmpl or mileage_kmpl <= 0:
        return None
    return (dist_m / 1000.0) / float(mileage_kmpl)


def estimate(dist_m, mileage_kmpl, price_per_litre=None):
    """Return a dict with one-way and round-trip fuel (and cost if a price is given)."""
    one = litres_needed(dist_m, mileage_kmpl)
    if one is None:
        return None
    out = {"one_way_l": one, "round_trip_l": one * 2.0,
           "one_way_cost": None, "round_trip_cost": None}
    if price_per_litre and price_per_litre > 0:
        out["one_way_cost"] = one * price_per_litre
        out["round_trip_cost"] = one * 2.0 * price_per_litre
    return out


def summary_text(dist_m, mileage_kmpl, price_per_litre=None, unit="L"):
    """Short one-line summary for a route card, e.g. '2.1 L there / 4.2 L round trip'."""
    e = estimate(dist_m, mileage_kmpl, price_per_litre)
    if not e:
        return ""
    txt = f"{e['one_way_l']:.1f} {unit} there / {e['round_trip_l']:.1f} {unit} round trip"
    if e["round_trip_cost"]:
        txt += f"  (~{e['one_way_cost']:.0f} / {e['round_trip_cost']:.0f})"
    return txt
