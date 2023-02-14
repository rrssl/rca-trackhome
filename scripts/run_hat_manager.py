"""Routine that manages the HAT."""
from argparse import ArgumentParser
from multiprocessing.connection import Client, Connection, Listener

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
    hat = DummyHat() if dummy else JamHat()
    # Lights on the first row are all managed by the tracker daemon, which
    # should be spawned after the HAT manager.
    hat.lights_1.off()
    # The HAT manager controls O2.
    hat.lights_2.yellow.off()
    # B2 requires a long press to send the poweroff signal.
    hat.button_2.hold_time = 3
    return hat


def set_buttons_callback(hat: JamHat, hard_in: Connection):
    def b1_cb():
        hard_in.send("TOGGLE")

    def b2_cb():
        hard_in.send("POWEROFF")

    hat.button_1.when_released = b1_cb
    hat.button_2.when_held = b2_cb


def run_event_loop(listener: Listener, conf: dict):
    hat = init_io(dummy=conf['dummy'])
    running = True
    while running:
        with listener.accept() as hard_out:
            while True:
                try:
                    msg = hard_out.recv()
                except EOFError:
                    break
                # System messages
                if msg == "LISTENING":
                    hard_in = Client(tuple(conf['hat']['address_in']))
                    set_buttons_callback(hat, hard_in)
                elif msg == "POWEROFF":
                    running = False
                    hard_in.close()
                    # Blink O2 for 3 blocking seconds then exit the loop.
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


def main():
    track_publish.get_arg_parser = get_arg_parser
    conf = track_publish.get_config()
    try:
        with Listener(tuple(conf['hat']['address_out'])) as listener:
            run_event_loop(listener, conf)
    except OSError:
        # Another HAT manager is already listening.
        return


if __name__ == "__main__":
    main()
