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
import asyncio
import json
import os
import time
from configparser import ConfigParser

import ipywidgets as widgets
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pypozyx as px
from PIL import Image

from trkpy import track

# %matplotlib widget

# +
CONFIG_PATH = "../config/local.ini"
PROFILE_NAME = "granite_floorplan_20210810163830.json"

FIGSIZE = (6, 6)

# +
config = ConfigParser()
config.read(CONFIG_PATH)

data_path = config['global']['data_path']
profile_path = os.path.join(data_path, PROFILE_NAME)
with open(profile_path) as handle:
    profile = json.load(handle)
print(profile)

# +
# Initialize tags.
serial_port = px.get_first_pozyx_serial_port()
if serial_port is None:
    raise OSError("No Pozyx connected. Check your USB cable or your driver!")
master = px.PozyxSerial(serial_port)
remote_id = profile['remote_id']
if remote_id is None:
    master.printDeviceInfo(remote_id)
else:
    for device_id in [None, remote_id]:
        master.printDeviceInfo(device_id)
# Configure anchors.
anchors = {int(k): v for k, v in profile['anchors'].items()}
# status = track.set_anchors_manual(master, anchors, remote_id=remote_id)
# if status != px.POZYX_SUCCESS or track.get_num_anchors(master, remote_id) != len(anchors):
#     print(track.get_latest_error(master, "Configuration", remote_id))
print(track.get_config_str(master, remote_id))

pos_dim = getattr(px.PozyxConstants, config['tracking']['pos_dim'])
pos_algo = getattr(px.PozyxConstants, config['tracking']['pos_algo'])


def get_position_2d(master: px.PozyxSerial, remote_id: int = None):
    pos = px.Coordinates()
    status = master.doPositioning(
        pos, dimension=pos_dim, algorithm=pos_algo, remote_id=remote_id
    )
    if status == px.POZYX_SUCCESS:
        return (pos.x, pos.y)

init_pos = get_position_2d(master, remote_id)
max_tries = 10
for _ in range(max_tries):
    time.sleep(.1)
    init_pos = get_position_2d(master, remote_id)
    if init_pos is not None:
        print(init_pos)
        break
else:
    print(track.get_latest_error(master, "Positioning", remote_id))

# +
run = False


async def do_positioning():
    while run:
        pos = get_position_2d(master, remote_id)
        if pos:
            pos_plot.set_offsets(pos)
            fig.canvas.draw()
        await asyncio.sleep(.5)


def start_positioning(button):
    global run
    if run is False:
        run = True
        asyncio.create_task(do_positioning())

    
def stop_positioning(button):
    global run
    run = False
    

start_bt = widgets.Button(
    description="Start",
    disabled=False,
    button_style='', # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Start positioning",
    icon='play' # (FontAwesome names without the `fa-` prefix)
)
start_bt.on_click(start_positioning)


stop_bt = widgets.Button(
    description="Stop",
    disabled=False,
    button_style='', # 'success', 'info', 'warning', 'danger' or ''
    tooltip="Stop positioning",
    icon='stop' # (FontAwesome names without the `fa-` prefix)
)
stop_bt.on_click(stop_positioning)

# +
floorplan_img = Image.open(profile['floorplan_path'])
display_params = profile['display_params']
if display_params['rotation']:
    floorplan_img = floorplan_img.rotate(display_params['rotation'], expand=True)
aspect = floorplan_img.width / floorplan_img.height
scale = display_params['scale']
shift = np.array([display_params['x'], display_params['y']]).reshape(2, 1)
extent = np.array([[-aspect, aspect], [-1, 1]]) / 2 * scale + shift

fig, ax = plt.subplots(figsize=FIGSIZE)
ax.set_axis_off()

ax.imshow(np.asarray(floorplan_img), extent=extent.ravel(), zorder=2)
ax.scatter(*zip(*[xyz[:2] for xyz in anchors.values()]), marker='s', zorder=3)
for name, xyz in anchors.items():
    ax.annotate(f"0x{name:04x}", xyz[:2], xytext=(5, 5), textcoords='offset pixels',
                path_effects=[pe.withStroke(linewidth=2, foreground='w')])
pos_plot = ax.scatter(*init_pos, c='tab:orange', s=100, zorder=4)

fig.tight_layout()

display(start_bt)
display(stop_bt)
# -

asyncio.all_tasks()
