import json
from argparse import ArgumentParser
from pathlib import Path

import matplotlib.animation as ma
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
# import pandasgui
import yaml
from PIL import Image
from tqdm import tqdm


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
        help="Path of the profile in the data dir"
    )
    parser.add_argument(
        '--speed',
        required=True,
        type=int,
        help="Seconds of recording per second of video"
    )
    parser.add_argument(
        '--fps',
        required=True,
        type=int,
        help="Frames per second of the video (independent of the replay speed)"
    )
    parser.add_argument(
        '--video',
        help="Path of the video in the output dir; if omitted, just play"
    )
    parser.add_argument(
        '--frames',
        type=int,
        help="Optional number of frames to output"
    )
    parser.add_argument(
        '--show_trace',
        action='store_true',
        help="Show the trace of tracking points"
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


def get_plot_updater(tag_plots, record, time_plot, trace_plot):
    def update(frame):
        time_plot.set_text(frame)
        for tag, tag_plot in tag_plots.items():
            try:
                row = record.loc[(frame, tag)]
            except KeyError:
                tag_plot.set_alpha(.2)
                continue
            tag_plot.set_offsets(row[['x', 'y']])
            tag_plot.set_alpha(.8)
        if trace_plot is not None:
            trace = record.loc[:frame]
            trace_plot.set_offsets(trace[['x', 'y']])
            trace_plot.set_facecolor(trace['c'])
        # line_plot.set_data(data['x'].iloc[:fid+1], data['y'].iloc[:fid+1])
    return update


def main():
    conf = get_config()
    data_dir = conf['global']['data_dir']
    profile_path = data_dir / conf['profile']
    with open(profile_path, 'r') as handle:
        profile = json.load(handle)
    floorplan_path = data_dir / profile['files']['floorplan']
    record_path = data_dir / profile['files']['recording']
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
        ).dt.tz_convert(profile['timezone'])
    )
    record = record.drop(  # remove points at (0, 0)
        record[(record['x'] == 0) & (record['y'] == 0)].index
    )
    tags_record = []
    target_period = conf['speed'] // conf['fps']
    assert target_period >= 1, "Speed must be higher than the FPS"
    for tag, tag_record in record.groupby('i'):  # tag-specific cleaning
        # Remove consecutive duplicates.
        tag_record = tag_record.sort_index()
        tag_record = tag_record.drop(tag_record[
            (tag_record['x'].shift(1) == tag_record['x'])
            & (tag_record['y'].shift(1) == tag_record['y'])
        ].index)
        # First downsample to remove some of the noise.
        tag_record = tag_record[['x', 'y', 'z']].resample('T').mean().dropna()
        # Then upsample to match the target speed given the framerate.
        tag_record = tag_record[['x', 'y', 'z']].resample(
            f'{target_period}S'
        ).interpolate('time', limit=2).dropna()
        # Save records.
        tag_record['i'] = tag
        tags_record.append(tag_record)
    record = pd.concat(
        tags_record
    ).set_index('i', append=True).sort_index()
    # pandasgui.show(record)
    # Assign locations to a floor.
    floor_maxima = {
        floor: max(profile['anchors'][fa][2] for fa in floor_anchors)
        for floor, floor_anchors in profile['floors'].items()
    }
    record['floor'] = ""
    for floor, floor_max in sorted(
            floor_maxima.items(), key=lambda it: it[1], reverse=True):
        record.loc[record['z'] < floor_max+1000, 'floor'] = floor
    record = record.drop(record[record['floor'] == ""].index)
    # Change coordinates depending on the floor.
    data_xforms = np.vstack(record['floor'].map(profile['transforms']))
    record['y'] = anchors_3d[:, 1].max() - record['y']  # swap y axis
    record[['x', 'y']] = record[['x', 'y']].multiply(data_xforms[:, 2:])
    record[['x', 'y']] = record[['x', 'y']].add(data_xforms[:, :2])
    # Define the points' colors.
    cmap = dict(zip(profile['tags'], ['tab:pink', 'tab:olive']))
    record['c'] = record.index.get_level_values('i').map(cmap)
    # Create the first frame.
    plt.rcParams['figure.facecolor'] = 'black'
    fig, ax = plt.subplots(figsize=(16, 9), dpi=120, frameon=False)
    ax.set_axis_off()
    ax.imshow(np.asarray(floorplan_img), zorder=2)
    ax.scatter(*anchors_2d.T, marker='s', s=10, zorder=3)
    for name, xy in zip(anchors_names, anchors_2d):
        ax.annotate(name, xy, xytext=(5, 5), textcoords='offset pixels',
                    path_effects=[pe.withStroke(linewidth=2, foreground='w')],
                    fontsize=4)
    frames = pd.date_range(
        record.index[0][0],
        record.index[-1][0],
        freq=f'{target_period}S'
    )
    if conf['frames'] is not None:
        frames = frames[:conf['frames']]
    tag_plots = {}
    for tag in profile['tags']:
        tag_first_record = record.xs(tag, level='i').iloc[0]
        tag_plots[tag] = ax.scatter(
            tag_first_record['x'],
            tag_first_record['y'],
            c=tag_first_record['c'],
            alpha=.8,
            edgecolor='k',
            lw=.5,
            s=50,
            zorder=5
        )
    if conf['show_trace']:
        trace_plot = ax.scatter(
            record.iloc[0]['x'],
            record.iloc[0]['y'],
            c=record.iloc[0]['c'],
            alpha=.1,
            edgecolor='none',
            s=20,
            zorder=4
        )
    else:
        trace_plot = None
    # pos_line_plot, = ax.plot(
    #     data['x'],
    #     data['y'],
    #     c='tab:pink',
    #     alpha=.2,
    #     lw=1,
    #     zorder=4
    # )
    time_plot = ax.annotate(frames[0], (.03, .06), xycoords='axes fraction')
    fig.tight_layout()
    updater = get_plot_updater(
        tag_plots,
        record,
        time_plot,
        trace_plot
    )
    ani = ma.FuncAnimation(
        fig,
        updater,
        frames=frames,
        interval=1000//conf['fps']  # interval is in ms
    )
    if conf['video'] is None:
        plt.show()
        return
    bar = tqdm(total=len(frames))
    # metadata = dict(title='Movie Test', artist='Matplotlib',
    #                 comment='a red circle following a blue sine wave')
    video_path = conf['global']['out_dir'] / conf['video']
    ani.save(
        video_path,
        writer='ffmpeg',
        progress_callback=lambda i, n: bar.update()
    )


if __name__ == "__main__":
    main()
