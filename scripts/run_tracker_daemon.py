"""This scripts allows to remotely start/stop tracking and poweroff."""
import json
import os
import subprocess
import time
from multiprocessing.connection import Client, Listener
from threading import Thread

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


def get_cloud_callback(state, addr_out):
    def callback(unused_client, unused_userdata, message):
        cmd = str(message.payload.decode('utf-8'))
        update_state(cmd, state, addr_out)
    return callback


def run_hard_in(src_address, state, addr_out):
    with Listener(src_address) as listener:
        # The Listener is bound to the address, so clients can connect.
        with Client(addr_out) as hard_out:
            hard_out.send("LISTENING")
        with listener.accept() as conn:  # blocking
            while state['on']:
                cmd = conn.recv()  # blocking
                update_state(cmd, state, addr_out)


def run_track_loop(tracker, state, addr_out, conf, ppid):
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
        with Client(addr_out) as hard_out:
            hard_out.send(('G1', True))  # on when tracking
        if state['run']:
            tracker.loop()
        else:
            tracker.loop(check_only=True)
        with Client(addr_out) as hard_out:
            hard_out.send(('G1', False))
        t_elapsed = time.time() - t_start
        time.sleep(max(0, pos_period - t_elapsed))


def update_state(cmd, state, addr_out):
    if cmd[0] == "{":
        state['conf'] = cmd
    elif cmd == "START":
        state['run'] = True
    elif cmd == "STOP":
        state['run'] = False
    elif cmd == "TOGGLE":
        state['run'] = not state['run']
    elif cmd == "POWEROFF":
        state['run'] = False
        state['on'] = False
    # Signal state change to HAT manager.
    with Client(addr_out) as hard_out:
        hard_out.send(('O1', not state['run']))
        if cmd == "POWEROFF":
            hard_out.send("POWEROFF")


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
    # Init state dict (will update according to commands).
    state = {'on': True, 'run': False, 'conf': None}
    # Init hardware input connection.
    address_out = ("localhost", 8888)
    address_in = ("localhost", 8889)
    hard_in_thread = Thread(
        target=run_hard_in,
        args=(address_in, state, address_out),
        daemon=True
    )
    hard_in_thread.start()
    # Init cloud client.
    client = AWSClient(**conf['cloud']['aws'])
    client._client.on_message = get_cloud_callback(state, address_out)
    # Init logger.
    logger = track_publish.init_logger(client, conf)
    while not client.connected:
        time.sleep(1)
    # Init tracker.
    tracker = track_publish.init_tracker(logger, conf)
    # Start the event loop.
    update_state("STOP", state, address_out)  # tracking starts paused
    tracker.logger.debug(f"Ready ({pid=}).")
    poweroff_on_exit = True
    try:
        run_track_loop(tracker, state, address_out, conf, pid)
    except KeyboardInterrupt:
        poweroff_on_exit = False
        update_state("POWEROFF", state, address_out)
    finally:
        hard_in_thread.join()
        tracker.logger.debug(f"Exiting ({pid=}).")
        client.disconnect()
        if poweroff_on_exit:
            subprocess.run('poweroff')


if __name__ == "__main__":
    main()
