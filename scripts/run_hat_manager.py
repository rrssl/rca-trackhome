"""Routine that manages the HAT."""
from argparse import ArgumentParser
from multiprocessing.connection import Client, Listener

from gpiozero import JamHat

import track_publish
from trkpy.dummy_hat import DummyHat


def get_arg_parser():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        '--config',
        metavar='FILE',
        required=True,
        help="Path to the config file"
    )
    parser.add_argument(
        '--dummy',
        action='store_true',
        help="Use a dummy HAT"
    )
    return parser


def init_io(dummy: bool = False):
    if dummy:
        hat = DummyHat()
    else:
        hat = JamHat()
    # Lights on the first row are all managed by the tracker daemon, which
    # should be spawned after the HAT manager.
    hat.lights_1.off()
    # The HAT manager controls O2.
    hat.lights_2.yellow.off()
    # B2 requires a long press to send the poweroff signal.
    hat.button_2.hold_time = 3
    return hat


def set_buttons_callback(hat: JamHat, dest_address: tuple[str, int]):
    conn = Client(dest_address)

    def b1_cb():
        conn.send("TOGGLE")

    def b2_cb():
        conn.send("POWEROFF")
        conn.close()

    hat.button_1.when_released = b1_cb
    hat.button_2.when_held = b2_cb


def main():
    track_publish.get_arg_parser = get_arg_parser
    conf = track_publish.get_config()
    address_out = tuple(conf['hat']['address_out'])
    address_in = tuple(conf['hat']['address_in'])
    with Listener(address_out) as listener:
        hat = init_io(dummy=conf['dummy'])
        running = True
        while running:
            with listener.accept() as conn:
                while True:
                    try:
                        msg = conn.recv()
                    except EOFError:
                        break
                    # System messages
                    if msg == "LISTENING":
                        set_buttons_callback(hat, address_in)
                    elif msg == "POWEROFF":
                        running = False
                        # Blink O2 for 3 seconds then exit the loop.
                        hat.lights_2.yellow.blink(.5, .5, 3, background=False)
                        break
                    else:
                        # Output signals
                        led_name, state = msg
                        led_board = {
                            '1': hat.lights_1,
                            '2': hat.lights_2
                        }[led_name[1]]
                        led = {
                            'R': led_board.red,
                            'O': led_board.yellow,
                            'G': led_board.green
                        }[led_name[0]]
                        if state:
                            led.on()
                        else:
                            led.off()


if __name__ == "__main__":
    main()
