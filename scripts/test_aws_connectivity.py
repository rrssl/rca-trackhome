"""Script to check whether the AWS server is reachable."""
import platform
import subprocess
import tkinter as tk
from collections import deque
from tkinter.scrolledtext import ScrolledText
from threading import Thread


def append_readonly_output(text_area, text):
    text_area.configure(state='normal')
    text_area.insert(tk.INSERT, text)
    text_area.configure(state='disabled')


def update_output_area(window, output_area, message_queue):
    try:
        text = message_queue.popleft()
        append_readonly_output(output_area, text)
    except IndexError:
        pass
    window.after(500, update_output_area, window, output_area, message_queue)


def run_connectivity_test(input_field, message_queue):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", param, "3", input_field.get()]
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    ) as process:
        for line in process.stdout:
            message_queue.append(line.decode())


def run_connectivity_test_thread(input_field, message_queue):
    thread = Thread(
        target=run_connectivity_test,
        args=(input_field, message_queue),
        daemon=True
    )
    thread.start()


def main():
    # Communication between threads.
    msg_queue = deque()
    # GUI
    window = tk.Tk()
    window.title("AWS Connectivity test")
    header = tk.Label(text="Enter the AWS endpoint URL:")
    header.pack()
    input_field = tk.Entry(window)
    input_field.pack()
    output_area = ScrolledText(window)
    output_area.configure(state='disabled')  # make the text read-only
    action_btn = tk.Button(
        window,
        text="Run test",
        command=lambda: run_connectivity_test_thread(input_field, msg_queue)
    )
    action_btn.pack()
    output_area.pack()
    # Run the GUI event loop.
    window.after(500, update_output_area, window, output_area, msg_queue)
    window.mainloop()


if __name__ == "__main__":
    main()
