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
        '--place',
        required=True,
        help="Name of the experiment's place"
    )
    parser.add_argument(
        '--floorplan',
        required=True,
        help="Path of the floorplan in the place's floorplan dir"
    )
    parser.add_argument(
        '--profile',
        required=True,
        help="Path of the profile in the place's floorplan dir"
    )
    parser.add_argument(
        '--experiment',
        required=True,
        help="Name of the experiment in the place's tracking dir"
    )
    # parser.add_argument(
    #     '--dummy',
    #     action='store_true',
    #     help="Dummy"
    # )
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
    floorplan_path = data_dir / "floorplan" / conf['floorplan']
    profile_path = data_dir / "floorplan" / conf['profile']
    with open(profile_path, 'r') as handle:
        profile = json.load(handle)
    record_path = data_dir / "tracking" / conf['experiment'] / "location.csv"
    # Load the floorplans.
    floorplan_img = Image.open(floorplan_path)
    # Scale and align the anchors.
    anchors_names = list(profile['anchors'].keys())
    anchors_floors = {}
    for floor, floor_anchors in profile['floors'].items():
        for fa in floor_anchors:
            anchors_floors[fa] = floor
    anchors_xforms = np.array([
        profile['transforms'][anchors_floors[a]] for a in anchors_names
    ])
    anchors_3d = np.array(list(profile['anchors'].values()), dtype=float)
    anchors_2d = anchors_3d[:, :2].copy()
    anchors_2d[:, 1] = anchors_3d[:, 1].max() - anchors_2d[:, 1]  # swap y axis
    anchors_2d *= anchors_xforms[:, 2:]
    anchors_2d += anchors_xforms[:, :2]
    # Load and clean the data.
    record = pd.read_csv(record_path)
    record = record[record['i'].isin(profile['tags'])]
    record = record.set_index(
        pd.to_datetime(
            record['t'], unit='ms', utc=True
        ).dt.tz_convert("Europe/London")
    ).sort_index()
    record = record.drop(record[(record['x'] == 0) & (record['y'] == 0)].index)
    record = record.drop(record[
        (record['x'].shift(-1) == record['x'])
        & (record['y'].shift(-1) == record['y'])
    ].index)
    # Assign locations to a floor.
    floor_maxima = {
        floor: max(profile['anchors'][fa][2] for fa in floor_anchors)
        for floor, floor_anchors in profile['floors'].items()
    }
    record['floor'] = ""
    for floor, floor_max in sorted(
            floor_maxima.items(), key=lambda it: it[1], reverse=True):
        record.loc[record['z'] < floor_max, 'floor'] = floor
    record = record.drop(record[record['floor'] == ""].index)
    # Change coordinates depending on the floor.
    data_xforms = np.vstack(record['floor'].map(profile['transforms']))
    record['y'] = anchors_3d[:, 1].max() - record['y']  # swap y axis
    record[['x', 'y']] = record[['x', 'y']].multiply(data_xforms[:, 2:])
    record[['x', 'y']] = record[['x', 'y']].add(data_xforms[:, :2])
    # TODO Resample the coordinates to the framerate.
    # Define the points' colors.
    colormap = dict(zip(profile['tags'], ['tab:pink', 'tab:olive']))
    record['c'] = record['i'].map(colormap)
    # Create the first frame.
    plt.rcParams['figure.facecolor'] = 'black'
    fig, ax = plt.subplots()  # figsize=conf['figsize'])
    ax.set_axis_off()
    ax.imshow(np.asarray(floorplan_img), zorder=2)
    ax.scatter(*anchors_2d.T, marker='s', s=10, zorder=3)
    for name, xy in zip(anchors_names, anchors_2d):
        ax.annotate(name, xy, xytext=(5, 5), textcoords='offset pixels',
                    path_effects=[pe.withStroke(linewidth=2, foreground='w')],
                    fontsize=4)
    bg_plot = ax.scatter(
        record['x'],
        record['y'],
        c=record['c'],
        alpha=.2,
        edgecolor='none',
        s=25,
        zorder=5
    )
    plt.show()
    # pos_plot = ax.scatter(
    #     data['x'].iloc[0],
    #     data['y'].iloc[0],
    #     c='tab:red',
    #     s=50,
    #     zorder=5
    # )
    # pos_line_plot, = ax.plot(
    #     data['x'],
    #     data['y'],
    #     c='tab:pink',
    #     alpha=.2,
    #     lw=1,
    #     zorder=4
    # )
    # # Initialise the video.
    # FFMpegWriter = ma.writers['ffmpeg']
    # metadata = dict(title='Movie Test', artist='Matplotlib',
    #                 comment='a red circle following a blue sine wave')
    # writer = FFMpegWriter(fps=15, metadata=metadata)
    # # Generate the frames.
    # with writer.saving(fig, "writer_test.mp4", dpi=100):
    #     for i in range(10):
    #         pos_plot.set_offsets(data[['x', 'y']].iloc[i])
    #         pos_line_plot.set_data(data['x'].iloc[:i+1], data['y'].iloc[:i+1])
    #         # slider_text.value = data.index[i].strftime('%H:%M:%S')
    #         writer.grab_frame()


if __name__ == "__main__":
    main()
