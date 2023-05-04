"""
Collect and save telemetry from Google Cloud Pub/Sub topics.
"""
import argparse
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from logging.handlers import QueueHandler
from pathlib import Path
from queue import Queue
from threading import Event, Thread

import yaml
from flask import Flask, Response, request, redirect, url_for
from jsonschema.exceptions import ValidationError

from trkpy.cloud import AWSClient
from trkpy.collect import CloudCollector
from trkpy.validate import validate_tracking_config


def check_config_name(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in 'json'


def get_arg_parser():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        required=True,
        help="Path to the YAML config file."
    )
    parser.add_argument(
        "--write_after",
        default=300,
        type=int,
        help="Flush logs older than this amount (in seconds). Default: 300",
    )
    return parser


def get_config():
    # Load the configuration.
    aconf, fconf_override = get_arg_parser().parse_known_args()
    with open(aconf.config, 'r') as handle:
        fconf = yaml.safe_load(handle)
    # Override file config with "--section.option val" command line arguments.
    args = iter(fconf_override)
    for name, val in zip(args, args):
        section, option = name[2:].split('.')
        fconf[section][option] = val
    # Preprocess paths to make life easier.
    for section in fconf.values():
        for key, value in section.items():
            if not isinstance(value, str):
                continue
            if "/" in value or value in (".", "..", "~"):  # UNIX path
                section[key] = Path(value)
    # Merge configs.
    conf = vars(aconf) | fconf
    # Process authentication file paths.
    auth_dir = conf['global']['auth_dir']
    for provider, cloud_conf in conf['cloud'].items():
        cloud_conf['ca_certs'] = auth_dir / provider / cloud_conf['ca_certs']
        cloud_conf['device_private_key'] = (
            auth_dir / provider / cloud_conf['device_private_key']
        )
        if 'device_cert' in cloud_conf:
            cloud_conf['device_cert'] = (
                auth_dir / provider / cloud_conf['device_cert']
            )
    return conf


def init_logger(que: Queue = None):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    # Log to the standard output.
    stream_handler = logging.StreamHandler()
    stream_formatter = logging.Formatter(
        fmt='|{asctime}|{levelname}|{name}|{funcName}|{message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    stream_handler.setFormatter(stream_formatter)
    root_logger.addHandler(stream_handler)
    # Log to the queue.
    if que is not None:
        queue_handler = QueueHandler(que)
        queue_handler.addFilter(logging.Filter("trkpy"))
        root_logger.addHandler(queue_handler)


def init_webapp(log_queue: Queue, client: AWSClient):
    app = Flask(__name__)

    @app.route("/log")
    def log_page():
        return f"""
            <!doctype html>
            <title>Log</title>
            <h1>Log</h1>
            <div id="log"></div>
            <script>
              const logDiv = document.getElementById('log');
              const eventSrc = new EventSource('{url_for("update_log")}');
              eventSrc.onmessage = e => {{
                const pre = document.createElement('pre');
                pre.innerHTML = e.data;
                logDiv.append(pre);
              }}
            </script>
            """

    @app.route("/update-log")
    def update_log():
        def event_stream():
            while True:
                if not log_queue.empty():
                    yield f"data: {log_queue.get().getMessage()}\n\n"
                time.sleep(.1)  # avoid using 100% CPU
        return Response(event_stream(), mimetype="text/event-stream")

    @app.route("/upload", methods=['GET', 'POST'])
    def upload_page():
        if request.method == 'POST':
            # Validate the config
            if 'config' not in request.files:
                app.config['ERROR_REASON'] = "Config file is missing"
                return redirect('upload-error')
            file = request.files['config']
            if not check_config_name(file.filename):
                app.config['ERROR_REASON'] = "Not a JSON file"
                return redirect('upload-error')
            config = json.loads(file.read())
            try:
                validate_tracking_config(config)
            except ValidationError as e:
                app.config['ERROR_REASON'] = e.message
                return redirect('upload-error')
            # Send the config
            device = request.form['device']
            client.publish(f"config/{device}", json.dumps(config))
            return f"""
                <!doctype html>
                <p>Config successfully sent to {device}!</p>
                <pre>{json.dumps(config, indent=4)}</pre>
                """
        return """
            <!doctype html>
            <title>Upload config file</title>
            <h1>Upload config file</h1>
            <form method=post enctype=multipart/form-data>
              <input type=file accept="application/json" name=config>
              <select name=device>
                <option value="rpi1">rpi1</option>
                <option value="rpi2">rpi2</option>
              </select>
              <input type=submit value=Upload>
            </form>
            """

    @app.route("/upload-error")
    def upload_error_page():
        return f"""
            <!doctype html>
            <title>Upload error</title>
            <h1>Upload error</h1>
            <p>Error: {app.config['ERROR_REASON']}</p>
            <p><a href="{url_for('upload_page')}">Try again</a></p>
            """

    return app


def flush_collector(
    col: CloudCollector,
    write_after: int,
    flush_every: int,
    stop_event: Event
):
    write_after = timedelta(seconds=write_after)
    while not stop_event.wait(flush_every):
        write_time = datetime.now(timezone.utc) - write_after
        col.flush(older_than=write_time)


def main():
    """Entry point."""
    que = Queue(-1)
    init_logger(que)
    conf = get_config()
    client = AWSClient(**conf['cloud']['aws'], publisher=False)
    app = init_webapp(que, client)
    out_dir = Path(conf['global']['out_dir'])
    subscriptions = ['location', 'error', 'debug']
    types = ['json', 'str', 'str']
    collector = CloudCollector(
        client,
        subscriptions,
        types,
        flush_dir=out_dir,
    )
    stop_flush_thread = Event()
    flush_thread = Thread(
        target=flush_collector,
        args=(collector, conf['write_after'], 60, stop_flush_thread),
        daemon=True
    )
    flush_thread.start()
    try:
        app.run(host="0.0.0.0")
    finally:
        stop_flush_thread.set()
        flush_thread.join()
        client.disconnect()


if __name__ == "__main__":
    main()
