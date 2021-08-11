"""
Script demonstrating how to use the Pozyx system to localize a device.
"""
import json
import os
import time
from argparse import ArgumentParser
from configparser import ConfigParser
from pprint import pprint

import pypozyx as px

from trkpy import track


def main():
    """Entry point"""
    # Parse arguments and load configuration and profile.
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('profile', help="Name of the profile")
    parser.add_argument('-c', '--config', help="Path to the config file")
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
    while True:
        pos = track.do_positioning(master, pos_dim, pos_algo, remote_id)
        if pos:
            print(f"POS [{remote_name}]: {pos}")
        else:
            print(track.get_latest_error(master, "Positioning", remote_id))
        time.sleep(.1)


if __name__ == "__main__":
    main()
