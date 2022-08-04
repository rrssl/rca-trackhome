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
import time
from pathlib import Path

import numpy as np
import open3d as o3d
import yaml

# +
CONFIG_PATH = "../config/local.yml"

with open(CONFIG_PATH, 'r', encoding='ascii') as handle:
    conf = yaml.safe_load(handle)
    
data_dir = Path(conf['global']['data_dir']) / "scans" / "sportsman" / "open3d-windows"
intrinsic_path = data_dir / "intrinsic.json"
depth_dir = data_dir / "depth"
color_dir = data_dir / "color"
# -

intrinsic = o3d.io.read_pinhole_camera_intrinsic(str(intrinsic_path))
depth_img_paths = list(sorted(depth_dir.glob("*.png")))


# +
def load_pcloud(depth_img_path: Path, out: o3d.geometry.PointCloud = None):
    depth_img = o3d.io.read_image(str(depth_img_path))
    color_img_path = color_dir / depth_img_path.with_suffix(".jpg").name.replace("depth", "color")
    color_img = o3d.io.read_image(str(color_img_path))
    rgbd_img = o3d.geometry.RGBDImage.create_from_color_and_depth(
        color_img,
        depth_img,
        convert_rgb_to_intensity=False
    )
    pcloud = o3d.geometry.PointCloud.create_from_rgbd_image(
        rgbd_img,
        intrinsic,
        # depth_scale=1,
        # depth_trunc=3000
    )
    if out is None:
        return pcloud
    out.points = pcloud.points
    out.colors = pcloud.colors
    return out


class RGBD2PCDAnimation():
    def __init__(self, depth_img_paths: list[Path]):
        self.depth_img_paths = depth_img_paths
        self.flag_play = True
        self.flag_exit = False

    def escape_callback(self, vis: o3d.visualization.VisualizerWithKeyCallback):
        self.flag_exit = True
        return False
    
    def space_callback(self, vis: o3d.visualization.VisualizerWithKeyCallback):
        self.flag_play = not self.flag_play
        return False
    
    def run(self):
        # Create Visualizer and set options + callbacks.
        vis = o3d.visualization.VisualizerWithKeyCallback()
        vis.create_window()
        vis.register_key_callback(256, self.escape_callback)
        vis.register_key_callback(32, self.space_callback)
        vis.get_render_option().point_size = 1  # render options need to be set after creating the window!!
        # Initialize the geometry.
        geometry = load_pcloud(self.depth_img_paths[0])
        vis.add_geometry(geometry)
        # Play the animation.
        idx = 1
        while idx < len(self.depth_img_paths) and not self.flag_exit:
            if self.flag_play:
                depth_img_path = self.depth_img_paths[idx]
                load_pcloud(depth_img_path, out=geometry)
                vis.update_geometry(geometry)
                idx +=1
            vis.poll_events()
            vis.update_renderer()
        vis.destroy_window()


# -

anim = RGBD2PCDAnimation(depth_img_paths)
anim.run()
