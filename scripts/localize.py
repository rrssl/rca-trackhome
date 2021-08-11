"""
Script demonstrating how to use the Pozyx system to localize a device.
"""
import json
import os
import time
from argparse import ArgumentParser
from configparser import ConfigParser

import pypozyx as px

from trkpy import track


def init_master(retry_wait: float = 1, max_attempts: int = 10):
    """Initialize the master tag."""
    serial_port = px.get_first_pozyx_serial_port()
    if serial_port is None:
        raise OSError("No Pozyx connected. Check your USB cable or driver!")
    for i in range(max_attempts):
        try:
            master = px.PozyxSerial(serial_port)
        except OSError:
            if i == max_attempts-1:
                raise
            print("Master tag is busy. Retrying in {retry_wait}s.")
            time.sleep(retry_wait)
        else:
            break
    return master


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
    master = init_master()
    remote_id = profile['remote_id']
    if remote_id is None:
        master.printDeviceInfo(remote_id)
    else:
        for device_id in [None, remote_id]:
            master.printDeviceInfo(device_id)
    # Configure anchors.
    anchors = {int(k): v for k, v in profile['anchors'].items()}
    status = track.set_anchors_manual(master, anchors, remote_id=remote_id)
    if (
        status != px.POZYX_SUCCESS
        or track.get_num_anchors(master, remote_id) != len(anchors)
    ):
        print(track.get_latest_error(master, "Configuration", remote_id))
    print(track.get_config_str(master, remote_id))
    # Start positioning loop.
    pos_dim = getattr(px.PozyxConstants, config['tracking']['pos_dim'])
    pos_algo = getattr(px.PozyxConstants, config['tracking']['pos_algo'])
    remote_name = track.get_network_name(remote_id)
    while True:
        pos = px.Coordinates()
        status = master.doPositioning(
            pos, dimension=pos_dim, algorithm=pos_algo, remote_id=remote_id
        )
        if status == px.POZYX_SUCCESS:
            print(f"POS [{remote_name}]: ({track.get_position_str(pos)})")
        else:
            print(track.get_latest_error(master, "Positioning", remote_id))
        time.sleep(.1)


if __name__ == "__main__":
    main()
