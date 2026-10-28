[app]
title = Tarang Nav
package.name = tarangnav
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv
version = 4.0
# Bump this integer on every Play Store upload (versionCode must always increase).
android.numeric_version = 1
requirements = python3==3.11.5,hostpython3==3.11.5,kivy==2.3.0,kivy_garden.mapview,plyer,requests,urllib3,idna,charset-normalizer,certifi
orientation = all
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
presplash.color = #0A1F44
fullscreen = 0
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,FOREGROUND_SERVICE,FOREGROUND_SERVICE_LOCATION,WAKE_LOCK,POST_NOTIFICATIONS,CAMERA,READ_MEDIA_IMAGES

# Background GPS tracking service (keeps recording when minimized / screen off).
# Syntax: <Name>:<entrypoint>:<foreground|sticky>
services = Tracker:service.py:foreground

android.api = 34
android.minapi = 24
# 64-bit (arm64) is required by Play; armeabi-v7a adds support for older devices.
android.archs = arm64-v8a,armeabi-v7a
android.ndk = 25b
android.ndk_api = 24
android.accept_sdk_license = True

# Play Store wants an Android App Bundle (.aab) for release builds.
# `buildozer android release` reads this; debug builds still produce an .apk.
android.release_artifact = aab

p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
