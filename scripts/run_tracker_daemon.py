"""This scripts allows to remotely start/stop tracking and poweroff."""
import json
import os
import subprocess
import time

from gpiozero import JamHat

import track_publish
from trkpy.cloud import AWSClient
from trkpy.system import is_online, lock_file


def check_already_running(conf: dict):
    """Detect if an an instance with the label is already running, globally
    at the operating system level.
    """
    lock_path = conf['daemon']['lock_file']
    is_locked = lock_file(lock_path)
    return not is_locked


def get_state_updater(state: dict):
    def callback(unused_client, unused_userdata, message):
        payload = str(message.payload.decode('utf-8'))
        # Apply command if applicable.
        if payload == 'START':
            state['run'] = True
        elif payload == 'STOP':
            state['run'] = False
        elif payload == 'POWEROFF':
            state['on'] = False
        # Update config if applicable.
        if payload[0] == '{':
            state['conf'] = payload
        else:
            state['conf'] = None
    return callback


def init_io(state):
    hat = JamHat()
    hat.lights_1.off()
    hat.lights_2.yellow.off()

    def toggle_tracking():
        state['run'] = not state['run']
        hat.lights_1.yellow.toggle()

    def poweroff():
        state['on'] = False
        hat.lights_2.yellow.blink(.5, .5)

    hat.button_1.when_released = toggle_tracking
    hat.button_2.hold_time = 3
    hat.button_2.when_held = poweroff
    return hat


def run_track_loop(tracker, state, conf, ppid):
    log_period = conf['daemon']['log_period']
    pos_period = conf['tracking']['interval']
    # cpid = os.getpid()
    counter = 0
    while state['on']:
        if counter % log_period == 0:
            tracker.logger.debug(f"Running ({ppid=}).")
        counter += 1
        # Reload config if applicable.
        if state['conf']:
            state_conf = json.loads(state['conf'])
            pos_period = state_conf['interval']
            tracker.reload_conf(state_conf)
            state['conf'] = None
            continue
        # Run the normal loop.
        t_start = time.time()
        if state['run']:
            tracker.loop()
        else:
            tracker.loop(check_only=True)
        t_elapsed = time.time() - t_start
        time.sleep(max(0, pos_period - t_elapsed))


def main():
    """Entry point"""
    conf = track_publish.get_config()
    # Exit if the daemon is already running.
    pid = os.getpid()
    if check_already_running(conf):
        print(f"Process {pid} ending.")
        return
    while not is_online():
        time.sleep(3)
    # Init cloud client.
    client = AWSClient(**conf['cloud']['aws'])
    # Init state dict (will update according to commands).
    state = {'on': True, 'run': False, 'conf': None}
    client._client.on_message = get_state_updater(state)
    # Init logger.
    logger = track_publish.init_logger(client, conf)
    while not client.connected:
        time.sleep(1)
    # Init I/O board.
    hat = init_io()
    # Init tracker.
    tracker = track_publish.init_tracker(logger, conf, output=hat)
    # Start the event loop.
    hat.lights_1.yellow.on()
    tracker.logger.debug(f"Ready ({pid=}).")
    poweroff_on_exit = True
    try:
        run_track_loop(tracker, state, conf, pid)
    except KeyboardInterrupt:
        poweroff_on_exit = False
    finally:
        hat.lights_1.off()
        tracker.logger.debug(f"Exiting ({pid=}).")
        client.disconnect()
        if poweroff_on_exit:
            subprocess.call(['sudo', 'poweroff'])


if __name__ == "__main__":
    main()
