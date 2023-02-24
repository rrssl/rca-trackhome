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
from scipy import stats

# %matplotlib widget

# + [markdown] tags=[]
# ## Define and load config

# +
ACONF = {
    'path': "../config/local.yml",
    'figsize': (6, 6),
    'replay_timestep': .1,
} | [
    {
        'place': "sportsman",
        'profile': "tracking/both/lower.json",
        'experiment': "tracking/both/test1",
        'floorplan': "floorplan/lower/furniture.png",
        'device': "rpi1",
        'tag_id': "0x7625",
        # floorplan display params: (2380, 3550, 7411)
    },
    {
        'place': "sportsman",
        'profile': "tracking/both/upper.json",
        'experiment': "tracking/both/test1",
        'floorplan': "floorplan/upper/furniture.png",
        'device': "rpi2",
        'tag_id': "0x6812",
        # floorplan display params: (2260, 2500, 9441)
    },
][1]

with open(ACONF['path'], 'r') as handle:
    conf = yaml.safe_load(handle)
conf |= ACONF

data_dir = Path(conf['global']['data_dir']) / conf['place']
profile_path = data_dir / conf['profile']
with open(profile_path, 'r') as handle:
    profile = json.load(handle)
display(profile)
anchors = profile['anchors']
recording_path = data_dir / conf['experiment'] / "location.csv"
errors_path = data_dir / conf['experiment'] / "error.csv"
floorplan_path = data_dir / conf['floorplan']
# -

# ## Load data

data = pd.read_csv(recording_path)
data = data[(data['msg_sender'] == conf['device']) & (data['i'] == conf['tag_id'])]
timestamps = pd.to_datetime(data['t'], unit='ms', utc=True).dt.tz_convert("Europe/London")
data = data.set_index(timestamps)
data = data.sort_index()
data = data.drop(data[(data['x'] == 0) & (data['y'] == 0)].index)
data = data.loc[~((data['x'].shift(-1) == data['x']) & (data['y'].shift(-1) == data['y']))]
# data = data[(data.index.month == 8) & (data.index.day == 15)]
# data = data.between_time('10:00', '11:00')
data

# +
# data[data.index.to_series().diff().dt.seconds > 2.0]
# -

# ## Align the floorplan

# +
floorplan_img = Image.open(floorplan_path)
# floorplan_img = floorplan_img.rotate(conf['display']['rotation'], expand=True)

fig, ax = plt.subplots(figsize=conf['figsize'])
ax.set_axis_off()
floorplan_display = ax.imshow(
    np.asarray(floorplan_img),
    # extent=extent.ravel(),
    zorder=2
)
ax.scatter(*zip(*[xyz[:2] for xyz in anchors.values()]), marker='s', zorder=3)
for name, xyz in anchors.items():
    ax.annotate(name, xyz[:2], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])
ax.set_aspect('equal')
fig.tight_layout()

@widgets.interact(x=(0, 5000, 10), y=(0, 5000, 10), s=(1, 10000, 10))
def update_floorplan(x, y, s):
    aspect = floorplan_img.width / floorplan_img.height
    shift = np.array([[x], [y]])
    extent = np.array([[-aspect, aspect], [-1, 1]]) / 2 * s + shift
    floorplan_display.set_extent(extent.ravel())
    fig.canvas.draw()


# -

# ## View the recording

# + tags=[] jupyter={"source_hidden": true}
slider = widgets.IntSlider(
    value=0,
    min=0,
    max=len(data.index)-1,
    step=1,
    description="Time",
    readout=False
)

slider_text = widgets.Label(value=data.index[0].strftime('%H:%M:%S'))

def get_slider_change_callback(fig):

    def cb(change):
        pos_plot.set_offsets(data[['x', 'y']].iloc[change.new])
        pos_line_plot.set_data(data['x'].iloc[:change.new+1], data['y'].iloc[:change.new+1])
        fig.canvas.draw()
        slider_text.value = data.index[change.new].strftime('%H:%M:%S')

    return cb

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

# + jupyter={"source_hidden": true} tags=[]
fig, ax = plt.subplots(figsize=conf['figsize'])
ax.set_axis_off()

slider.observe(get_slider_change_callback(fig), names='value')

ax.imshow(np.asarray(floorplan_img), extent=floorplan_display.get_extent(), zorder=2)
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

# +
valid_data = data[(data['x'] != 0) & (data['y'] != 0)]


xmin = valid_data['x'].min()
xmax = valid_data['x'].max()
ymin = valid_data['y'].min()
ymax = valid_data['y'].max()

X, Y = np.mgrid[xmin:xmax:100j, ymin:ymax:100j]
positions = np.vstack([X.ravel(), Y.ravel()])
values = np.vstack([valid_data['x'], valid_data['y']])
kernel = stats.gaussian_kde(values)
Z = np.reshape(kernel(positions).T, X.shape)

# positions = data[['x', 'y']].values
# gaussian_kde(positions.T)
# -

fig, ax = plt.subplots()
ax.set_axis_off()
ax.imshow(np.asarray(floorplan_img), extent=extent.ravel(), zorder=2)
ax.imshow(np.rot90(Z), cmap=plt.cm.gist_earth_r,
          extent=[xmin, xmax, ymin, ymax])
# ax.plot(values[0], values[1], 'k.', markersize=2)
ax.set_xlim([xmin, xmax])
ax.set_ylim([ymin-1000, ymax])
plt.show()

errors = pd.read_csv(errors_path)
timestamps = pd.to_datetime(errors['msg_time'], unit='s', utc=True).dt.tz_convert("Europe/London")
errors = errors.set_index(timestamps)
errors = errors.sort_index()
# errors = errors[(errors.index.month == 8) & (errors.index.day == 15)]
# errors = errors.between_time('08:00', '23:00')
display(errors['message'].value_counts())

# +
fig, ax = plt.subplots(figsize=(14, 6))

errors['Anchors'] = errors['message'].str.contains("ANCHOR")
errors['Tag 0x7625'] = errors['message'].str.contains("0x7625")
errors['Master tag'] = ~(errors['Anchors'] | errors['Tag 0x7625'])
agg_errors = errors[['Anchors', 'Tag 0x7625', 'Master tag']].resample("10Min").sum()

agg_errors.plot(kind='bar', stacked=True, ax=ax)
ax.set_xticklabels(agg_errors.index.strftime('%H:%M'))  # , rotation=45, ha='right', rotation_mode='anchor')
fig.tight_layout()
