
from pydbus import SystemBus
from gi.repository.GLib import Variant


bus = SystemBus()

o = bus.get("dishpan.pytooth", "/dishpan/pytooth/agent")
help(o)
o.Cancel()
o.Release()
