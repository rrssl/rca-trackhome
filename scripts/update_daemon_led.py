"""Routine that turns on the R2 LED if the tracker daemon is not running.

Usage: python update_daemon_led.py path/to/config.yml
"""
import sys
from multiprocessing.connection import Client

import yaml

from trkpy.system import lock_file


def main():
    conf_path = sys.argv[1]
    with open(conf_path, 'r') as handle:
        conf = yaml.safe_load(handle)
    lock_path = conf['daemon']['lock_file']
    address_out = tuple(conf['hat']['address_out'])
    led = 'R2'
    not_running = lock_file(lock_path)
    try:
        with Client(address_out) as conn:
            conn.send((led, not_running))
    except ConnectionRefusedError:
        return


if __name__ == "__main__":
    main()
