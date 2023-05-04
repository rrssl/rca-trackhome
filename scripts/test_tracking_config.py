"""Validate the tracking config against the predefined schema."""
import argparse
import json

from jsonschema.exceptions import ValidationError

from trkpy.validate import validate_tracking_config


def get_arg_parser():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        required=True,
        help="Path to the JSON config file."
    )
    return parser


def main():
    args = get_arg_parser().parse_args()
    with open(args.config, 'r') as handle:
        conf = json.load(handle)
    try:
        validate_tracking_config(conf)
    except ValidationError as e:
        print(e.message)


if __name__ == "__main__":
    main()
