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

# + tags=[]
import datetime
import json
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy.interpolate as interp
import yaml
from PIL import Image
from scipy import stats

# + [markdown] tags=[]
# ## Define and load config

# +
ACONF = {
    'config': "../config/local.yml",
    'place': "sportsman",
    'floor': "lower",
    'device': "rpi1",
    'tag': "0x7625",
    'experiment': "accuracy-1",
    'locations': {
        # upper/accuracy-1
        # 'A': (1635, 1730),
        # 'B': (1190, 6580-2100),
        # 'C': (3020, 7130-600)
        # upper/accuracy-2
        # 'A': (4652, 661),
        # 'B': (370, 1191),
        # 'C': (3413, 3083),
        # 'D': (1132, 4739)
        # lower/accuracy-1
        'A': (1290, 7130-810),
        'B': (1670, 4817-1393+385),
        'C': (2780-346, 4817-1393-340),
        'D': (994, 486),
        'E': (4745-480, 7130-2208+1365),
        'F': (2780+130, 4817-1393)
    },
    'day': 30,
    'month': 11,
    'times': {
        # upper/accuracy-1
        # 'A': ('19:50', '20:20'),
        # 'B': ('18:50', '19:20'),
        # 'C': ('20:50', '21:20')
        # upper/accuracy-2
        # 'A': ('12:15', '14:45'),
        # 'B': ('15:10', '17:40'),
        # 'C': ('18:00', '20:30'),
        # 'D': ('09:00', '11:30')
        # 'A': ('11:45', '14:15'),
        # 'B': ('14:45', '17:15'),
        # 'C': ('17:45', '20:15')
        # 'A': ('13:45', '17:15'),
        # 'B': ('17:45', '20:15'),
        # 'D': ('09:15', '13:15')
        # lower/accuracy-1
        'A': ('09:05', '10:55'),
        'B': ('11:05', '12:55'),
        'C': ('13:05', '14:55'),
        'D': ('15:05', '16:55'),
        'E': ('17:05', '20:25'),
        'F': ('21:15', '22:35')
    },
    'display': {
        # upper/accuracy-2
        # 'x': 2300,
        # 'y': 2550,
        # 'scale': 9500,
        # 'rotation': 0
        # lower/accuracy-1
        'x': 2375,
        'y': 3550,
        'scale': 7450,
        'rotation': 0
    }
}

with open(ACONF['config'], 'r') as handle:
    conf = yaml.safe_load(handle)
conf |= ACONF

place_dir = Path(conf['global']['data_dir']) / conf['place']
profile_path = place_dir / "tracking" / conf['floor'] / "profile.json"
with open(profile_path, 'r') as handle:
    profile = json.load(handle)
display(profile)
anchors = profile['anchors']
recording_path = place_dir / "tracking" / conf['floor'] / conf['experiment'] / "location.csv"
floorplan_path = place_dir / "floorplan" / conf['floor'] / "furniture.png"
# -

# ## Load data

data = pd.read_csv(recording_path)
data = data[(data['device'] == conf['device']) & (data['i'] == conf['tag'])]
timestamps = pd.to_datetime(data['t'], unit='ms', utc=True).dt.tz_convert("Europe/London")
data = data.set_index(timestamps).sort_index()
data = data.drop(data[(data['x'] == 0) & (data['y'] == 0)].index)
data = data.loc[~((data['x'].shift(-1) == data['x']) & (data['y'].shift(-1) == data['y']))]
data = data[(data.index.month == conf['month']) & (data.index.day == conf['day'])]
points_data = {
    point: data.between_time(start, end)
    for point, (start, end) in conf['times'].items()
}

floorplan_img = Image.open(floorplan_path)
if conf['display']['rotation']:
    floorplan_img = floorplan_img.rotate(conf['display']['rotation'], expand=True)
aspect = floorplan_img.width / floorplan_img.height
scale = conf['display']['scale']
shift = np.array([conf['display']['x'], conf['display']['y']]).reshape(2, 1)
extent = np.array([[-aspect, aspect], [-1, 1]]) / 2 * scale + shift

# ## Visualize positions

# +
fig, ax = plt.subplots(figsize=(12, 12))
ax.set_axis_off()
ax.set_aspect('equal')

ax.scatter(*zip(*[xyz[:2] for xyz in anchors.values()]), marker='s', zorder=3)
for name, xyz in anchors.items():
    ax.annotate(name, xyz[:2], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])
ax.imshow(np.asarray(floorplan_img), extent=extent.ravel(), zorder=2)

for point, location in conf['locations'].items():
    ax.scatter(*location, facecolor='black', edgecolor='white', s=50, zorder=6)
    ax.annotate(point, location, xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')],
                zorder=6)
    ax.scatter(points_data[point]['x'], points_data[point]['y'], alpha=.3,
               edgecolor='none', s=25, zorder=5)

# -

# ## Visualize the heatmap

# +
def compute_kde(data, res, margin):
    xmin = data['x'].min() - margin
    xmax = data['x'].max() + margin
    ymin = data['y'].min() - margin
    ymax = data['y'].max() + margin
    aspect = (xmax - xmin) / (ymax - ymin)
    X, Y = np.mgrid[xmin:xmax:int(res*aspect)*1j, ymin:ymax:res*1j]
    positions = np.vstack([X.ravel(), Y.ravel()])
    values = np.vstack([data['x'], data['y']])
    kernel = stats.gaussian_kde(values, bw_method=3)
    Z = np.reshape(kernel.pdf(positions).T, X.shape)
    return np.rot90(Z), np.array([xmin, xmax, ymin, ymax])

res = 100
margin = 500
density_extent_kde = {
    point: compute_kde(point_data, res, margin)
    for point, point_data in points_data.items()
}


# +
fig, ax = plt.subplots(figsize=(16, 16))
ax.set_axis_off()
ax.set_aspect('equal')

ax.scatter(*zip(*[xyz[:2] for xyz in anchors.values()]), marker='s', zorder=3)
for name, xyz in anchors.items():
    ax.annotate(name, xyz[:2], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])
for point, location in conf['locations'].items():
    ax.scatter(*location, facecolor='black', edgecolor='white', s=50, zorder=6)
    ax.annotate(point, location, xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])
for point, (point_density, point_extent) in density_extent_kde.items():
    ax.imshow(point_density, cmap=plt.cm.gist_earth_r, extent=point_extent,
              alpha=.5)
ax.imshow(np.asarray(floorplan_img), extent=extent.ravel(), zorder=2)
# ax.plot(values[0], values[1], 'k.', markersize=2)
# ax.set_xlim([xmin, xmax])
# ax.set_ylim([ymin-1000, ymax])
# -

agg_data = {
    'Accuracy (mm)': [
        np.linalg.norm(point_data[['x', 'y']].mean() - conf['locations'][point])
        for point, point_data in points_data.items()
    ],
    'Std X (mm)': [
        point_data['x'].std()
        for _, point_data in points_data.items()
    ],
    'Std Y (mm)': [
        point_data['y'].std()
        for _, point_data in points_data.items()
    ],
}
agg_data = pd.DataFrame(agg_data, index=list(points_data.keys()))
agg_data.loc["Mean"] = agg_data.mean()
agg_data.astype(int)
