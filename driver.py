# Proper test driver for the 10moons graphics tablet

import os
import sys

# Specification of the device https://python-evdev.readthedocs.io/en/latest/
from evdev import UInput, ecodes, AbsInfo
# Establish usb communication with device
import usb
import yaml

path = os.path.join(os.path.dirname(__file__), "config.yaml")
# Loading tablet configuration
with open(path, "r") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)


# Get the required ecodes from configuration
pen_codes = []
btn_codes = []
for k, v in config["actions"].items():
    codes = btn_codes if k == "tablet_buttons" else pen_codes
    if isinstance(v, list):
        codes.extend(v)
    else:
        codes.append(v)


temp = []
for c in pen_codes:
    temp.extend([ecodes.ecodes[x] for x in c.split("+")])
pen_codes = temp

temp = []
for c in btn_codes:
    temp.extend([ecodes.ecodes[x] for x in c.split("+")])
btn_codes = temp

pen_events = {
    ecodes.EV_KEY: pen_codes,
    ecodes.EV_ABS: [
        #AbsInfo input: value, min, max, fuzz, flat
        (ecodes.ABS_X, AbsInfo(0, 0, config['pen']['max_x'], 0, 0, config["pen"]["resolution_x"])),         
        (ecodes.ABS_Y, AbsInfo(0, 0, config['pen']['max_y'], 0, 0, config["pen"]["resolution_y"])),
        (ecodes.ABS_PRESSURE, AbsInfo(0, 0, config['pen']['max_pressure'], 0, 0, 0))
    ],
}

btn_events = {ecodes.EV_KEY: btn_codes}

# Find the device
dev = usb.core.find(idVendor=config["vendor_id"], idProduct=config["product_id"])
# Select end point for reading second interface [2] for actual data
# I don't know what [0] and [1] are used for
ep = dev[0].interfaces()[2].endpoints()[0]
# Reset the device (don't know why, but till it works don't touch it)
dev.reset()

# Drop default kernel driver from all devices
for j in [0, 1, 2]:
    if dev.is_kernel_driver_active(j):
        dev.detach_kernel_driver(j)

# Set new configuration
dev.set_configuration()

vpen = UInput(events=pen_events, name=config["xinput_name"], version=0x3)
vbtn = UInput(events=btn_events, name=config["xinput_name"] + "_buttons", version=0x3)

pressed = -1

max_x = config['pen']['max_x']
max_y = config['pen']['max_y']

# Standart directions
decode_x = lambda data: max_x - (data[5] * 255 + data[4])
decode_y = lambda data: data[3] * 255 + data[2]

if config["settings"]["swap_directions"]:
    if config["settings"]["swap_axis"]:
        # Inverse axis and inverse directions
        decode_x = lambda data: max_x - (data[3] * 255 + data[2])
        decode_y = lambda data: data[5] * 255 + data[4]
    else:
        # Inverse directions
        decode_x = lambda data: data[5] * 255 + data[4]
        decode_y = lambda data: max_y - (data[3] * 255 + data[2])
elif config["settings"]["swap_axis"]:
    # Inverse axis
    decode_x = lambda data: data[3] * 255 + data[2]
    decode_y = lambda data: max_y - (data[5] * 255 + data[4])

# Infinite loop
while True:
    try:
        data = dev.read(ep.bEndpointAddress, ep.wMaxPacketSize)
        if data[1] in [192, 193]: # Pen actions

            pen_x = decode_x(data)
            pen_y = decode_y(data)

            pen_pressure = data[7] * 255 + data[6]
            vpen.write(ecodes.EV_ABS, ecodes.ABS_X, pen_x)
            vpen.write(ecodes.EV_ABS, ecodes.ABS_Y, pen_y)
            vpen.write(ecodes.EV_ABS, ecodes.ABS_PRESSURE, pen_pressure)
            if data[1] == 192: # Pen touch
                vpen.write(ecodes.EV_KEY, ecodes.BTN_TOUCH, 0)
            else:
                vpen.write(ecodes.EV_KEY, ecodes.BTN_TOUCH, 1)
        elif data[0] == 2: # Tablet button actions
            # press types: 0 - up; 1 - down; 2 - hold
            press_type = 1
            if data[1] == 2: # First button
                pressed = 0
            elif data[1] == 4: # Second button
                pressed = 1
            elif data[3] == 44: # Third button
                pressed = 2
            elif data[3] == 43: # Fourth button
                pressed = 3
            else:
                press_type = 0
            key_codes = config["actions"]["tablet_buttons"][pressed].split("+")
            for key in key_codes:
                act = ecodes.ecodes[key]
                vbtn.write(ecodes.EV_KEY, act, press_type)
        # Flush
        vpen.syn()
        vbtn.syn()
    except usb.core.USBError as e:
        if e.args[0] == 19:
            vpen.close()
            raise Exception('Device has been disconnected')
    except KeyboardInterrupt:
    	vpen.close()
    	vbtn.close()
    	sys.exit("\nDriver terminated successfully.")
    except Excception as e:
    	print(e)
