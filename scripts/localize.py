"""
Script demonstrating how to use the Pozyx system to localize a device.
"""
import json
import os
import time
from argparse import ArgumentParser
from configparser import ConfigParser
from datetime import datetime
from pathlib import Path
from pprint import pprint

import numpy as np
import pypozyx as px
import yaml

from trkpy import track


class Tracker:
    def __init__(self, interface):
        self.interface = interface
        self.pos_dim = None
        self.pos_algo = None
        self.remote_ids = []

        # Make sure the tracker has no control over the LEDs.
        led_config = 0x0
        self.interface.setLedConfig(led_config)
        for remote_id in self.remote_ids:
            self.interface.setLedConfig(led_config, remote_id)

    def localize(self, device_id: int = None):
        """Localize the device."""
        self.interface.setLed(1, True, device_id)
        pos = track.do_positioning(
            self.interface, self.pos_dim, self.pos_algo, device_id
        )
        if pos:
            t_now = time.time()
            remote_name = track.get_network_name(device_id)
            print(f"POS [{remote_name}] (t={t_now}s): {pos}")
        else:
            print(
                track.get_latest_error(
                    self.interface, "Positioning", device_id
                )
            )
        self.interface.setLed(1, False, device_id)


def get_arg_parser():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        '--config',
        metavar='FILE',
        required=True,
        help="Path to the config file"
    )
    parser.add_argument(
        '--profile',
        required=True,
        help="Name of the profile"
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=.1,
        help="Interval in seconds between measurements (default 0.1s)"
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help="Use this flag to save the measurements"
    )
    return parser


def get_config():
    # Load the configuration.
    aconf, fconf_override = get_arg_parser().parse_known_args()
    with open(aconf.config, 'r') as handle:
        fconf = yaml.safe_load(handle)
    # Override file config with "--section.option val" command line arguments.
    it = iter(fconf_override)
    for name, val in zip(it, it):
        section, option = name[2:].split('.')
        fconf[section][option] = val
    # Preprocess paths to make life easier.
    for section in fconf.values():
        for key, value in section.items():
            if not isinstance(value, str):
                continue
            if "/" in value or value in (".", "..", "~"):  # UNIX path
                section[key] = Path(value)
    # Merge configs.
    conf = vars(aconf) | fconf['global'] | fconf['tracking']
    return conf


def main():
    """Entry point"""
    # Parse arguments and load configuration and profile.
    parser = get_arg_parser()
    args = parser.parse_args()
    config = ConfigParser()
    config.read(args.config)
    data_path = config['global']['data_path']
    profile_path = os.path.join(data_path, f"{args.profile}.json")
    with open(profile_path) as handle:
        profile = json.load(handle)
    # Initialize tags.
    master = track.init_master(timeout=1)
    remote_id = profile['remote_id']
    if remote_id is None:
        master.printDeviceInfo(remote_id)
    else:
        for device_id in [None, remote_id]:
            master.printDeviceInfo(device_id)
    # Configure anchors.
    success = track.set_anchors_manual(
        master, profile['anchors'], remote_id=remote_id
    )
    if success:
        pprint(track.get_anchors_config(master, remote_id))
    else:
        print(track.get_latest_error(master, "Configuration", remote_id))
    # Start positioning loop.
    pos_dim = getattr(px.PozyxConstants, config['tracking']['pos_dim'])
    pos_algo = getattr(px.PozyxConstants, config['tracking']['pos_algo'])
    remote_name = track.get_network_name(remote_id)
    if args.save:
        pos_data = []
    t_start = time.time()
    try:
        while True:
            t_now = time.time() - t_start
            pos = track.do_positioning(master, pos_dim, pos_algo, remote_id)
            if pos:
                print(f"POS [{remote_name}] (t={t_now}s): {pos}")
                if args.save:
                    pos_data.append((t_now,) + pos)
            else:
                print(track.get_latest_error(master, "Positioning", remote_id))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        if args.save:
            pos_data = np.single(pos_data)
            file_name = (
                f"recording{datetime.now().strftime('_%Y%m%d%H%M%S')}-"
                f"{args.profile}.npy"
            )
            file_path = os.path.join(data_path, file_name)
            np.save(file_path, pos_data)


if __name__ == "__main__":
    main()
