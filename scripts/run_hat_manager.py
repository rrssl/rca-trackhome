from multiprocessing.connection import Client, Listener

from gpiozero import JamHat


def init_io():
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
    address_out = ("localhost", 8888)
    address_in = ("localhost", 8889)
    with Listener(address_out) as listener:
        hat = init_io()
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
                    # Output signals
                    # ...


if __name__ == "__main__":
    main()
