"""Phone GPS via plyer (Android). On a desktop there is no GPS, so fixes can be injected for testing."""
import time

from kivy.clock import Clock

try:                                                     # only exists inside the Android app
    from android.permissions import Permission, request_permissions  # type: ignore
    ANDROID = True
except Exception:
    ANDROID = False


class GPSProvider:
    def __init__(self, on_fix, on_status):
        self.on_fix, self.on_status = on_fix, on_status
        self.running = False

    def start(self):
        if self.running:
            return
        if ANDROID:
            request_permissions([Permission.ACCESS_FINE_LOCATION, Permission.ACCESS_COARSE_LOCATION],
                                self._perm)
        else:
            self.on_status("No GPS on this device (desktop). Open the app on your phone.")

    def _perm(self, permissions, grants):
        if grants and all(grants):
            Clock.schedule_once(lambda dt: self._begin())
        else:
            self.on_status("Location permission denied. Enable it in Android settings.")

    def _begin(self):
        try:
            from plyer import gps
            gps.configure(on_location=self._loc, on_status=self._status)
            gps.start(minTime=1000, minDistance=0)
            self.running = True
            self.on_status("GPS searching for a fix...")
        except NotImplementedError:
            self.on_status("GPS is not supported on this device.")
        except Exception as e:
            self.on_status(f"GPS error: {e}")

    def _loc(self, **kw):                                # called from a non-UI thread
        fix = {"lat": kw.get("lat"), "lon": kw.get("lon"), "acc": kw.get("accuracy"),
               "speed": kw.get("speed"), "t": time.time()}
        if fix["lat"] is not None:
            Clock.schedule_once(lambda dt: self.on_fix(fix))

    def _status(self, stype, status):
        Clock.schedule_once(lambda dt: self.on_status(f"GPS {stype}: {status}"))

    def stop(self):
        if self.running:
            try:
                from plyer import gps
                gps.stop()
            except Exception:
                pass
            self.running = False

    def inject(self, lat, lon, acc=5.0, t=None):         # desktop testing / simulation
        self.on_fix({"lat": lat, "lon": lon, "acc": acc, "speed": None, "t": t or time.time()})


def keep_screen_on(on=True):
    """Stops the screen sleeping during a trip (Android only; silently ignored elsewhere)."""
    try:
        from android.runnable import run_on_ui_thread  # type: ignore
        from jnius import autoclass  # type: ignore

        @run_on_ui_thread
        def _apply():
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            flag = autoclass("android.view.WindowManager$LayoutParams").FLAG_KEEP_SCREEN_ON
            win = act.getWindow()
            win.addFlags(flag) if on else win.clearFlags(flag)
        _apply()
    except Exception:
        pass
