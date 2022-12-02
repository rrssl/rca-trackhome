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
    # 'points': {
    #     'A': (1635, 1730),
    #     'B': (1190, 6580-2100),
    #     'C': (3020, 7130-600)
    # },
    # 'display': {
    #     'x': 2300,
    #     'y': 2550,
    #     'scale': 9500,
    #     'rotation': 0
    # }
    'points': {
        'A': (1290, 7130-810),
        'B': (1670, 4817-1393+385),
        'C': (2780-346, 4817-1393-340),
        'D': (994, 486),
        'E': (4745-480, 7130-2208+1365),
        'F': (2780+130, 4817-1393),
    },
    # 'display': {
    #     'x': 2300,
    #     'y': 2550,
    #     'scale': 9500,
    #     'rotation': 0
    # }
    'display': {
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
data = data[(data.index.month == 11) & (data.index.day == 30)]
# data = data.between_time('18:00', '22:00')
# data_A = data.between_time('19:50', '20:20')
# data_B = data.between_time('18:50', '19:20')
# data_C = data.between_time('20:50', '21:20')
data_A = data.between_time('09:05', '10:55')
data_B = data.between_time('11:05', '12:55')
data_C = data.between_time('13:05', '14:55')
data_D = data.between_time('15:05', '16:55')
data_E = data.between_time('17:05', '20:25')
data_F = data.between_time('21:15', '22:35')

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

for point in "ABCDEF":
    ax.scatter(*conf['points'][point], facecolor='black', edgecolor='white', s=50, zorder=6)
    ax.annotate(point, conf['points'][point], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')], zorder=6)
for data_i in (data_A, data_B, data_C, data_D, data_E, data_F):
    ax.scatter(data_i['x'], data_i['y'], alpha=.3, edgecolor='none', s=25, zorder=5)

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
density_A, extent_A = compute_kde(data_A, res, margin)
density_B, extent_B = compute_kde(data_B, res, margin)
density_C, extent_C = compute_kde(data_C, res, margin)
density_D, extent_D = compute_kde(data_D, res, margin)
density_E, extent_E = compute_kde(data_E, res, margin)
density_F, extent_F = compute_kde(data_F, res, margin)


# +
fig, ax = plt.subplots(figsize=(16, 16))
ax.set_axis_off()
ax.set_aspect('equal')

ax.scatter(*zip(*[xyz[:2] for xyz in anchors.values()]), marker='s', zorder=3)
for name, xyz in anchors.items():
    ax.annotate(name, xyz[:2], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])
for point in "ABCDEF":
    ax.scatter(*conf['points'][point], facecolor='black', edgecolor='white', s=50, zorder=6)
    ax.annotate(point, conf['points'][point], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])

ax.imshow(density_A, cmap=plt.cm.gist_earth_r, extent=extent_A, alpha=0.5)
ax.imshow(density_B, cmap=plt.cm.gist_earth_r, extent=extent_B, alpha=0.5)
ax.imshow(density_C, cmap=plt.cm.gist_earth_r, extent=extent_C, alpha=0.5)
ax.imshow(density_D, cmap=plt.cm.gist_earth_r, extent=extent_D, alpha=0.5)
ax.imshow(density_E, cmap=plt.cm.gist_earth_r, extent=extent_E, alpha=0.5)
ax.imshow(density_F, cmap=plt.cm.gist_earth_r, extent=extent_F, alpha=0.5)
ax.imshow(np.asarray(floorplan_img), extent=extent.ravel(), zorder=2)
# ax.plot(values[0], values[1], 'k.', markersize=2)
# ax.set_xlim([xmin, xmax])
# ax.set_ylim([ymin-1000, ymax])
# -

agg_data = {
    'Accuracy (mm)': [
        np.linalg.norm(data_A[['x', 'y']].mean() - conf['points']['A']),
        np.linalg.norm(data_B[['x', 'y']].mean() - conf['points']['B']),
        np.linalg.norm(data_C[['x', 'y']].mean() - conf['points']['C']),
        np.linalg.norm(data_D[['x', 'y']].mean() - conf['points']['D']),
        np.linalg.norm(data_E[['x', 'y']].mean() - conf['points']['E']),
        np.linalg.norm(data_F[['x', 'y']].mean() - conf['points']['F']),
    ],
    'Std X (mm)': [
        data_A['x'].std(),
        data_B['x'].std(),
        data_C['x'].std(),
        data_D['x'].std(),
        data_E['x'].std(),
        data_F['x'].std(),
    ],
    'Std Y (mm)': [
        data_A['y'].std(),
        data_B['y'].std(),
        data_C['y'].std(),
        data_D['y'].std(),
        data_E['y'].std(),
        data_F['y'].std(),
    ],
}
agg_data = pd.DataFrame(agg_data, index=list("ABCDEF"))
agg_data.loc["Mean"] = agg_data.mean()
agg_data.astype(int)