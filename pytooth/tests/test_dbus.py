
from pydbus import SystemBus
from gi.repository.GLib import Variant


bus = SystemBus()

o = bus.get("org.bluez", "/org/bluez")
help(o)
