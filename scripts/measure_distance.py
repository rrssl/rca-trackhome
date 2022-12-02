"""
This demo requires two Pozyx devices. It demonstrates the ranging capabilities
and the functionality to remotely control a Pozyx device. Move around with
the other Pozyx device.

This demo measures the range between the two devices.

"""
from pypozyx import (PozyxSerial, PozyxConstants, SingleRegister, NetworkID,
                     DeviceRange, POZYX_SUCCESS, get_first_pozyx_serial_port)


def get_master_error(p: PozyxSerial):
    error_code = SingleRegister()
    if p.getErrorCode(error_code) == POZYX_SUCCESS:
        return p.getErrorMessage(error_code)


def get_master_id(p: PozyxSerial):
    network_id = NetworkID()
    p.getNetworkId(network_id)
    return network_id.id


def main():
    # ID of the tag performing the ranging. If you want the master tag to
    # perform it, then this ID should be None! It won't work if the ID is the
    # same as the master's.
    remote_id = None
    # remote_id = 0x7625
    # ID of the tag to which the distance is measured. It can be the master tag
    # as long as remote tag is selected to perform the ranging.
    destination_id = 0x7625
    # destination_id = 0x764c
    # The ranging protocol. Alternative: PozyxConstants.RANGE_PROTOCOL_FAST
    ranging_protocol = PozyxConstants.RANGE_PROTOCOL_PRECISION

    # Setup
    serial_port = get_first_pozyx_serial_port()
    if serial_port is None:
        print("No Pozyx connected. Check your USB cable or your driver!")
        return
    pozyx = PozyxSerial(serial_port)
    pozyx.setRangingProtocol(ranging_protocol)

    master_id = get_master_id(pozyx)
    if remote_id == master_id:
        print("The remote and master's ID are the same. Use a different id for remote!")
        return

    for device in (remote_id, destination_id):
        if device == master_id:
            device = None
        pozyx.printDeviceInfo(device)

    while True:
        device_range = DeviceRange()
        status = pozyx.doRanging(destination_id, device_range, remote_id)
        if status == POZYX_SUCCESS:
            print(device_range)
        else:
            error = get_master_error(pozyx)
            print(error if error else "Unknown error")


if __name__ == "__main__":
    main()
