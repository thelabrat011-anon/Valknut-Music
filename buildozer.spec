[app]

title = ValknutMusic
package.name = miplayer
package.domain = org.miapp
version = 0.1

source.dir = .
source.include_exts = py,png,jpg,kv,atlas
icon.filename = %(source.dir)s/icon.png

requirements = python3==3.11.9,hostpython3==3.11.9,kivy,pyjnius,mutagen,android,plyer

orientation = portrait
fullscreen = 0

android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,INTERNET,FOREGROUND_SERVICE
android.api = 33
android.minapi = 21
android.ndk = 28c
android.accept_sdk_license = True
android.foreground = True

[buildozer]
log_level = 2
warn_on_root = 1
