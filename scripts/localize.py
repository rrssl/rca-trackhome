"""
Script demonstrating how to use the Pozyx system to localize a device.
"""
import pypozyx as px

from trkpy import track


def main():
    """Entry point"""
    # --- CONFIG ---
    serial_port = px.get_first_pozyx_serial_port()
    if serial_port is None:
        print("No Pozyx connected. Check your USB cable or your driver!")
        return
    remote_id = 0x7625  # network ID of the tag
    remote = False  # whether to use a remote tag or master
    if not remote:
        remote_id = None
    # Necessary data for calibration, change the IDs and coordinates yourself
    # according to your measurements.
    anchors = {
        0x681D: (520, 0, 1125),
        0x685C: (3270, 400, 2150),
        0x0D31: (4555, 2580, 1630),
        0x0D2D: (400, 3180, 1895)
    }
    # Positioning algorithm to use. Options are:
    #  - PozyxConstants.POSITIONING_ALGORITHM_TRACKING
    #  - PozyxConstants.POSITIONING_ALGORITHM_UWB_ONLY
    algorithm = px.PozyxConstants.POSITIONING_ALGORITHM_UWB_ONLY
    # Positioning dimension. Options are
    #  - PozyxConstants.DIMENSION_2D
    #  - PozyxConstants.DIMENSION_2_5D
    #  - PozyxConstants.DIMENSION_3D
    dimension = px.PozyxConstants.DIMENSION_2D
    # Height of device, required in 2.5D positioning
    height = 1000
    # --- END OF CONFIG ---

    # Initialize tags.
    master = px.PozyxSerial(serial_port)
    if remote_id is None:
        master.printDeviceInfo(remote_id)
    else:
        for device_id in [None, remote_id]:
            master.printDeviceInfo(device_id)
    # Configure anchors.
    status = track.set_anchors_manual(master, anchors, remote_id=remote_id)
    if (
        status != px.POZYX_SUCCESS
        or track.get_num_anchors(master, remote_id) != len(anchors)
    ):
        print(track.get_latest_error(master, "Configuration", remote_id))
    print(track.get_config_str(master, remote_id))
    # Start positioning loop.
    remote_name = track.get_network_name(remote_id)
    while True:
        position = px.Coordinates()
        status = master.doPositioning(
            position, dimension, height, algorithm, remote_id=remote_id
        )
        if status == px.POZYX_SUCCESS:
            print(f"POS [{remote_name}]: ({track.get_position_str(position)})")
        else:
            print(track.get_latest_error(master, "Positioning", remote_id))


if __name__ == "__main__":
    main()
