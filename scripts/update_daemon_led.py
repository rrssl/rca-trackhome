"""Routine that turns on the R2 LED if the tracker daemon is not running.

Usage: python update_daemon_led.py path/to/config.yml
"""
import sys
import yaml
from gpiozero import JamHat

from trkpy.system import lock_file


def main():
    conf_path = sys.argv[1]
    with open(conf_path, 'r') as handle:
        conf = yaml.safe_load(handle)
    lock_path = conf['daemon']['lock_file']
    hat = JamHat()
    led = hat.lights_2.red
    if lock_file(lock_path):
        if not led.is_lit:
            led.on()
    else:
        if led.is_lit:
            led.off()


if __name__ == "__main__":
    main()
