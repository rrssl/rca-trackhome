"""
Functions to initialize and use the Pozyx tracker.
"""
import pypozyx as px


def get_network_name(network_id: int = None):
    """Get the name of the device (tag or anchor) as a '0x****' string."""
    if network_id is None:
        name = "MASTER"
    else:
        name = f"0x{network_id:04x}"
    return name


def get_latest_error(
    master: px.PozyxSerial,
    operation: str,
    remote_id: int = None
):
    """Get the latest device's error."""
    error_message = f"{operation} error on tag {get_network_name(remote_id)}"
    error_code = px.SingleRegister()
    status = master.getErrorCode(error_code, remote_id)
    if remote_id is None or status == px.POZYX_SUCCESS:
        error_message += f": {master.getErrorMessage(error_code)}"
    else:
        # Only happens when not able to communicate with a remote tag.
        error_message += (
            f", but couldn't retrieve remote error;"
            f"{get_latest_error(master, '')}"
        )
    return error_message


def get_num_anchors(master: px.PozyxSerial, remote_id: int = None):
    """Get the number of anchors added to the tag."""
    list_size = px.SingleRegister()
    master.getDeviceListSize(list_size, remote_id)
    return list_size[0]


def get_position_str(position):
    """Return the tag's position as a human-readable string."""
    return f"x: {position.x}mm y: {position.y}mm z: {position.z}mm"


def get_config_str(master: px.PozyxSerial, remote_id: int = None):
    """Return the tag's anchor configuration as a human-readable string."""
    num_anchors = get_num_anchors(master, remote_id)
    config_str = f"Anchors found: {num_anchors}\n"
    device_list = px.DeviceList(list_size=num_anchors)
    master.getDeviceIds(device_list, remote_id)
    for nid in device_list:
        anchor_coords = px.Coordinates()
        master.getDeviceCoordinates(nid, anchor_coords, remote_id)
        config_str += f"Anchor {get_network_name(nid)}: {anchor_coords}\n"
    return config_str


def set_anchors_manual(
    master: px.PozyxSerial,
    anchors: dict[int, tuple[float, float, float]],
    save_to_flash: bool = False,
    remote_id: int = None
):
    """Adds the manually measured anchors to the Pozyx's device list."""
    status = master.clearDevices(remote_id)
    for name, xyz in anchors.items():
        # Second argument of DeviceCoordinates is 1 for 'anchor'.
        coords = px.DeviceCoordinates(name, 1, px.Coordinates(*xyz))
        status &= master.addDevice(coords, remote_id)
    if len(anchors) > 4:
        status &= master.setSelectionOfAnchors(
            px.PozyxConstants.ANCHOR_SELECT_AUTO,
            len(anchors),
            remote_id=remote_id
        )
    if save_to_flash:
        master.saveAnchorIds(remote_id)
        master.saveRegisters(
            [px.PozyxRegisters.POSITIONING_NUMBER_OF_ANCHORS],
            remote_id=remote_id
        )
    return status