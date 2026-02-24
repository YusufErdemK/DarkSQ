#!/usr/bin/env python3
# DarkSQ - ZeXis OS Security Suite
# Main entry point

import sys
import os
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, Gio, GLib
from app import DarkSQApp

def main():
    app = DarkSQApp()
    return app.run(sys.argv)

if __name__ == '__main__':
    sys.exit(main())
