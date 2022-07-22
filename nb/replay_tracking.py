# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.0
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# NB: This notebook requires `ipympl` to interactively update the plot. See installation instructions here: https://github.com/matplotlib/ipympl

# + tags=[]
import datetime
import json
from pathlib import Path

import ipywidgets as widgets
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.interpolate as interp
import yaml
from PIL import Image

# %matplotlib widget

# + [markdown] tags=[]
# ## Define and load config

# +
ACONF = {
    'path': "../config/local.yml",
    'profile': "ldml.json",
    'recording': "location.csv",
    'device': "rpi1",
    'figsize': (6, 6),
    'replay_timestep': .1,
    'track_id': "0x7625",
}

with open(ACONF['path'], 'r') as handle:
    conf = yaml.safe_load(handle)
conf |= ACONF

data_dir = Path(conf['global']['data_dir'])
profile_path = data_dir / conf['profile']
with open(profile_path, 'r') as handle:
    profile = json.load(handle)
display(profile)
out_dir = Path(conf['global']['out_dir'])
recording_path = out_dir / conf['recording']
# -

# ## Load data

data = pd.read_csv(recording_path)
data = data[(data['device'] == conf['device']) & (data['i'] == conf['track_id'])]
timestamps = pd.to_datetime(data['t'], unit='ms', utc=True).dt.tz_convert("Europe/London")
data = data.set_index(timestamps)
data = data.between_time('15:00', '17:00')

# +
# anchors = profile['anchors']

# floorplan_img = Image.open(profile['floorplan_path'])
# display_params = profile['display_params']
# if display_params['rotation']:
#     floorplan_img = floorplan_img.rotate(display_params['rotation'], expand=True)
# aspect = floorplan_img.width / floorplan_img.height
# scale = display_params['scale']
# shift = np.array([display_params['x'], display_params['y']]).reshape(2, 1)
# extent = np.array([[-aspect, aspect], [-1, 1]]) / 2 * scale + shift
# -

# ## View the recording

# +
# def id2time(i):
#     return (
#         f"{str(datetime.timedelta(seconds=times[i]))[:-5]} / "
#         f"{str(datetime.timedelta(seconds=times[-1]))[:-5]}"
#     )

slider = widgets.IntSlider(
    value=0,
    min=0,
    max=len(data.index)-1,
    step=1,
    description="Time",
    readout=False
)

slider_text = widgets.Label(value=data.index[0].strftime('%H:%M:%S'))

def handle_slider_change(change):
    pos_plot.set_offsets(data[['x', 'y']].iloc[change.new])
    pos_line_plot.set_data(data['x'].iloc[:change.new+1], data['y'].iloc[:change.new+1])
    fig.canvas.draw()
    slider_text.value = data.index[change.new].strftime('%H:%M:%S')

slider.observe(handle_slider_change, names='value')

play = widgets.Play(
    value=0,
    min=0,
    max=len(data.index)-1,
    step=1,
    interval=50,  # 50ms between frames
    description="Press play",
    disabled=False
)
widgets.jslink((play, 'value'), (slider, 'value'))

controls = widgets.HBox([play, slider, slider_text])

# +
fig, ax = plt.subplots(figsize=conf['figsize'])
ax.set_axis_off()

# ax.imshow(np.asarray(floorplan_img), extent=extent.ravel(), zorder=2)
anchors = profile['anchors']
ax.scatter(*zip(*[xyz[:2] for xyz in anchors.values()]), marker='s', zorder=3)
for name, xyz in anchors.items():
    ax.annotate(name, xyz[:2], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])
ax.set_aspect('equal')
bg_plot = ax.scatter(data['x'], data['y'], c='tab:olive', alpha=.2, edgecolor='none', s=25, zorder=5)
pos_plot = ax.scatter(data['x'].iloc[0], data['y'].iloc[0], c='tab:red', s=50, zorder=5)
pos_line_plot, = ax.plot(data['x'], data['y'], c='tab:olive', alpha=.2, lw=1, zorder=4)

fig.tight_layout()

display(controls)
