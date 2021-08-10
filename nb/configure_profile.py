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

# +
import json
import os
from configparser import ConfigParser
from datetime import datetime

import ipywidgets as widgets
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

# %matplotlib widget

# +
ANCHORS = {
    0x681D: ( 520,    0, 1125),
    0x685C: (3270,  400, 2150),
    0x0D31: (4555, 2580, 1630),
    0x0D2D: ( 400, 3180, 1895)
}
REMOTE_ID = [None, 0x7625][0]  # network ID of the tag. Use None for the master.

CONFIG_PATH = "../config/local.ini"
FLOORPLAN_NAME = "granite_floorplan.jpg"
FIGSIZE = (6, 6)

# +
config = ConfigParser()
config.read(CONFIG_PATH)

anchors_array = np.array([p[:2] for p in ANCHORS.values()])
default_shift = anchors_array.mean(axis=0).reshape((2, 1))
default_scale = np.ptp(anchors_array, axis=0).max() * 2

floorplan_path = os.path.join(config['global']['data_path'], FLOORPLAN_NAME)
base_img = Image.open(floorplan_path)
aspect = base_img.width / base_img.height
extent = np.array([[-aspect, aspect], [-1, 1]]) / 2 * default_scale + default_shift

display_params = {
    'x': default_shift[0, 0],
    'y': default_shift[1, 0],
    'scale': default_scale,
    'rotation': 0,
}

def save_profile(button):
    profile_data = {
        'anchors': ANCHORS,
        'remote_id': REMOTE_ID,
        'floorplan_path': os.path.abspath(floorplan_path),
        'display_params': display_params
    }
    dirname, filename = os.path.split(profile_data['floorplan_path'])
    filename, _ = os.path.splitext(filename)
    filename += datetime.now().strftime('_%Y%m%d%H%M%S') + ".json"
    profile_path = os.path.join(dirname, filename)
    with open(profile_path, 'w') as handle:
        json.dump(profile_data, handle, indent=2)
    print(f"Profile saved at {profile_path}")

button = widgets.Button(
    description="Save user profile",
    disabled=False,
    button_style='', # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Save the configuration on disk",
    icon='save' # (FontAwesome names without the `fa-` prefix)
)
button.on_click(save_profile)


# +
fig, ax = plt.subplots(figsize=FIGSIZE)
ax.set_xlim(default_shift[0]-default_scale, default_shift[0]+default_scale)
ax.set_ylim(default_shift[1]-default_scale, default_shift[1]+default_scale)

ax.set_aspect('equal')
ax.set_facecolor('#eee')
for s in ax.spines.values(): s.set_visible(False)
ax.grid(color='#fff')
ax.set_xticklabels([])
ax.set_yticklabels([])
ax.tick_params(tick1On=False)

ax.scatter(*zip(*[xyz[:2] for xyz in ANCHORS.values()]), marker='s', zorder=3)
for name, xyz in ANCHORS.items():
    ax.annotate(f"0x{name:04x}", xyz[:2], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])
# ax.scatter(0, 0, c='tab:orange', s=100)

img_plot = ax.imshow(np.asarray(base_img), extent=extent.ravel(), zorder=2)

fig.tight_layout()

display(button)

@widgets.interact(
    x=(default_shift[0, 0]-default_scale/2, default_shift[0, 0]+default_scale/2),
    y=(default_shift[1, 0]-default_scale/2, default_shift[1, 0]+default_scale/2),
    scale=(default_scale/2, default_scale*2),
    rotation=(0, 270, 90)
)
def update_image(
    x=default_shift[0],
    y=default_shift[1],
    scale=default_scale,
    rotation=0
):
    img = base_img.rotate(rotation, expand=True) if rotation else base_img
    img_plot.set_data(np.asarray(img))

    aspect = img.width / img.height  # rotation changes the aspect
    shift = np.array([x, y]).reshape(2, 1)
    extent = np.array([[-aspect, aspect], [-1, 1]]) / 2 * scale + shift
    img_plot.set_extent(extent.ravel())
    
    display_params['x'] = x
    display_params['y'] = y
    display_params['scale'] = scale
    display_params['rotation'] = rotation
