import time
from threading import Thread


class DummyLED:
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return self.name

    def blink(self, on_time=1, off_time=1, n=None, background=True):
        if background:
            print(f"{self} BLINK")
        else:
            for _ in range(n):
                self.on()
                time.sleep(on_time)
                self.off()
                time.sleep(off_time)

    def off(self):
        print(f"{self} OFF")

    def on(self):
        print(f"{self} ON")

    def toggle(self):
        print(f"{self} TOGGLE")


class DummyLEDBoard(DummyLED):
    def __init__(self, name: str):
        self.name = name
        self.red = DummyLED(f"R{name}")
        self.yellow = DummyLED(f"O{name}")
        self.green = DummyLED(f"G{name}")


class DummyButton:
    def __init__(self, name: str):
        self.name = name
        self.hold_time = 1

    def when_held(self):
        print(f"{self.name} held")

    def when_pressed(self):
        print(f"{self.name} pressed")

    def when_released(self):
        print(f"{self.name} released")


class DummyHat(Thread):
    """Simulates a HAT with 2 * 3 LEDs and 2 buttons."""

    def __init__(self, name="dummy_hat"):
        super().__init__(name=name, daemon=True)
        self.lights_1 = DummyLEDBoard("1")
        self.lights_2 = DummyLEDBoard("2")
        self.button_1 = DummyButton("B1")
        self.button_2 = DummyButton("B2")
        self.start()

    def on_input(self, inp: str):
        if inp[0] == '1':
            button = self.button_1
        elif inp[0] == '2':
            button = self.button_2
        else:
            return
        if len(inp) == 1:
            button.when_released()
        else:
            button.when_held()

    def run(self):
        while True:
            print(f"{self.name} input: ")
            self.on_input(input())
