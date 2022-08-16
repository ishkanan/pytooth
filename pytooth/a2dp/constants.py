
from pytooth.constants import DBUS_ORG_NAME


A2DP_PROFILE_UUID = "0000110d-0000-1000-8000-00805f9b34fb"
A2DP_SOURCE_UUID = "0000110a-0000-1000-8000-00805f9b34fb"
A2DP_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"

A2DP_DBUS_MEDIA_ENDPOINT = DBUS_ORG_NAME+".endpoints.a2dp"
A2DP_DBUS_PROFILE_ENDPOINT = DBUS_ORG_NAME+".profiles.a2dp"

SBC_CODEC = b'\x00'
#Channel Modes: Mono DualChannel Stereo JointStereo
#Frequencies: 16Khz 32Khz 44.1Khz 48Khz
#Subbands: 4 8
#Blocks: 4 8 12 16
#Bitpool Range: 2-64
SBC_CAPABILITIES = [b'\xff', b'\xff', b'\x02', b'\x40']
# JointStereo 44.1Khz Subbands: Blocks: 16 Bitpool Range: 2-32
SBC_CONFIGURATION = [b'\x21', b'\x15', b'\x02', b'\x20']

MP3_CODEC = b'\x01'
#Channel Modes: Mono DualChannel Stereo JointStereo
#Frequencies: 32Khz 44.1Khz 48Khz
#CRC: YES
#Layer: 3
#Bit Rate: All except Free format
#VBR: Yes
#Payload Format: RFC-2250
MP3_CAPABILITIES = [b'\x3f', b'\x07', b'\xff', b'\xfe']
# JointStereo 44.1Khz Layer: 3 Bit Rate: VBR Format: RFC-2250
MP3_CONFIGURATION = [b'\x21', b'\x02', b'\x00', b'\x80']
