"""Background GPS tracking service (Android foreground service).

python-for-android starts this file as a *separate* Android service process when
the app begins a trip (see background.py and the `services` line in
buildozer.spec). Because it runs as a foreground service with a persistent
notification and a wake lock, Android keeps it alive when the screen is off or
the app is minimized, so tracking never stops until the trip is ended.

It talks to Android's LocationManager directly (and the barometer, if present)
on its own Looper thread, feeds a Tracker, and writes the live trip state to a
small JSON file that the UI reads when it comes back to the foreground.

Pure-python helpers (tracker.py / algos.py) are reused; this file has no Kivy
dependency because there is no UI in a service process.
"""
import json
import os
import threading
import time

import tracker as trk

def _parse_arg():
    """The app passes one argument string (PYTHON_SERVICE_ARGUMENT) as JSON:
    {"state_path": ..., "mode": ..., "weight_kg": ...}."""
    raw = os.environ.get("PYTHON_SERVICE_ARGUMENT", "").strip()
    try:
        d = json.loads(raw)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {"state_path": raw}


_ARG = _parse_arg()
STATE_PATH = _ARG.get("state_path", "")
_tracker = trk.Tracker()
_lock = threading.Lock()
_mode = _ARG.get("mode", "")
try:
    _weight = float(_ARG.get("weight_kg", 70) or 70)
except Exception:
    _weight = 70.0
_baro_available = False


def _write_state():
    if not STATE_PATH:
        return
    with _lock:
        s = _tracker.summary(_mode, weight_kg=_weight)
    s["running"] = True
    s["updated"] = time.time()
    try:
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(s, f)
        os.replace(tmp, STATE_PATH)
    except Exception:
        pass


def _acquire_wakelock():
    try:
        from jnius import autoclass
        Context = autoclass("android.content.Context")
        PowerManager = autoclass("android.os.PowerManager")
        service = autoclass("org.kivy.android.PythonService").mService
        pm = service.getSystemService(Context.POWER_SERVICE)
        wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "TarangNav::TripWakeLock")
        wl.acquire()
        return wl
    except Exception:
        return None


def _start_barometer():
    """Feed accurate relative altitude into the tracker if a barometer exists."""
    global _baro_available
    try:
        from jnius import autoclass, PythonJavaClass, java_method

        Context = autoclass("android.content.Context")
        Sensor = autoclass("android.hardware.Sensor")
        service = autoclass("org.kivy.android.PythonService").mService
        manager = service.getSystemService(Context.SENSOR_SERVICE)
        sensor = manager.getDefaultSensor(Sensor.TYPE_PRESSURE)
        if sensor is None:
            return None

        class _PListener(PythonJavaClass):
            __javainterfaces__ = ["android/hardware/SensorEventListener"]

            @java_method("(Landroid/hardware/SensorEvent;)V")
            def onSensorChanged(self, event):
                try:
                    hpa = event.values[0]
                except Exception:
                    return
                alt = 44330.0 * (1.0 - (hpa / 1013.25) ** 0.1903)
                with _lock:
                    _tracker.feed_altitude(alt)

            @java_method("(Landroid/hardware/Sensor;I)V")
            def onAccuracyChanged(self, sensor, accuracy):
                pass

        listener = _PListener()
        manager.registerListener(listener, sensor, 2)
        _baro_available = True
        with _lock:
            _tracker.ELE_EMA = 0.5
            _tracker.ELE_THRESH = 1.0
        return listener
    except Exception:
        return None


def _run():
    from jnius import autoclass, PythonJavaClass, java_method

    Looper = autoclass("android.os.Looper")
    Looper.prepare()

    Context = autoclass("android.content.Context")
    LocationManager = autoclass("android.location.LocationManager")
    service = autoclass("org.kivy.android.PythonService").mService
    manager = service.getSystemService(Context.LOCATION_SERVICE)

    def handle_location(location):
        try:
            lat = location.getLatitude()
            lon = location.getLongitude()
            acc = location.getAccuracy() if location.hasAccuracy() else None
            alt = None if _baro_available else (location.getAltitude() if location.hasAltitude() else None)
        except Exception:
            return
        with _lock:
            _tracker.add_fix(lat, lon, time.time(), acc, alt)
        _write_state()

    class _Listener(PythonJavaClass):
        __javainterfaces__ = ["android/location/LocationListener"]

        @java_method("(Landroid/location/Location;)V")
        def onLocationChanged(self, location):
            handle_location(location)

        @java_method("(Ljava/lang/String;)V")
        def onProviderEnabled(self, provider):
            pass

        @java_method("(Ljava/lang/String;)V")
        def onProviderDisabled(self, provider):
            pass

        @java_method("(Ljava/lang/String;ILandroid/os/Bundle;)V")
        def onStatusChanged(self, provider, status, extras):
            pass

    listener = _Listener()
    for name in (LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER):
        try:
            last = manager.getLastKnownLocation(name)
            if last is not None:
                handle_location(last)
        except Exception:
            pass
        try:
            if manager.isProviderEnabled(name):
                manager.requestLocationUpdates(name, 1000, 0.0, listener)
        except Exception:
            pass

    # Tick the clock even when no new fix arrives, so elapsed time stays live.
    def ticker():
        while True:
            time.sleep(2.0)
            _write_state()
    threading.Thread(target=ticker, daemon=True).start()

    Looper.loop()


def main():
    _acquire_wakelock()
    _start_barometer()
    _write_state()
    _run()


if __name__ == "__main__":
    main()
