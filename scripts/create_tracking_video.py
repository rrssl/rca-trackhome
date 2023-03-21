import json
from argparse import ArgumentParser
from pathlib import Path

import matplotlib.animation as ma
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from PIL import Image


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
        '--dummy',
        action='store_true',
        help="Use a dummy RTLS"
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
    conf = get_config()
    data_dir = conf['global']['data_dir'] / conf['place']
    profile_path = data_dir / conf['experiment'] / conf['profile']
    with open(profile_path, 'r') as handle:
        profile = json.load(handle)
    anchors = profile['anchors']
    recording_path = data_dir / conf['experiment'] / "location.csv"
    floorplan_path = data_dir / conf['floorplan']
    # Load the floorplans.
    floorplan_img = Image.open(floorplan_path)
    # Scale and align the floorplans.
    # Load and clean the data.
    data = pd.read_csv(recording_path)
    data = data[
        (data['msg_sender'] == conf['device']) & (data['i'] == conf['tag_id'])
    ]
    timestamps = pd.to_datetime(
        data['t'], unit='ms', utc=True
    ).dt.tz_convert("Europe/London")
    data = data.set_index(timestamps)
    data = data.sort_index()
    data = data.drop(data[(data['x'] == 0) & (data['y'] == 0)].index)
    data = data.loc[~(
        (data['x'].shift(-1) == data['x']) & (data['y'].shift(-1) == data['y'])
    )]
    # Transform the coordinates depending on the floor.
    data = data.drop(data[data['z'] > 2800].index)
    # Resample the coordinates to the framerate.
    # Create the first frame.
    fig, ax = plt.subplots(figsize=conf['figsize'])
    ax.set_axis_off()
    ax.imshow(
        np.asarray(floorplan_img),
        extent=floorplan_display.get_extent(),
        zorder=2
    )
    ax.scatter(
        *zip(*[xyz[:2] for xyz in anchors.values()]),
        marker='s',
        zorder=3
    )
    for name, xyz in anchors.items():
        ax.annotate(name, xyz[:2], xytext=(5, 5), textcoords='offset pixels',
                    path_effects=[pe.withStroke(linewidth=2, foreground='w')])
    ax.set_aspect('equal')
    bg_plot = ax.scatter(
        data['x'],
        data['y'],
        c='tab:pink',
        alpha=.2,
        edgecolor='none',
        s=25,
        zorder=5
    )
    pos_plot = ax.scatter(
        data['x'].iloc[0],
        data['y'].iloc[0],
        c='tab:red',
        s=50,
        zorder=5
    )
    pos_line_plot, = ax.plot(
        data['x'],
        data['y'],
        c='tab:pink',
        alpha=.2,
        lw=1,
        zorder=4
    )
    # Initialise the video.
    FFMpegWriter = ma.writers['ffmpeg']
    metadata = dict(title='Movie Test', artist='Matplotlib',
                    comment='a red circle following a blue sine wave')
    writer = FFMpegWriter(fps=15, metadata=metadata)
    # Generate the frames.
    with writer.saving(fig, "writer_test.mp4", dpi=100):
        for i in range(10):
            pos_plot.set_offsets(data[['x', 'y']].iloc[i])
            pos_line_plot.set_data(data['x'].iloc[:i+1], data['y'].iloc[:i+1])
            # slider_text.value = data.index[i].strftime('%H:%M:%S')
            writer.grab_frame()


if __name__ == "__main__":
    main()
