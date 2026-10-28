"""Barometric altitude for accurate elevation gain/loss on Android.

GPS altitude is noisy and many phones never report it, so climbing a couple of
floors shows no change. Most phones have a pressure sensor (barometer) which
measures height changes to within a metre. We read it through Android's
SensorManager and convert pressure to altitude with the barometric formula.

Only *changes* in altitude matter for gain/loss, so we don't need to know the
exact sea-level pressure; the reading tracks every floor climbed or descended.
On a device without a barometer (or on desktop) this silently does nothing and
the tracker falls back to GPS altitude.
"""
import time

from kivy.clock import Clock

try:
    from android.permissions import check_permission  # noqa: F401  (import probes Android)
    ANDROID = True
except Exception:
    ANDROID = False

SEA_LEVEL_HPA = 1013.25


def pressure_to_altitude(hpa, sea_level_hpa=SEA_LEVEL_HPA):
    """Barometric formula: metres above the reference pressure level."""
    return 44330.0 * (1.0 - (hpa / sea_level_hpa) ** 0.1903)


class Barometer:
    """Calls on_alt(metres, t) whenever a new pressure reading arrives."""

    def __init__(self, on_alt):
        self.on_alt = on_alt
        self.running = False
        self.available = False
        self._manager = None
        self._sensor = None
        self._listener = None     # strong ref so the pyjnius proxy is not GC'd

    def start(self):
        if self.running or not ANDROID:
            return False
        try:
            from jnius import autoclass, PythonJavaClass, java_method

            Context = autoclass("android.content.Context")
            Sensor = autoclass("android.hardware.Sensor")
            SensorManager = autoclass("android.hardware.SensorManager")
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            manager = activity.getSystemService(Context.SENSOR_SERVICE)
            sensor = manager.getDefaultSensor(Sensor.TYPE_PRESSURE)
            if sensor is None:
                return False

            provider = self

            class _Listener(PythonJavaClass):
                __javainterfaces__ = ["android/hardware/SensorEventListener"]

                @java_method("(Landroid/hardware/SensorEvent;)V")
                def onSensorChanged(self, event):
                    try:
                        hpa = event.values[0]
                    except Exception:
                        return
                    provider._emit(hpa)

                @java_method("(Landroid/hardware/Sensor;I)V")
                def onAccuracyChanged(self, sensor, accuracy):
                    pass

            listener = _Listener()
            # SENSOR_DELAY_UI == 2 (about every 60 ms); plenty for altitude.
            manager.registerListener(listener, sensor, 2)
            self._manager, self._sensor, self._listener = manager, sensor, listener
            self.running = self.available = True
            return True
        except Exception:
            return False

    def _emit(self, hpa):
        alt = pressure_to_altitude(hpa)
        Clock.schedule_once(lambda dt: self.on_alt(alt, time.time()))

    def stop(self):
        if not self.running:
            return
        try:
            self._manager.unregisterListener(self._listener)
        except Exception:
            pass
        self.running = False
