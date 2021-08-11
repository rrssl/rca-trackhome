# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.11.4
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# NB: This notebook requires `ipympl` to interactively update the plot. See installation instructions here: https://github.com/matplotlib/ipympl

# + tags=[]
import datetime
import json
import os
from configparser import ConfigParser

import ipywidgets as widgets
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import scipy.interpolate as interp
from PIL import Image

# %matplotlib widget

# + [markdown] tags=[]
# ## Define and load config

# +
CONFIG_PATH = "../config/local.ini"
PROFILE_NAME = "granite_floorplan_20210810163830"
RECORDING_NAME = "recording_20210811155803-granite_floorplan_20210810163830"

FIGSIZE = (6, 6)
REPLAY_TIMESTEP = .1

# +
config = ConfigParser()
config.read(CONFIG_PATH)

data_path = config['global']['data_path']
profile_path = os.path.join(data_path, f"{PROFILE_NAME}.json")
with open(profile_path) as handle:
    profile = json.load(handle)
display(profile)
# -

# ## Load data

# +
recording_path = os.path.join(data_path, f"{RECORDING_NAME}.npy")
pos_data = np.load(recording_path)
# Resample the data to match the replay timestep. Using 'previous' means that
# we use the last known value at any given time.
resample_x = interp.interp1d(
    pos_data[:, 0], pos_data[:, 1], kind='previous', assume_sorted=True
)
resample_y = interp.interp1d(
    pos_data[:, 0], pos_data[:, 2], kind='previous', assume_sorted=True
)
times = np.arange(pos_data[0, 0], pos_data[-1, 0], REPLAY_TIMESTEP)
pos_data_resampled = np.column_stack((resample_x(times), resample_y(times)))

anchors = profile['anchors']

floorplan_img = Image.open(profile['floorplan_path'])
display_params = profile['display_params']
if display_params['rotation']:
    floorplan_img = floorplan_img.rotate(display_params['rotation'], expand=True)
aspect = floorplan_img.width / floorplan_img.height
scale = display_params['scale']
shift = np.array([display_params['x'], display_params['y']]).reshape(2, 1)
extent = np.array([[-aspect, aspect], [-1, 1]]) / 2 * scale + shift


# -

# ## View the recording

# +
def id2time(i):
    return (
        f"{str(datetime.timedelta(seconds=times[i]))[:-5]} / "
        f"{str(datetime.timedelta(seconds=times[-1]))[:-5]}"
    )

slider = widgets.IntSlider(
    value=0,
    min=0,
    max=len(pos_data_resampled)-1,
    step=1,
    description="Time",
    readout=False
)

slider_text = widgets.Label(value=id2time(0))

def handle_slider_change(change):
    pos_plot.set_offsets(pos_data_resampled[change.new])
    pos_line_plot.set_data(pos_data_resampled[:change.new+1].T)
    fig.canvas.draw()
    slider_text.value = id2time(change.new)

slider.observe(handle_slider_change, names='value')

play = widgets.Play(
    value=0,
    min=0,
    max=len(pos_data_resampled)-1,
    step=1,
    interval=REPLAY_TIMESTEP*1000,
    description="Press play",
    disabled=False
)
widgets.jslink((play, 'value'), (slider, 'value'))

controls = widgets.HBox([play, slider, slider_text])

# +
fig, ax = plt.subplots(figsize=FIGSIZE)
ax.set_axis_off()

ax.imshow(np.asarray(floorplan_img), extent=extent.ravel(), zorder=2)
ax.scatter(*zip(*[xyz[:2] for xyz in anchors.values()]), marker='s', zorder=3)
for name, xyz in anchors.items():
    ax.annotate(f"0x{int(name):04x}", xyz[:2], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])
pos_plot = ax.scatter(*pos_data_resampled[0], c='tab:red', s=50, zorder=5)
pos_line_plot, = ax.plot(*pos_data_resampled[0], c='tab:orange', zorder=4)

fig.tight_layout()

display(controls)
