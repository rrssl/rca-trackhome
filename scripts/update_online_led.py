"""Routine that turns on the G2 LED if there is a working internet connection.

Usage: python update_online_led.py path/to/config.yml
"""
import sys
from multiprocessing.connection import Client

import yaml

from trkpy.system import is_online


def main():
    conf_path = sys.argv[1]
    with open(conf_path, 'r') as handle:
        conf = yaml.safe_load(handle)
    address_out = tuple(conf['hat']['address_out'])
    led = 'G2'
    online = is_online()
    try:
        with Client(address_out) as conn:
            conn.send((led, online))
    except ConnectionRefusedError:
        return


if __name__ == "__main__":
    main()
