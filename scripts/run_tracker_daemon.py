"""This scripts allows to remotely start/stop tracking and poweroff."""
import json
import os
import subprocess
import time

import track_publish
from trkpy.system import lock_file


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


def main():
    """Entry point"""
    conf = track_publish.get_config()
    # Exit if the daemon is already running.
    pid = os.getpid()
    if check_already_running(conf):
        print(f"Process {pid} ending.")
        return
    # Init cloud client, logger and tracker.
    client = track_publish.CloudIOTClient(**conf['cloud'])
    logger = track_publish.init_logger(client, conf)
    tracker = track_publish.init_tracker(logger, conf)
    # Init state dict (will update according to commands).
    state = {'on': True, 'run': False, 'conf': None}
    client.on_message = get_state_updater(state)
    # Start the event loop.
    counter = 0
    pos_period = conf['tracking']['interval']
    poweroff_on_exit = True
    tracker.logger.debug(f"Starting ({pid=}).")
    try:
        while state['on']:
            if counter % 60 == 0:
                tracker.logger.debug(f"Running ({pid=}).")
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
    except KeyboardInterrupt:
        poweroff_on_exit = False
    finally:
        tracker.logger.debug(f"Exiting ({pid=}).")
        client.disconnect()
        if poweroff_on_exit:
            subprocess.call(['sudo', 'poweroff'])


if __name__ == "__main__":
    main()
