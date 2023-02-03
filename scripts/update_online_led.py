"""Routine that turns on the G2 LED if there is a working internet connection.

Usage: python update_online_led.py
"""
from multiprocessing.connection import Client

from trkpy.system import is_online


def main():
    address = ('localhost', 8888)
    led = 'G2'
    if is_online():
        with Client(address) as conn:
            conn.send((led, True))
    else:
        with Client(address) as conn:
            conn.send((led, False))


if __name__ == "__main__":
    main()
