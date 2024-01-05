# Housing standardisation: Study of home use patterns

This work is part of the AHRC-funded project ["Housing Standardisation: The Architecture of Regulations and Design Standards"](https://gtr.ukri.org/projects?ref=AH%2FW003198%2F1). The present repository contains the code supporting the collection and visualisation of quantitative data on how people use their homes. This data was collected in 2023-24 in more than 30 homes and across 6 countries.

The data collection was based on a real-time locating system (RTLS) using the [Creator One kit](https://www.pozyx.io/creator-one-kit) from Pozyx (no longer available). This kit used a wireless two-way ranging UWB protocol and advertised a 10 cm indoor positioning accuracy.
Because of specific requirements in terms of flexibility, privacy, and control over the data, we decided to only use the hardware and basic positioning software, and build our own solution to orchestrate the devices, configure them, monitor them, securely backup the data on the cloud, and visualise the location data (both real-time and recordings).

## Overview

The two main folders are `trkpy`, the core package of this project, and `scripts`, which contains all the high-level python and shell files.

### The `trkpy` package

Cloud (used by both client and server to send and receive data)
- `cloud.py`
- `collect.py`
- `publish.py`

Client (Raspberry Pi)
- `dummy_hat.py`
- `system.py`
- `track.py`

Configuration (used by the server)
- `validate.py`

Visualisation
- `postprocess.py`

### Scripts

Client
- `run_crontab.sh`
- `run_hat_manager.py`
- `run_tracker_daemon.py`
- `track_publish.py`
- `update_daemon_led.py`
- `update_online_led.py`

Server
- `collect_save.py`

Debugging
- `check_poweroff.py`
- `localize_demo.py`
- `measure_distance.py`
- `test_tracking_config.py`

Visualisation
- `create_tracking_video.py`
- `view_log.sh`

## Requirements

This project was developed using Python 3.9 and managing dependencies with Anaconda (or Miniforge on the Raspberry Pi). The necessary packages are included in `environment.yml`.
