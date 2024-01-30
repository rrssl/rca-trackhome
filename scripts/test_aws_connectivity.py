"""Script to check whether the AWS server is reachable."""
import platform    # For getting the operating system name
import subprocess  # For executing a shell command
import tkinter as tk
from tkinter.scrolledtext import ScrolledText


def update_process_output(window, process, text_area):
    text_area.configure(state='normal')
    try:
        line = next(process.stdout).decode('utf8')
        text_area.insert(tk.INSERT, line)
    except StopIteration:
        pass
    text_area.configure(state='disabled')
    window.after(10, update_process_output, window, process, text_area)


def main():
    window = tk.Tk()
    window.title("AWS Connectivity test")

    header = tk.Label(text="This is a test")
    header.pack()
    scroll_txt = ScrolledText(window)
    scroll_txt.configure(state='disabled')  # make the text read-only
    scroll_txt.pack()

    # Option for the number of packets as a function of
    param = "-n" if platform.system().lower() == "windows" else "-c"
    # Building the command. Ex: "ping -c 1 google.com"
    host = "8.8.8.8"
    command = ["ping", param, "3", host]
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    ) as process:
        window.after(10, update_process_output, window, process, scroll_txt)
        window.mainloop()


if __name__ == "__main__":
    main()
