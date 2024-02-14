import json
from argparse import ArgumentParser
from pathlib import Path

import matplotlib.animation as ma
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
# import pandasgui
import yaml
from matplotlib.widgets import Slider
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
        default=300,
        type=int,
        help="Seconds of recording per second of video (default: 300)"
    )
    parser.add_argument(
        '--fps',
        required=True,
        type=int,
        help="Video frames per second (default: 15)"
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
    parser.add_argument(
        '--set_transform',
        action='store_true',
        help="Show the controls to configure the anchor/recording tranform"
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


def load_and_format_recording(profile, anchors):
    recording = postprocess.get_recording(
        profile['recording_path'],
        profile,
        anchors,
        interp_period=profile['interval']
    )
    recording['c'] = recording.index.get_level_values('i').map(
        profile['tag_colors']
    )
    return recording


def get_animation_frame_indices(recording, profile):
    frame_indices = pd.date_range(
        recording.index[0][0],
        recording.index[-1][0],
        freq=f"{profile['interval']}s"
    )
    frame_indices = frame_indices[
        frame_indices.indexer_between_time(*profile['time_range'])
    ].copy()
    if profile['num_frames'] is not None:
        frame_indices = frame_indices[:profile['num_frames']]
    return frame_indices


def init_figure_and_plots(floorplan_img, anchors, profile):
    plt.rcParams['figure.facecolor'] = 'black'
    fig, ax = plt.subplots(figsize=(16, 9), dpi=120, frameon=False)
    plots = {}
    plots['anchors'] = plot_background(ax, floorplan_img, anchors)
    plots['tags'] = create_tag_plots(ax, profile)
    plots['clock'] = ax.annotate(
        "",
        (.03, .06),
        xycoords='figure fraction',
        fontsize=24
    )
    if profile['show_trace']:
        plots['tags_trace'] = create_trace_plot(ax)
    fig.tight_layout()
    return fig, plots


def plot_background(ax, floorplan_img, anchors):
    ax.set_axis_off()
    ax.imshow(np.asarray(floorplan_img), zorder=2)
    anchor_plot = ax.scatter(
        anchors['xi'],
        anchors['yi'],
        marker='s',
        s=10,
        zorder=3
    )
    return anchor_plot


def create_tag_plots(ax, profile):
    tag_plots = {}
    for tag in profile['tags']:
        tag_plots[tag] = ax.scatter(
            0,
            0,
            c=profile['tag_colors'][tag],
            alpha=.8,
            edgecolor='k',
            lw=.5,
            s=50,
            zorder=5
        )
    return tag_plots


def create_trace_plot(ax):
    trace_plot = ax.scatter(
        0,
        0,
        c='none',
        alpha=.1,
        edgecolor='none',
        s=20,
        zorder=4
    )
    return trace_plot


def get_plot_updater(recording, plots):
    def update(frame):
        for tag, tag_plot in plots['tags'].items():
            try:
                row = recording.loc[(frame, tag)]
            except KeyError:
                tag_plot.set_alpha(.2)
                continue
            tag_plot.set_offsets(row[['x', 'y']])
            tag_plot.set_alpha(.8)
        plots['clock'].set_text(frame.strftime("%a %H:%M"))
        if 'tags_trace' in plots:
            trace = recording.loc[:frame]
            plots['tags_trace'].set_offsets(trace[['x', 'y']])
            plots['tags_trace'].set_facecolor(trace['c'])
    return update


def get_control_blueprints(profile):
    blueprints = {}
    param_defaults = {
        'x': {'valmin': 0, 'valmax': 200, 'valstep': 1},
        'y': {'valmin': 0, 'valmax': 600, 'valstep': 1},
        's': {'valmin': 0.1, 'valmax': 0.5, 'valstep': 0.001},
    }
    for floor_name, floor_xform in profile['transforms'].items():
        for value, (param, kwargs) in zip(floor_xform, param_defaults.items()):
            label = "/".join((floor_name, param))
            blueprints[label] = kwargs | {'valinit': value}
    return blueprints


def create_controls(profile, anchors_plot):
    blueprints = get_control_blueprints(profile)
    fig = anchors_plot.figure
    fig_width = 16
    fig_height = 18
    controls = {}
    for i, (label, kwargs) in enumerate(blueprints.items()):
        ax = fig.add_subplot(
            fig_height,
            fig_width,
            ((i+1)*fig_width-4, (i+1)*fig_width-1)
        )
        controls[label] = Slider(ax=ax, label=label, **kwargs)
        controls[label].on_changed(
            get_anchor_updater(profile, label, anchors_plot)
        )
    return controls


def get_anchor_updater(profile, label, anchors_plot):
    def update_anchors(value):
        floor_name, parameter = label.split("/")
        param_index = ('x', 'y', 's').index(parameter)
        profile['transforms'][floor_name][param_index] = value
        anchors = postprocess.get_anchors(profile)
        anchors_plot.set_offsets(anchors[['xi', 'yi']])
    return update_anchors


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
    profile['floorplan_path'] = data_dir / profile['files']['floorplan']
    # Create the animation settings.
    profile['recording_path'] = data_dir / profile['files']['recording']
    profile['num_frames'] = conf['frames']
    profile['show_trace'] = conf['show_trace']
    profile['interval'] = conf['speed'] // conf['fps']
    assert profile['interval'] >= 1, "Speed must be higher than the FPS"
    base_tag_colors = ['tab:pink', 'tab:olive', 'tab:cyan']
    profile['tag_colors'] = dict(zip(profile['tags'], base_tag_colors))
    # Load the data (floorplan, anchors, recording).
    floorplan_img = Image.open(profile['floorplan_path'])
    anchors = postprocess.get_anchors(profile)
    record = load_and_format_recording(profile, anchors)
    frame_indices = get_animation_frame_indices(record, profile)
    # Render.
    fig, plots = init_figure_and_plots(floorplan_img, anchors, profile)
    updater = get_plot_updater(record, plots)
    updater(frame_indices[0])
    # Show the transform controls or animation depending on the options.
    if conf['set_transform']:
        _ = create_controls(profile, plots['anchors'])
        plt.show()
    else:
        ani = ma.FuncAnimation(
            fig,
            updater,
            frames=frame_indices,
            interval=1000//conf['fps']  # interval is in ms
        )
        if conf['video'] is None:
            plt.show()
        else:
            render_anim_to_file(ani, conf)


if __name__ == "__main__":
    main()
