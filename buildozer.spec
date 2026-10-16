[app]
title = Tarang Nav
package.name = tarangnav
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv
version = 3.0
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,kivy_garden.mapview,plyer,requests,urllib3,idna,charset-normalizer,certifi
orientation = all
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
presplash.color = #0A1F44
fullscreen = 0
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.ndk = 25b
android.ndk_api = 24
android.accept_sdk_license = True

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
