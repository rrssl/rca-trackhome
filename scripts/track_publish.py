"""Main script used to track location and publish to the cloud."""
import json
import logging
import time
from argparse import ArgumentParser
from pathlib import Path

import yaml

from trkpy import track
from trkpy.publish import CloudHandler


class Tracker:
    """High-level manager of the real-time location system."""

    def __init__(
        self,
        profile_path: str,
        logger: logging.Logger,
        pos_dim: int,
        pos_algo: int,
        timeout: float
    ):
        self.logger = logger
        self.pos_dim = pos_dim
        self.pos_algo = pos_algo
        self.wait_time = .5  # wait time between tags

        # Init the interface.
        self.interface = track.init_master(timeout=timeout)
        # Init the devices.
        with open(profile_path) as handle:
            profile = json.load(handle)
        self.tags = [t if t is None else int(t, 16) for t in profile['tags']]
        self.anchors = {
            int(a, 16): tuple(xyz) for a, xyz in profile['anchors'].items()
        }
        for tag in self.tags:
            self.configure_tag(tag)
        self._tags_to_reconfigure = set()

    def check(self):
        """Check that all devices are currently connected."""
        for tag_id in self.tags:
            name = track.get_network_name(tag_id)
            details = track.get_device_details(self.interface, tag_id)
            if details is not None:
                test_whoami = details.who_am_i == 0x43
                test_type = details.selftest == 0b111111
                if test_whoami and test_type:
                    self.logger.debug(f"TAG {name} STATUS GOOD")
                    continue
            self._tags_to_reconfigure.add(tag_id)
            self.logger.error(f"TAG {name} STATUS BAD")
        for anchor_id in self.anchors:
            name = track.get_network_name(anchor_id)
            details = track.get_device_details(self.interface, anchor_id)
            if details is not None:
                test_whoami = details.who_am_i == 0x43
                test_type = details.selftest == 0b110000
                if test_whoami and test_type:
                    self.logger.debug(f"ANCHOR {name} STATUS GOOD")
                    continue
            self.logger.error(f"ANCHOR {name} STATUS BAD")

    def configure_tag(self, tag_id: int):
        # Configure anchors.
        tag_anchors = track.get_anchors_config(self.interface, tag_id)
        if tag_anchors != self.anchors:
            success = track.set_anchors_manual(
                self.interface, self.anchors,
                save_to_flash=True, remote_id=tag_id
            )
            if success:
                self.log_anchor_config(tag_id)
            else:
                self.logger.error(track.get_latest_error(
                    self.interface, "Configuration", tag_id
                ))
        # Make sure the tags have no control over the LEDs.
        led_config = 0x0
        self.interface.setLedConfig(led_config, tag_id)

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
        for tag_id in self.tags:
            self.interface.setLed(1, True, tag_id)
            time.sleep(self.wait_time)
            responses[tag_id] = self.localize(tag_id)
            self.interface.setLed(1, False, tag_id)
        for tag_id, res in responses.items():
            if res['success']:
                if tag_id in self._tags_to_reconfigure:
                    self.configure_tag(tag_id)
                    self._tags_to_reconfigure.remove(tag_id)
                else:
                    datum = {
                        'x': res['pos'][0],
                        'y': res['pos'][1],
                        'z': res['pos'][2],
                        'i': track.get_network_name(tag_id),
                        't': int(res['t'] * 1000)  # format expected by topic
                    }
                    payload = json.dumps(datum)
                    self.logger.info(payload)
            else:
                self._tags_to_reconfigure.add(tag_id)
                self.logger.error(res['err'])

    def log_anchor_config(self, tag_id: int):
        anchors = track.get_anchors_config(self.interface, tag_id)
        tag_str = track.get_network_name(tag_id)
        for anchor, coords in anchors.items():
            self.logger.debug(
                f"Anchor {track.get_network_name(anchor)} configured on tag "
                f"{tag_str}: {coords}"
            )


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
    # Parse arguments and load configuration.
    conf = get_config()
    data_dir = conf['global']['data_dir']
    profile_path = data_dir / conf['profile']
    pos_dim = conf['tracking']['pos_dim']
    pos_algo = conf['tracking']['pos_algo']
    pos_period = conf['interval']
    timeout = conf['tracking']['timeout']
    check_every_n_loops = conf['tracking']['check_period']
    name = Path(__file__).with_suffix("").name
    out_dir = conf['global']['out_dir']
    log_path = out_dir / f"{name}.log"
    # Create loggers.
    # - root logger: logs to a local file.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(log_path, encoding='ascii')
    file_formatter = logging.Formatter(
        fmt='|{asctime}|{levelname}|{name}|{funcName}|{message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    # - cloud logger.
    cloud_logger = logging.getLogger("cloud")
    cloud_handler = CloudHandler(**conf['publish'])
    cloud_logger.addHandler(cloud_handler)
    # Initialize the tracker.
    tracker = Tracker(profile_path, cloud_logger, pos_dim, pos_algo, timeout)
    # Start tracking.
    loop_cnt = 0
    try:
        cloud_logger.debug("Starting.")
        while True:
            t_start = time.time()
            if loop_cnt % check_every_n_loops == 0:
                tracker.check()
                # for tag in tracker.tags:
                #     tracker.log_anchor_config(tag)
            loop_cnt += 1
            tracker.loop()
            t_elapsed = time.time() - t_start
            time.sleep(pos_period - t_elapsed)
    except KeyboardInterrupt:
        cloud_logger.debug("Exiting.")
        cloud_handler.client.disconnect()


if __name__ == "__main__":
    main()
