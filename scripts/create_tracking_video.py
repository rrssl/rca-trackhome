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

from trkpy import postprocess


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


def get_recording_row_colors(recording, tags, colors):
    cmap = dict(zip(tags, colors))
    return recording.index.get_level_values('i').map(cmap)


def prepare_recording(
    record_path,
    profile,
    anchors,
    target_period,
    tag_colors
):
    record = postprocess.get_recording(
        record_path,
        profile,
        anchors,
        interp_period=target_period
    )
    record['c'] = get_recording_row_colors(
        record,
        profile['tags'],
        colors=tag_colors
    )
    return record


def init_figure_and_plots(
    floorplan_img,
    anchors,
    recording,
    target_period,
    profile,
    conf
):
    plt.rcParams['figure.facecolor'] = 'black'
    fig, ax = plt.subplots(figsize=(16, 9), dpi=120, frameon=False)
    plot_background(ax, floorplan_img, anchors)
    frames = create_frames(recording, profile, conf, target_period)
    tag_plots = create_tag_plots(ax, recording, profile)
    time_plot = ax.annotate(
        frames[0].strftime("%a %H:%M"),
        (.03, .06),
        xycoords='figure fraction',
        fontsize=24
    )
    if conf['show_trace']:
        trace_plot = create_trace_plot(ax, recording)
    else:
        trace_plot = None
    fig.tight_layout()
    return fig, frames, tag_plots, time_plot, trace_plot


def plot_background(ax, floorplan_img, anchors):
    ax.set_axis_off()
    ax.imshow(np.asarray(floorplan_img), zorder=2)
    ax.scatter(anchors['xi'], anchors['yi'], marker='s', s=10, zorder=3)
    for name, anchor in anchors.iterrows():
        ax.annotate(
            name,
            (anchor['xi'], anchor['yi']),
            xytext=(5, 5),
            textcoords='offset pixels',
            path_effects=[pe.withStroke(linewidth=2, foreground='w')],
            fontsize=4
        )


def create_frames(recording, profile, conf, target_period):
    frames = pd.date_range(
        recording.index[0][0],
        recording.index[-1][0],
        freq=f'{target_period}s'
    )
    frames = frames[
        frames.indexer_between_time(*profile['time_range'])
    ].copy()
    if conf['frames'] is not None:
        frames = frames[:conf['frames']]
    return frames


def create_tag_plots(ax, recording, profile):
    tag_plots = {}
    for tag in profile['tags']:
        tag_first_record = recording.xs(tag, level='i').iloc[0]
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
    return tag_plots


def create_trace_plot(ax, recording):
    trace_plot = ax.scatter(
        recording.iloc[0]['x'],
        recording.iloc[0]['y'],
        c=recording.iloc[0]['c'],
        alpha=.1,
        edgecolor='none',
        s=20,
        zorder=4
    )
    return trace_plot


def get_plot_updater(tag_plots, recording, time_plot, trace_plot):
    def update(frame):
        time_plot.set_text(frame.strftime("%a %H:%M"))
        for tag, tag_plot in tag_plots.items():
            try:
                row = recording.loc[(frame, tag)]
            except KeyError:
                tag_plot.set_alpha(.2)
                continue
            tag_plot.set_offsets(row[['x', 'y']])
            tag_plot.set_alpha(.8)
        if trace_plot is not None:
            trace = recording.loc[:frame]
            trace_plot.set_offsets(trace[['x', 'y']])
            trace_plot.set_facecolor(trace['c'])
    return update


def render_anim_to_file(ani, conf):
    bar = tqdm(total=ani._save_count)
    # metadata = dict(title='Movie Test', artist='Matplotlib',
    #                 comment='Some comment')
    video_path = conf['global']['out_dir'] / conf['video']
    ani.save(
        video_path,
        writer='ffmpeg',
        progress_callback=lambda i, n: bar.update()
    )


def main():
    conf = get_config()
    data_dir = conf['global']['data_dir']
    profile_path = data_dir / conf['profile']
    with open(profile_path, 'r') as handle:
        profile = json.load(handle)
    floorplan_path = data_dir / profile['files']['floorplan']
    record_path = data_dir / profile['files']['recording']
    # Load the data (floorplan, anchors, recording).
    floorplan_img = Image.open(floorplan_path)
    anchors = postprocess.get_anchors(profile)
    target_period = conf['speed'] // conf['fps']
    assert target_period >= 1, "Speed must be higher than the FPS"
    colors = ['tab:pink', 'tab:olive', 'tab:cyan']
    record = prepare_recording(
        record_path,
        profile,
        anchors,
        target_period,
        colors
    )
    # Render.
    fig, frames, tag_plots, time_plot, trace_plot = init_figure_and_plots(
        floorplan_img,
        anchors,
        record,
        target_period,
        profile,
        conf
    )
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
    else:
        render_anim_to_file(ani, conf)


if __name__ == "__main__":
    main()
