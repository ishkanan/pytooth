
import ctypes as ct
import struct


# initialise
print("Loading libliquid...")
lib = ct.CDLL("/usr/local/lib/libliquid.so.1.2.0")
print("Making cvsd instance...")
lib.cvsd_create_sg(
    ct.c_uint(5),
    ct.c_float(1.5),
    ct.c_float(0.95))
print("CVSD instance was created.")

# read captured CVSD samples
with open('out.cvsd', 'rb') as f:
    data = f.read()

# decode loop
try:
    float_init = [0.0] * 8
    float_array_type = ct.c_float * 8
    decode_buf = float_array_type(*float_init)

    with open('out.cvsd.decoded', 'wb') as f:
        for b in data:
            lib.cvsd_decode8_sg(
                ct.c_ubyte(b),
                ct.pointer(decode_buf))
            for i in range(0, 8):
                f.write(bytearray(struct.pack("f", decode_buf[i])))
except Exception as e:
    print(e)
finally:
    lib.cvsd_destroy_sg()
    print("CVSD instance was destroyed.")
