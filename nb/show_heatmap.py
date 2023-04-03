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

# +
import json
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from matplotlib.colors import LogNorm, PowerNorm
from matplotlib.patches import Rectangle
from PIL import Image
from scipy import spatial, stats

# +
ACONF = {
    'config': "../config/local.yml",
    'profile': "sportsman/tracking/both/test-3/profile_full.json"
}
with open(ACONF['config'], 'r') as handle:
    conf = yaml.safe_load(handle)
conf |= ACONF
data_dir = Path(conf['global']['data_dir'])
profile_path = data_dir / conf['profile']
with open(profile_path, 'r') as handle:
    profile = json.load(handle)
floorplan_path = data_dir / profile['files']['floorplan']
record_path = data_dir / profile['files']['recording']
# Load the floorplan.
floorplan_img = Image.open(floorplan_path)

bounds = {
    'lower': (270, 800, 95, 890),
    'upper': (1130, 1650, 95, 890)
}


# +
def get_anchors(profile) -> pd.DataFrame:
    anchors = pd.DataFrame.from_dict(
        data=profile['anchors'],
        orient='index',
        dtype=float,
        columns=['x', 'y', 'z']
    )
    anchors['floor'] = ""
    for floor, floor_anchors in profile['floors'].items():
        for fa in floor_anchors:
            anchors.loc[fa, 'floor'] = floor
    anchors[['tx', 'ty', 's']] = anchors.apply(
        lambda row: profile['transforms'][row['floor']],
        axis=1,
        result_type='expand'
    )
    anchors['i'] = anchors['y'].max() - anchors['y']  # swap y axis
    anchors['i'] = anchors['i']*anchors['s'] + anchors['ty']
    anchors['j'] = anchors['x']*anchors['s'] + anchors['tx']
    return anchors

anchors = get_anchors(profile)


# +
def get_recording(record_path, profile, anchors):
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
    for tag, tag_record in record.groupby('i'):  # tag-specific cleaning
        # Remove consecutive duplicates.
        tag_record = tag_record.sort_index()
        tag_record = tag_record.drop(tag_record[
            (tag_record['x'].shift(1) == tag_record['x'])
            & (tag_record['y'].shift(1) == tag_record['y'])
        ].index)
        # Downsample to remove some of the noise.
        tag_record = tag_record[['x', 'y', 'z']].resample('60S').mean().dropna()
        # Save result.
        tag_record['i'] = tag
        tags_record.append(tag_record)
    record = pd.concat(
        tags_record
    ).set_index('i', append=True).sort_index()
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
    record['y'] = anchors['y'].max() - record['y']  # swap y axis
    record[['x', 'y']] = record[['x', 'y']].multiply(data_xforms[:, 2:])
    record[['x', 'y']] = record[['x', 'y']].add(data_xforms[:, :2])

    return record

record = get_recording(record_path, profile, anchors)
display(record)


# +
def plot_background(ax):
    ax.set_axis_off()
    img_plot = ax.imshow(np.asarray(floorplan_img), zorder=2)
    ax.scatter(anchors['j'], anchors['i'], marker='s', s=10, zorder=3)
    for name, row in anchors.iterrows():
        ax.annotate(
            name,
            (row['j'], row['i']),
            xytext=(5, 5),
            textcoords='offset pixels',
            path_effects=[pe.withStroke(linewidth=2, foreground='w')],
            fontsize=4
        )
    return img_plot

def plot_bounds(ax, bounds):
    ax.add_patch(
        Rectangle(
            (bounds[0], bounds[2]),
            bounds[1]-bounds[0],
            bounds[3]-bounds[2],
            linewidth=1,
            linestyle='--',
            edgecolor='r',
            facecolor='none',
            zorder=3
        )
    )


# -

# Define the points' colors.
cmap = dict(zip(profile['tags'], ['tab:pink', 'tab:olive']))
record['c'] = record.index.get_level_values('i').map(cmap)
# Create the plot.
fig, ax = plt.subplots(figsize=(16, 9), dpi=120)
plot_background(ax)
plot_bounds(ax, bounds['lower'])
plot_bounds(ax, bounds['upper'])
ax.scatter(
    record['x'],
    record['y'],
    c=record['c'],
    alpha=.1,
    edgecolor='none',
    s=20,
    zorder=4
);

# ## Histogram-style heatmap

# +
bin_size = 32

fig, ax = plt.subplots(figsize=(16, 9), dpi=120)
plot_background(ax)

for tag, tag_cmap in zip(profile['tags'], ('RdPu', 'Greens')):
    for floor, floor_bounds in bounds.items():
        xmin, xmax, ymin, ymax = floor_bounds
        bins_x = np.arange(xmin, xmax, bin_size)
        bins_y = np.arange(ymin, ymax, bin_size)

        heatmap, edges_x, edges_y = np.histogram2d(
            record.xs(tag, level='i')['x'],
            record.xs(tag, level='i')['y'],
            bins=(bins_x, bins_y)
        )
        ax.pcolormesh(
            edges_x,
            edges_y,
            heatmap.T,
            cmap=tag_cmap,
            norm=LogNorm(vmin=2, vmax=20),
            zorder=4,
            alpha=.75
        )


# -

# ## KDE-style heatmap (can't compare between tags!!!)

# +
def compute_kde(kernel, bounds, step, log=False):
    xmin, xmax, ymin, ymax = bounds
    X, Y = np.mgrid[xmin:xmax:step, ymin:ymax:step]
    positions = np.vstack([X.ravel(), Y.ravel()])
    evaluate = kernel.logpdf if log else kernel.pdf
    Z = np.reshape(evaluate(positions), X.shape)
    return np.rot90(Z)

pix_size = 8

for tag, tag_cmap in zip(profile['tags'], ('RdPu', 'Greens')):
    fig, ax = plt.subplots(figsize=(16, 9), dpi=120)
    kernel = stats.gaussian_kde(
        record.xs(tag, level='i')[['x', 'y']].to_numpy().T,  # expects dims x points
        bw_method='scott'
    )
    display(kernel.factor)
    densities = {}
    for floor, floor_bounds in bounds.items():
        densities[floor] = compute_kde(
            kernel,
            floor_bounds,
            pix_size,
            log=False
        )
    vmin = min(d.min() for d in densities.values())
    vmax = max(d.max() for d in densities.values())
    for floor, floor_bounds in bounds.items():
        ax.imshow(
            densities[floor],
            cmap=tag_cmap,
            alpha=.5,
            extent=floor_bounds,
            norm=PowerNorm(gamma=.3, vmin=vmin, vmax=vmax),
            # norm=LogNorm(vmin=vmin, vmax=vmax),
            zorder=4
        )
    plot_background(ax);


# -

# ## Distance function

# +
def compute_distances(tree, bounds, step):
    xmin, xmax, ymin, ymax = bounds
    X, Y = np.mgrid[xmin:xmax:step, ymin:ymax:step]
    positions = np.column_stack([X.ravel(), Y.ravel()])  # shape: points x dims
    Z = np.reshape(tree.query(positions)[0], X.shape)
    return np.rot90(Z)

pix_size = 8

for tag, tag_cmap in zip(profile['tags'], ('RdPu', 'Greens')):
    fig, ax = plt.subplots(figsize=(16, 9), dpi=120)
    tree = spatial.KDTree(record.xs(tag, level='i')[['x', 'y']].to_numpy())
    for floor, floor_bounds in bounds.items():
        distances = compute_distances(
            tree,
            floor_bounds,
            pix_size
        )
        ax.imshow(
            distances,
            cmap=tag_cmap+'_r',
            alpha=.5,
            extent=floor_bounds,
            # norm=PowerNorm(gamma=.7),
            zorder=4
        )
    plot_background(ax);
