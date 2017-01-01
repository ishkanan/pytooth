
A2DP_SOURCE_UUID = "0000110A-0000-1000-8000-00805F9B34FB"
A2DP_SINK_UUID = "0000110B-0000-1000-8000-00805F9B34FB"
HFP_AG_UUID = "0000111F-0000-1000-8000-00805F9B34FB"
HFP_HF_UUID = "0000111E-0000-1000-8000-00805F9B34FB"
HSP_AG_UUID = "00001112-0000-1000-8000-00805F9B34FB"

SBC_CODEC = dbus.Byte(0x00)
#Channel Modes: Mono DualChannel Stereo JointStereo
#Frequencies: 16Khz 32Khz 44.1Khz 48Khz
#Subbands: 4 8
#Blocks: 4 8 12 16
#Bitpool Range: 2-64
SBC_CAPABILITIES = dbus.Array([dbus.Byte(0xff), dbus.Byte(0xff), dbus.Byte(2), dbus.Byte(64)])
# JointStereo 44.1Khz Subbands: Blocks: 16 Bitpool Range: 2-32
SBC_CONFIGURATION = dbus.Array([dbus.Byte(0x21), dbus.Byte(0x15), dbus.Byte(2), dbus.Byte(32)])

MP3_CODEC = dbus.Byte(0x01)
#Channel Modes: Mono DualChannel Stereo JointStereo
#Frequencies: 32Khz 44.1Khz 48Khz
#CRC: YES
#Layer: 3
#Bit Rate: All except Free format
#VBR: Yes
#Payload Format: RFC-2250
MP3_CAPABILITIES = dbus.Array([dbus.Byte(0x3f), dbus.Byte(0x07), dbus.Byte(0xff), dbus.Byte(0xfe)])
# JointStereo 44.1Khz Layer: 3 Bit Rate: VBR Format: RFC-2250
MP3_CONFIGURATION = dbus.Array([dbus.Byte(0x21), dbus.Byte(0x02), dbus.Byte(0x00), dbus.Byte(0x80)])
