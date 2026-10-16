"""Phone GPS for Android.

Primary path talks to Android's LocationManager directly through pyjnius, because
plyer's gps facade frequently turns the system GPS on (requestLocationUpdates
succeeds) yet never delivers onLocationChanged callbacks, so a fix never arrives.
plyer is kept only as a fallback. On a desktop there is no GPS, so fixes can be
injected for testing.
"""
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
        self._manager = None
        self._listener = None            # strong ref so pyjnius proxy isn't GC'd
        self._native = False

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
        if self._begin_native():
            return
        self._begin_plyer()

    # ------------------------------------------------------------------ native LocationManager
    def _begin_native(self):
        try:
            from jnius import autoclass, PythonJavaClass, java_method
            from android.runnable import run_on_ui_thread  # type: ignore

            Context = autoclass("android.content.Context")
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            manager = activity.getSystemService(Context.LOCATION_SERVICE)
            if manager is None:
                return False

            provider = self
            lat_lon_ready = {"ok": False}

            class _Listener(PythonJavaClass):
                __javainterfaces__ = ["android/location/LocationListener"]

                @java_method("(Landroid/location/Location;)V")
                def onLocationChanged(self, location):
                    provider._on_native_location(location)

                @java_method("(Ljava/lang/String;)V")
                def onProviderEnabled(self, provider_name):
                    pass

                @java_method("(Ljava/lang/String;)V")
                def onProviderDisabled(self, provider_name):
                    pass

                @java_method("(Ljava/lang/String;ILandroid/os/Bundle;)V")
                def onStatusChanged(self, provider_name, status, extras):
                    pass

            listener = _Listener()
            self._manager, self._listener, self._native = manager, listener, True

            LocationManager = autoclass("android.location.LocationManager")
            providers = [LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER]

            # Seed an immediate fix from the last known location if one exists.
            for name in providers:
                try:
                    last = manager.getLastKnownLocation(name)
                    if last is not None:
                        self._on_native_location(last)
                        lat_lon_ready["ok"] = True
                        break
                except Exception:
                    pass

            @run_on_ui_thread
            def _request():
                started = False
                for name in providers:
                    try:
                        if manager.isProviderEnabled(name):
                            manager.requestLocationUpdates(name, 1000, 0.0, listener)
                            started = True
                    except Exception:
                        pass
                if started:
                    self.running = True
                    if not lat_lon_ready["ok"]:
                        self.on_status("GPS searching for a fix...")
                else:
                    self.on_status("Location is off. Turn on Location in Android settings.")

            _request()
            return True
        except Exception:
            return False

    def _on_native_location(self, location):
        try:
            lat = location.getLatitude()
            lon = location.getLongitude()
            acc = location.getAccuracy() if location.hasAccuracy() else None
            spd = location.getSpeed() if location.hasSpeed() else None
            alt = location.getAltitude() if location.hasAltitude() else None
        except Exception:
            return
        fix = {"lat": lat, "lon": lon, "acc": acc, "speed": spd, "alt": alt, "t": time.time()}
        Clock.schedule_once(lambda dt: self.on_fix(fix))

    # ------------------------------------------------------------------ plyer fallback
    def _begin_plyer(self):
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
               "speed": kw.get("speed"), "alt": kw.get("altitude"), "t": time.time()}
        if fix["lat"] is not None:
            Clock.schedule_once(lambda dt: self.on_fix(fix))

    def _status(self, stype, status):
        Clock.schedule_once(lambda dt: self.on_status(f"GPS {stype}: {status}"))

    def stop(self):
        if not self.running:
            return
        if self._native:
            try:
                from android.runnable import run_on_ui_thread  # type: ignore

                @run_on_ui_thread
                def _remove():
                    try:
                        self._manager.removeUpdates(self._listener)
                    except Exception:
                        pass
                _remove()
            except Exception:
                pass
        else:
            try:
                from plyer import gps
                gps.stop()
            except Exception:
                pass
        self.running = False

    def inject(self, lat, lon, acc=5.0, t=None, alt=None):   # desktop testing / simulation
        self.on_fix({"lat": lat, "lon": lon, "acc": acc, "speed": None, "alt": alt, "t": t or time.time()})


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
