"""Start/stop the background tracking service and read its live state.

The heavy lifting is in service.py (a python-for-android foreground service).
This module is the app-side controller: it launches that service, hands it the
trip config + the path of the shared state file, stops it, and reads back the
JSON the service writes while it runs. Everything is a no-op off Android so the
same code runs on the desktop for development.
"""
import json
import os

import config as _appconfig  # noqa: F401  (kept for parity / future use)

try:
    from jnius import autoclass
    ANDROID = True
except Exception:
    ANDROID = False

# Must match buildozer.spec:  services = Tracker:service.py:foreground
_SERVICE_NAME = "Tracker"


def _service_class():
    """Fully-qualified name of the p4a-generated service class."""
    try:
        from android import mActivity  # type: ignore  # noqa
    except Exception:
        pass
    # org.<domain>.<package.name>.Service<Name>
    domain = "org.example"      # package.domain in buildozer.spec
    package = "tarangnav"       # package.name in buildozer.spec
    return f"{domain}.{package}.Service{_SERVICE_NAME}"


def state_path():
    """Where the service writes live trip state (app private storage)."""
    if ANDROID:
        try:
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            base = activity.getFilesDir().getAbsolutePath()
        except Exception:
            base = os.path.expanduser("~")
    else:
        base = os.environ.get("TARANG_DATA_DIR", os.path.expanduser("~"))
    return os.path.join(base, "trip_state.json")


def start(mode="", weight_kg=70.0):
    """Launch the foreground tracking service. Returns True if it was started."""
    if not ANDROID:
        return False
    try:
        arg = json.dumps({"state_path": state_path(), "mode": mode, "weight_kg": weight_kg})
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        service = autoclass(_service_class())
        service.start(activity, arg)
        return True
    except Exception:
        return False


def stop():
    """Stop the foreground tracking service."""
    if not ANDROID:
        return False
    try:
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        service = autoclass(_service_class())
        service.stop(activity)
    except Exception:
        pass
    # Mark the state file finished so the UI stops reading it as live.
    try:
        p = state_path()
        if os.path.exists(p):
            with open(p) as f:
                d = json.load(f)
            d["running"] = False
            with open(p, "w") as f:
                json.dump(d, f)
    except Exception:
        pass
    return True


def read_state():
    """Latest trip state written by the service, or None if unavailable."""
    try:
        with open(state_path()) as f:
            return json.load(f)
    except Exception:
        return None
