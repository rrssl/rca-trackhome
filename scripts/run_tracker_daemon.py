"""This scripts allows to remotely start/stop tracking and poweroff."""
import fcntl
import os
import subprocess
import time
from pathlib import Path

import track_publish


def check_already_running(label="default"):
    """Detect if an an instance with the label is already running, globally
    at the operating system level.

    The lock will be released when the program exits, or could be
    released if the file pointer were closed.

    Source: https://stackoverflow.com/a/384493
    """
    lock_path = Path(f"/tmp/tracker_daemon_{label}.lock")
    # Using `os.open` ensures that the file pointer won't be closed
    # by Python's garbage collector after the function's scope is exited.
    lock_file_pointer = os.open(lock_path, os.O_WRONLY | os.O_CREAT)
    try:
        fcntl.lockf(lock_file_pointer, fcntl.LOCK_EX | fcntl.LOCK_NB)
        already_running = False
    except IOError:
        already_running = True
    return already_running


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
    if check_already_running():
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
    pos_period = conf['interval']
    tracker.logger.debug(f"Starting ({pid=}).")
    try:
        while state['on']:
            if counter % 60 == 0:
                tracker.logger.debug(f"Running ({pid=}).")
            counter += 1
            # Reload config if applicable.
            if state['conf']:
                tracker.reload_anchors_from_str(state['conf'])
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
        pass
    finally:
        tracker.logger.debug(f"Exiting ({pid=}).")
        client.disconnect()
        subprocess.call(['sudo', 'poweroff'])


if __name__ == "__main__":
    main()
