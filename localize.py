"""
The Pozyx ready to localize tutorial (c) Pozyx Labs
Please read the tutorial that accompanies this sketch:
https://www.pozyx.io/Documentation/Tutorials/ready_to_localize/Python

This tutorial requires at least the contents of the Pozyx Ready to Localize
kit. It demonstrates the positioning capabilities of the Pozyx device both
locally and remotely. Follow the steps to correctly set up your environment in
the link, change the parameters and upload this sketch. Watch the coordinates
change as you move your device around!
"""
from pypozyx import (POZYX_SUCCESS, Coordinates, DeviceCoordinates, DeviceList,
                     PozyxConstants, PozyxRegisters, PozyxSerial,
                     SingleRegister, get_first_pozyx_serial_port)


def get_network_name(network_id: int = None):
    """Get the name of the device (tag or anchor) as a '0x****' string."""
    if network_id is None:
        name = "MASTER"
    else:
        name = f"0x{network_id:04x}"
    return name


def get_latest_error(
    master: PozyxSerial,
    operation: str,
    remote_id: int = None
):
    """Get the latest device's error."""
    error_message = f"{operation} error on tag {get_network_name(remote_id)}"
    error_code = SingleRegister()
    status = master.getErrorCode(error_code, remote_id)
    if remote_id is None or status == POZYX_SUCCESS:
        error_message += f": {master.getErrorMessage(error_code)}"
    else:
        # Only happens when not able to communicate with a remote tag.
        error_message += (
            f", but couldn't retrieve remote error;"
            f"{get_latest_error(master, '')}"
        )
    return error_message


def get_num_anchors(master: PozyxSerial, remote_id: int = None):
    """Get the number of anchors added to the tag."""
    list_size = SingleRegister()
    master.getDeviceListSize(list_size, remote_id)
    return list_size[0]


def get_position_str(position):
    """Return the tag's position as a human-readable string."""
    return f"x: {position.x}mm y: {position.y}mm z: {position.z}mm"


def get_config_str(master: PozyxSerial, remote_id: int = None):
    """Return the tag's anchor configuration as a human-readable string."""
    num_anchors = get_num_anchors(master, remote_id)
    config_str = f"Anchors found: {num_anchors}\n"
    device_list = DeviceList(list_size=num_anchors)
    master.getDeviceIds(device_list, remote_id)
    for nid in device_list:
        anchor_coords = Coordinates()
        master.getDeviceCoordinates(nid, anchor_coords, remote_id)
        config_str += f"Anchor {get_network_name(nid)}: {anchor_coords}\n"
    return config_str


def set_anchors_manual(
    master: PozyxSerial,
    anchors: list[DeviceCoordinates],
    save_to_flash: bool = False,
    remote_id: int = None
):
    """Adds the manually measured anchors to the Pozyx's device list."""
    status = master.clearDevices(remote_id)
    for anchor in anchors:
        status &= master.addDevice(anchor, remote_id)
    if len(anchors) > 4:
        status &= master.setSelectionOfAnchors(
            PozyxConstants.ANCHOR_SELECT_AUTO,
            len(anchors),
            remote_id=remote_id
        )
    if save_to_flash:
        master.saveAnchorIds(remote_id)
        master.saveRegisters(
            [PozyxRegisters.POSITIONING_NUMBER_OF_ANCHORS],
            remote_id=remote_id
        )
    return status


def main():
    """Entry point"""
    # --- CONFIG ---
    serial_port = get_first_pozyx_serial_port()
    if serial_port is None:
        print("No Pozyx connected. Check your USB cable or your driver!")
        return
    remote_id = 0x7625                 # network ID of the tag
    remote = True                      # whether to use a remote tag or master
    if not remote:
        remote_id = None
    # Necessary data for calibration, change the IDs and coordinates yourself
    # according to your measurements.
    anchors = [
        DeviceCoordinates(0x681D, 1, Coordinates( 520,    0, 1125)),
        DeviceCoordinates(0x685C, 1, Coordinates(3270,  400, 2150)),
        DeviceCoordinates(0x0D31, 1, Coordinates(4555, 2580, 1630)),
        DeviceCoordinates(0x0D2D, 1, Coordinates( 400, 3180, 1895))
    ]
    # Positioning algorithm to use, other is PozyxConstants.POSITIONING_ALGORITHM_TRACKING
    algorithm = PozyxConstants.POSITIONING_ALGORITHM_UWB_ONLY
    # Positioning dimension. Options are
    #  - PozyxConstants.DIMENSION_2D
    #  - PozyxConstants.DIMENSION_2_5D
    #  - PozyxConstants.DIMENSION_3D
    dimension = PozyxConstants.DIMENSION_2D
    # Height of device, required in 2.5D positioning
    height = 1000
    # --- END OF CONFIG ---

    # Initialize tags.
    pozyx = PozyxSerial(serial_port)
    if remote_id is None:
        pozyx.printDeviceInfo(remote_id)
    else:
        for device_id in [None, remote_id]:
            pozyx.printDeviceInfo(device_id)
    # Configure anchors.
    status = set_anchors_manual(pozyx, anchors, remote_id=remote_id)
    if status != POZYX_SUCCESS or get_num_anchors(pozyx, remote_id) != len(anchors):
        print(get_latest_error(pozyx, "Configuration", remote_id))
    print(get_config_str(pozyx, remote_id))
    # Start positioning loop.
    remote_name = get_network_name(remote_id)
    while True:
        position = Coordinates()
        status = pozyx.doPositioning(
            position, dimension, height, algorithm, remote_id=remote_id
        )
        if status == POZYX_SUCCESS:
            print(f"POS [{remote_name}]: ({get_position_str(position)})")
        else:
            print(get_latest_error(pozyx, "Positioning", remote_id))


if __name__ == "__main__":
    main()
