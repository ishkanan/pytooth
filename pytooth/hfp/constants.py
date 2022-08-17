
from pytooth.constants import DBUS_BASE_PATH


HFP_PROFILE_UUID = "0000110e-0000-1000-8000-00805f9b34fb"

HFP_DBUS_PROFILE_ENDPOINT = DBUS_BASE_PATH+"/profiles/hfp"

HF_NREC = 0x01  # EC and/or NR function
HF_3WAY = 0x02  # Call waiting or three-way calling
HF_CLI = 0x04  # CLI presentation capability
HF_VOICE_RECOGNITION = 0x08  # Voice recognition activation
HF_REMOTE_VOL = 0x10  # Remote volume control
HF_WIDE_BAND = 0x20  # Wide band speech
HF_ECALL_STAT = 0x20  # Enhanced call status
HF_ECALL_CTRL = 0x40  # Enhanced call control
HF_CODEC_NEG = 0x80  # Codec negotiation
HF_INDICATORS = 0x100  # HF indicators
HF_ESCO_S4T2 = 0x200  # eSCO S4 (and T2) settings support

HF_SUPPORTED_FEATURES = HF_3WAY | HF_CLI  # | HF_WIDE_BAND
HF_BRSF_FEATURES = HF_3WAY | HF_CLI | HF_ESCO_S4T2  # | HF_CODEC_NEG
