"""This scripts allows to remotely start/stop tracking and poweroff."""
import os
import subprocess
import time
from pathlib import Path

import track_publish


def check_already_running(pid_file: Path):
    if not pid_file.exists():
        return False
    my_name = Path(__file__).with_suffix("").name
    running_pid = int(pid_file.read_text())
    running_cmd = subprocess.run(
        f"ps -fp {running_pid} -o args=".split(),
        capture_output=True,
        check=False,
        encoding='utf-8'
    ).stdout
    if my_name in running_cmd and running_pid != os.getpid():
        # Another daemon is currently running
        return True
    return False


def get_state_updater(state: dict):
    def callback(unused_client, unused_userdata, message):
        payload = str(message.payload.decode('utf-8'))
        if payload == 'START':
            state['run'] = True
        elif payload == 'STOP':
            state['run'] = False
        elif payload == 'POWEROFF':
            state['on'] = False
    return callback


def main():
    """Entry point"""
    conf = track_publish.get_config()
    # Check if the daemon is already running and if not, write pid and go on.
    pid_file = conf['global']['out_dir'] / conf['daemon']['pid_file']
    if check_already_running(pid_file):
        print(f"Process {os.getpid()} ending")
        return
    pid_file.write_text(str(os.getpid()))
    # Init cloud client, logger and tracker.
    client = track_publish.CloudIOTClient(**conf['cloud'])
    logger = track_publish.init_logger(client, conf)
    tracker = track_publish.init_tracker(logger, conf)
    # Init state dict (will update according to commands).
    state = {'on': True, 'run': False}
    client.on_message = get_state_updater(state)
    # Start the event loop.
    pos_period = conf['interval']
    tracker.logger.debug("Starting.")
    try:
        while state['on']:
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
        tracker.logger.debug("Exiting.")
        client.disconnect()
        pid_file.unlink()
        subprocess.call(['sudo', 'poweroff'])


if __name__ == "__main__":
    main()
