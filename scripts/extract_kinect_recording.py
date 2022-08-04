"""Extract an MKV Kinect recording as a set of color/depth images."""
from argparse import ArgumentParser
from pathlib import Path

import open3d as o3d


def get_arg_parser():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        'recording',
        help="Path to the MKV Kinect recording"
    )
    return parser


def main():
    conf = vars(get_arg_parser().parse_args())
    recording_path = Path(conf['recording'])

    reader = o3d.io.AzureKinectMKVReader()
    reader.open(str(recording_path))
    if not reader.is_opened():
        raise RuntimeError(f"Unable to open file {recording_path}.")
    metadata = reader.get_metadata()
    o3d.io.write_azure_kinect_mkv_metadata(
        str(recording_path.with_suffix(".json")),
        metadata
    )
    idx = 0
    color_dir = recording_path.parent / "color"
    color_dir.mkdir(exist_ok=True)
    depth_dir = recording_path.parent / "depth"
    depth_dir.mkdir(exist_ok=True)
    while not reader.is_eof():
        rgbd = reader.next_frame()
        if rgbd is None:
            # Skip invalid frames
            continue
        color_path = color_dir / f"{idx:05d}.jpg"
        o3d.io.write_image(str(color_path), rgbd.color)
        depth_path = depth_dir / f"{idx:05d}.png"
        o3d.io.write_image(str(depth_path), rgbd.depth)
        if idx % 100 == 0:
            print(f"Wrote {color_path.name}")
        idx += 1


if __name__ == "__main__":
    main()
