# Housing standardisation: Study of home use patterns

This work is part of the AHRC-funded project ["Housing Standardisation: The Architecture of Regulations and Design Standards"](https://gtr.ukri.org/projects?ref=AH%2FW003198%2F1). The present repository contains the code supporting the collection and visualisation of quantitative data on how people use their homes. This data was collected in 2023-24 in more than 30 homes and across 6 countries.

The data collection was based on a real-time locating system (RTLS) using the [Creator One kit](https://www.pozyx.io/creator-one-kit) from Pozyx (no longer available). This kit used a wireless two-way ranging UWB protocol and advertised a 10 cm indoor positioning accuracy.
Because of specific requirements in terms of flexibility, privacy, and control over the data, we decided to only use the hardware and basic positioning software, and to build our own solution to orchestrate, configure, and monitor the devices, as well as securely backup the data via the cloud and create visualisations of the location data (both real-time and from recordings).

## Overview

The two main folders are `trkpy`, the core package of this project, and `scripts`, which contains all the high-level python and shell files.

### The `trkpy` package

Cloud (used by both client and server to send and receive data)
- `cloud.py` Implements `CloudClient`, an MQTT client (first was using Google Cloud, then moved to AWS).
- `collect.py` Implements `CloudCollector`, which runs server-side to collect and save the data.
- `publish.py` Implements `CloudHandler`, which uses Python's logging system to publish to the cloud.

Client (Raspberry Pi)
- `dummy_hat.py` Used when no HAT is attached to the Pi, to simulate its functionality.
- `system.py` System-level utility functions (network, power, lock).
- `track.py` Provides a more pythonic interface to the `pypozyx` package, and implements `DummyPozyxSerial` for debugging.

Configuration (used by the server)
- `validate.py` Defines the schema and validation function for the JSON file used to configure the RTLS.

Visualisation
- `postprocess.py` Defines functions to process recordings for visualisation.

### Scripts

Client
- `run_crontab.sh` Called by `cron` to automatically start the necessary processes. Runs the `run_*` and `update_*` scripts.
- `run_hat_manager.py` Process that manages the HAT (physical I/O of the Pi).
- `run_tracker_daemon.py` Process that manages all aspects of the RTLS.
- `track_publish.py` Script run manually to check the proper functioning of the RTLS and cloud communication.
- `update_daemon_led.py` Controls the LED indicating whether the tracker daemon is running.
- `update_online_led.py` Controls the LED indicating whether the Pi has network connectivity.

Server
- `collect_save.py` Process that collects and saves the data (location and logs), and starts the web interface for RTLS configuration and monitoring.

Debugging
- `check_poweroff.py` Used on the Pi to check whether it can be powered off from a python script.
- `localize_demo.py` Used on the Pi to check the RTLS positioning capability (1 tag and 3+ anchors required).
- `measure_distance.py` Used on the Pi to check basic distance measurements between two tags.
- `test_tracking_config.py` Checks whether a JSON configuration file is valid.

Visualisation
- `create_tracking_video.py` Creates an animation given the positioning data, RTLS configuration, and floorplan.
- `view_log.sh` Processes the logs to be more legible.

## Requirements

This project was developed using Python 3.9 and managing dependencies with Anaconda (or Miniforge on the Raspberry Pi). The necessary packages are included in `environment.yml`.
