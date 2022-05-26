"""
Functions to initialize and use the Pozyx tracker.
"""
import pypozyx as px


def init_master(timeout: float = .1):
    """Initialize the master tag."""
    port = px.get_first_pozyx_serial_port()
    if port is None:
        raise OSError("No Pozyx connected. Check your USB cable or driver!")
    master = px.PozyxSerial(port, timeout=timeout, write_timeout=timeout)
    return master


def do_positioning(
    master: px.PozyxSerial,
    dimension: int,
    algorithm: int,
    remote_id: int = None
):
    """Perform positioning of the tag."""
    pos = px.Coordinates()
    status = master.doPositioning(
        pos, dimension=dimension, algorithm=algorithm, remote_id=remote_id
    )
    if status != px.POZYX_SUCCESS:
        return None
    if dimension == px.PozyxConstants.DIMENSION_2D:
        return (pos.x, pos.y)
    return (pos.x, pos.y, pos.z)


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


def get_anchors_config(master: px.PozyxSerial, remote_id: int = None):
    """Return the tag's anchor configuration.

    It doesn't mean that the anchors are actually on and working! It only
    means that the tag is configured to recognize these anchors and assign them
    this position.

    """
    list_size = px.SingleRegister()
    master.getDeviceListSize(list_size, remote_id)
    device_list = px.DeviceList(list_size=list_size[0])
    master.getDeviceIds(device_list, remote_id)
    anchors = {}
    for nid in device_list:
        coords = px.Coordinates()
        master.getDeviceCoordinates(nid, coords, remote_id)
        anchors[get_network_name(nid)] = (coords.x, coords.y, coords.z)
    return anchors


def set_anchors_manual(
    master: px.PozyxSerial,
    anchors: dict[str, tuple[float, float, float]],
    save_to_flash: bool = False,
    remote_id: int = None
):
    """Adds the manually measured anchors to the Pozyx's device list."""
    status = master.clearDevices(remote_id)
    for id_hex, xyz in anchors.items():
        # Second argument of DeviceCoordinates is 1 for 'anchor'.
        coords = px.DeviceCoordinates(int(id_hex, 16), 1, px.Coordinates(*xyz))
        status &= master.addDevice(coords, remote_id)
    if len(anchors) > 4:
        status &= master.setSelectionOfAnchors(
            px.PozyxConstants.ANCHOR_SELECT_AUTO,
            len(anchors),
            remote_id=remote_id
        )
    if save_to_flash:
        master.saveNetwork(remote_id)
        # master.saveAnchorIds(remote_id)
        # master.saveRegisters(
        #     [px.PozyxRegisters.POSITIONING_NUMBER_OF_ANCHORS],
        #     remote_id=remote_id
        # )
    return status == px.POZYX_SUCCESS
