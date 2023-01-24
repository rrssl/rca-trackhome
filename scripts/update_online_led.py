"""Routine that turns on the G2 LED if there is a working internet connection.

Usage: python update_online_led.py
"""
from gpiozero import JamHat

from trkpy.system import is_online


def main():
    hat = JamHat()
    led = hat.lights_2.green
    if is_online():
        if not led.is_lit:
            led.on()
    else:
        if led.is_lit:
            led.off()


if __name__ == "__main__":
    main()
