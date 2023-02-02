"""
Functions to initialize and use the Pozyx tracker.
"""
from collections import defaultdict
from typing import Union

import pypozyx as px
from pypozyx.structures.device_information import DeviceDetails


class DummyPozyxSerial:
    """Simulates a master tag."""

    def __init__(
        self,
        port,
        baudrate=115200,
        timeout=0.1,
        write_timeout=0.1,
        print_output=False,
        debug_trace=False,
        show_trace=False,
        suppress_warnings=False
    ):
        self.tag2devices = defaultdict(list)

    def doPositioning(
        self,
        position,
        dimension=3,
        height=0,
        algorithm=None,
        remote_id=None,
        timeout=None
    ):
        position.x = 100
        position.y = 200
        if dimension == px.PozyxConstants.DIMENSION_2_5D:
            position.z = height
        elif dimension == px.PozyxConstants.DIMENSION_3D:
            position.z = 300
        return px.POZYX_SUCCESS

    def addDevice(self, device_coordinates, remote_id=None):
        self.tag2devices[remote_id].append(device_coordinates)
        return px.POZYX_SUCCESS

    def clearDevices(self, remote_id=None):
        self.tag2devices[remote_id].clear()
        return px.POZYX_SUCCESS

    def getDeviceCoordinates(self, device_id, coordinates, remote_id=None):
        for device_coordinates in self.tag2devices[remote_id]:
            if device_coordinates.network_id == device_id:
                coordinates.load(device_coordinates.pos.data)
        return px.POZYX_SUCCESS

    def getDeviceDetails(self, system_details, remote_id=None):
        system_details.data[0] = 0x43
        if remote_id in self.tag2devices:
            system_details.data[3] = 0b111111
        else:
            system_details.data[3] = 0b110000
        return px.POZYX_SUCCESS

    def getDeviceIds(self, devices, remote_id=None):
        for i, device_coordinates in enumerate(self.tag2devices[remote_id]):
            devices.data[i] = device_coordinates.network_id
        return px.POZYX_SUCCESS

    def getDeviceListSize(self, device_list_size, remote_id=None):
        device_list_size.value = len(self.tag2devices[remote_id])
        return px.POZYX_SUCCESS

    def getErrorCode(self, error_code, remote_id=None):
        error_code.value = 0xFF
        return px.POZYX_SUCCESS

    def getErrorMessage(self, error_code):
        return px.PozyxSerial.getErrorMessage(self, error_code)

    def saveNetwork(self, remote_id=None):
        return px.POZYX_SUCCESS

    def setSelectionOfAnchors(self, mode, number_of_anchors, remote_id=None):
        return px.POZYX_SUCCESS


def init_master(timeout: float = .1, _dummy: bool = False):
    """Initialize the master tag."""
    if _dummy:
        return DummyPozyxSerial("", timeout=timeout, write_timeout=timeout)
    port = px.get_first_pozyx_serial_port()
    if port is None:
        raise OSError("No Pozyx connected. Check your USB cable or driver!")
    master = px.PozyxSerial(port, timeout=timeout, write_timeout=timeout)
    return master


def do_positioning(
    master: px.PozyxSerial,
    dimension: Union[str, int],
    algorithm: Union[str, int],
    remote_id: int = None
):
    """Perform positioning of the tag."""
    if isinstance(dimension, str):
        dimension = getattr(px.PozyxConstants, dimension)
    if isinstance(algorithm, str):
        algorithm = getattr(px.PozyxConstants, algorithm)
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
        error_message += f" (unreachable); {get_latest_error(master, '')}"
    return error_message


def get_anchors_config(
    master: px.PozyxSerial,
    remote_id: int = None
) -> dict[int, tuple[float, float, float]]:
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
        anchors[nid] = (coords.x, coords.y, coords.z)
    return anchors


def get_device_details(master: px.PozyxSerial, remote_id: int = None):
    """Queries a device for details."""
    details = DeviceDetails()
    status = master.getDeviceDetails(details, remote_id)
    if status == px.POZYX_SUCCESS:
        return details
    return None


def set_anchors_manual(
    master: px.PozyxSerial,
    anchors: dict[int, tuple[float, float, float]],
    save_to_flash: bool = False,
    remote_id: int = None
):
    """Adds the manually measured anchors to the Pozyx's device list."""
    status = master.clearDevices(remote_id)
    for anchor_id, xyz in anchors.items():
        # Second argument of DeviceCoordinates is 1 for 'anchor'.
        coords = px.DeviceCoordinates(anchor_id, 1, px.Coordinates(*xyz))
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
