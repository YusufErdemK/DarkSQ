#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib
from window import DarkSQWindow

class DarkSQApp(Adw.Application):
    def __init__(self):
        # DEFAULT_FLAGS was added in newer GLib, FLAGS_NONE is the compatible fallback
        flags = getattr(Gio.ApplicationFlags, 'DEFAULT_FLAGS',
                        Gio.ApplicationFlags.FLAGS_NONE)
        super().__init__(
            application_id='com.zexis.darksq',
            flags=flags
        )
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        win = DarkSQWindow(application=app)
        win.present()