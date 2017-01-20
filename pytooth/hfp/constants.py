
from pytooth.constants import DBUS_BASE_PATH


HFP_PROFILE_UUID = "0000110e-0000-1000-8000-00805f9b34fb"

HFP_DBUS_PROFILE_ENDPOINT = DBUS_BASE_PATH+"/profiles/hfp"

HF_NREC = 0x0001 # EC and/or NR function
HF_3WAY = 0x0002 # Call waiting or three-way calling
HF_CLI = 0x0004 # CLI presentation capability
HF_VOICE_RECOGNITION = 0x0008 # Voice recognition activation
HF_REMOTE_VOL = 0x0010 # Remote volume control
HF_WIDE_BAND = 0x0020 # Wide band speech

HF_FEATURES = HF_3WAY | HF_CLI | HF_WIDE_BAND
