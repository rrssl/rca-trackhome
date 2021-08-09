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

# +
import json
import os
import time
from datetime import datetime

import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
import pypozyx as px
from PIL import Image

from trkpy import track

# %matplotlib widget

# +
ANCHORS = {
    0x681D: ( 520,    0, 1125),
    0x685C: (3270,  400, 2150),
    0x0D31: (4555, 2580, 1630),
    0x0D2D: ( 400, 3180, 1895)
}

REMOTE_ID = 0x7625  # network ID of the tag
REMOTE = False      # whether to use a remote tag or maste
if not REMOTE:
    REMOTE_ID = None
# Positioning algorithm to use, other is PozyxConstants.POSITIONING_ALGORITHM_TRACKING
POS_ALGO = px.PozyxConstants.POSITIONING_ALGORITHM_UWB_ONLY
# Positioning dimension. Options are
#  - PozyxConstants.DIMENSION_2D
#  - PozyxConstants.DIMENSION_2_5D
#  - PozyxConstants.DIMENSION_3D
DIM = px.PozyxConstants.DIMENSION_2D
# Height of device, required in 2.5D positioning
HEIGHT = 1000

FLOORPLAN_PATH = "granite_floorplan.jpg"
FIGSIZE = (6, 6)

# +
anchors_array = np.array([p[:2] for p in ANCHORS.values()])
default_shift = anchors_array.mean(axis=0).reshape((2, 1))
default_scale = np.ptp(anchors_array, axis=0).max() * 2

base_img = Image.open(FLOORPLAN_PATH)
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
        'floorplan_path': os.path.abspath(FLOORPLAN_PATH),
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
    description='Save user profile',
    disabled=False,
    button_style='', # 'success', 'info', 'warning', 'danger' or ''
    tooltip='Save the configuration on disk',
    icon='save' # (FontAwesome names without the `fa-` prefix)
)
button.on_click(save_profile)


# +
fig, ax = plt.subplots(figsize=FIGSIZE)
ax.set_aspect('equal')
ax.set_axis_off()

ax.scatter(*zip(*[pos[:2] for pos in ANCHORS.values()]), marker='s')
pos = ax.scatter(0, 0, c='tab:orange', s=100)

img_plot = ax.imshow(np.asarray(base_img), extent=extent.ravel())

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




# +
# Initialize tags.
serial_port = px.get_first_pozyx_serial_port()
if serial_port is None:
    print("No Pozyx connected. Check your USB cable or your driver!")
    raise Exception
master = px.PozyxSerial(serial_port)
if REMOTE_ID is None:
    master.printDeviceInfo(REMOTE_ID)
else:
    for device_id in [None, REMOTE_ID]:
        master.printDeviceInfo(device_id)
# Configure anchors.
status = track.set_anchors_manual(master, ANCHORS, remote_id=REMOTE_ID)
if status != px.POZYX_SUCCESS or track.get_num_anchors(master, REMOTE_ID) != len(ANCHORS):
    print(track.get_latest_error(master, "Configuration", REMOTE_ID))
print(track.get_config_str(master, REMOTE_ID))

# This is a trick so that the next cell doesn't run on 'run all cells', giving time to the plot
# above to finish initializing.
initialized = False
# -

if initialized:
    # Start positioning loop.
    # remote_name = track.get_network_name(REMOTE_ID)
    while True:
        position = px.Coordinates()
        status = master.doPositioning(
            position, DIM, HEIGHT, POS_ALGO, remote_id=REMOTE_ID
        )
        if status == px.POZYX_SUCCESS:
            pos.set_offsets((position.x, position.y))
            fig.canvas.draw()
            time.sleep(.5)
    #         print(f"POS [{remote_name}]: ({get_position_str(position)})")
    #     else:
    #         print(get_latest_error(master, "Positioning", REMOTE_ID))
else:
    initialized = True
