"""
Collect and save telemetry from Google Cloud Pub/Sub topics.
"""
import argparse
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from trkpy.cloud import AWSClient
from trkpy.collect import CloudCollector


def get_arg_parser():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        required=True,
        help="Path to the YAML config file."
    )
    parser.add_argument(
        "--write_after",
        default=300,
        type=int,
        help="Flush logs older than this amount (in seconds). Default: 300",
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
    # Process authentication file paths.
    auth_dir = conf['global']['auth_dir']
    for provider, cloud_conf in conf['cloud'].items():
        cloud_conf['ca_certs'] = auth_dir / provider / cloud_conf['ca_certs']
        cloud_conf['device_private_key'] = (
            auth_dir / provider / cloud_conf['device_private_key']
        )
        if 'device_cert' in cloud_conf:
            cloud_conf['device_cert'] = (
                auth_dir / provider / cloud_conf['device_cert']
            )
    return conf


def init_logger():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler()
    stream_formatter = logging.Formatter(
        fmt='|{asctime}|{levelname}|{name}|{funcName}|{message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    stream_handler.setFormatter(stream_formatter)
    root_logger.addHandler(stream_handler)


def main():
    """Entry point."""
    init_logger()
    conf = get_config()
    print(conf)
    client = AWSClient(**conf['cloud']['aws'], publisher=False)
    out_dir = Path(conf['global']['out_dir'])
    subscriptions = ['location', 'error', 'debug']
    types = ['json', 'str', 'str']
    collector = CloudCollector(
        client,
        subscriptions,
        types,
        flush_dir=out_dir,
    )
    write_after = timedelta(seconds=conf['write_after'])
    try:
        while True:
            write_time = datetime.now(timezone.utc) - write_after
            collector.flush(older_than=write_time)
            time.sleep(60)
    except KeyboardInterrupt:
        client.disconnect()
        return


if __name__ == "__main__":
    main()
