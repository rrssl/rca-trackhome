"""
Script demonstrating how to use the Pozyx system to localize a device.
"""
import json
import logging
import time
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

# import numpy as np
import pypozyx as px
import yaml

from trkpy import track


class Tracker:
    """High-level manager of the real-time location system."""

    def __init__(
        self,
        profile_path: str,
        pos_dim: int,
        pos_algo: int,
        timeout: float
    ):
        self.pos_dim = pos_dim
        self.pos_algo = pos_algo
        self.wait_time = .5  # wait time between tags

        # Init the log.
        logging.basicConfig(level=logging.DEBUG)
        # Init the devices.
        with open(profile_path) as handle:
            profile = json.load(handle)
        interface = track.init_master(timeout=timeout)
        tags = [t if t is None else int(t, 16) for t in profile['tags']]
        for device_id in tags:
            # interface.printDeviceInfo(device_id)
            # Configure anchors.
            success = track.set_anchors_manual(
                interface, profile['anchors'],
                save_to_flash=False, remote_id=device_id
            )
            if success:
                anchors = track.get_anchors_config(interface, device_id)
                for anchor, coords in anchors.items():
                    logging.info(f"Anchor {anchor}: {coords}")
            else:
                logging.error(track.get_latest_error(
                    interface, "Configuration", device_id
                ))
            # Make sure the tags have no control over the LEDs.
            led_config = 0x0
            interface.setLedConfig(led_config, device_id)

        self.interface = interface
        self.tags = tags

    def localize(self, device_id: int = None):
        """Localize the device."""
        t_now = time.time()
        pos = track.do_positioning(
            self.interface, self.pos_dim, self.pos_algo, device_id
        )
        if pos:
            res = {'success': True, 't': t_now, 'pos': pos}
        else:
            error_msg = track.get_latest_error(
                self.interface, "Positioning", device_id
            )
            res = {'success': False, 't': t_now, 'err': error_msg}
        return res

    def loop(self):
        """Loop through all the devices to localize them."""
        responses = {}
        for device_id in self.tags:
            self.interface.setLed(1, True, device_id)
            time.sleep(self.wait_time)
            responses[device_id] = self.localize(device_id)
            self.interface.setLed(1, False, device_id)
        for device_id, res in responses.items():
            name = track.get_network_name(device_id)
            local_t = datetime.fromtimestamp(
                res['t']
            ).strftime('%Y-%m-%d %H:%M:%S')
            if res['success']:
                logging.info(f"POS[{name}]({local_t}): {res['pos']}")
            else:
                logging.error(f"ERR[{name}]({local_t}): {res['err']}")


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
        default=1,
        help="Interval in seconds between measurements (default 1s)"
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
    args = iter(fconf_override)
    for name, val in zip(args, args):
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
    conf = vars(aconf) | fconf
    return conf


def main():
    """Entry point"""
    # Parse arguments and load configuration and profile.
    conf = get_config()
    data_dir = conf['global']['data_dir']
    profile_path = data_dir / conf['profile']
    pos_dim = getattr(px.PozyxConstants, conf['tracking']['pos_dim'])
    pos_algo = getattr(px.PozyxConstants, conf['tracking']['pos_algo'])
    timeout = 1
    tracker = Tracker(profile_path, pos_dim, pos_algo, timeout)
    pos_period = conf['interval']
    try:
        while True:
            t_start = time.time()
            tracker.loop()
            t_elapsed = time.time() - t_start
            time.sleep(pos_period - t_elapsed)
    except KeyboardInterrupt:
        logging.info("Exiting.")
        # if args.save:
        #     pos_data = np.single(pos_data)
        #     file_name = (
        #         f"recording{datetime.now().strftime('_%Y%m%d%H%M%S')}-"
        #         f"{args.profile}.npy"
        #     )
        #     file_path = data_dir / file_name
        #     np.save(file_path, pos_data)


if __name__ == "__main__":
    main()
