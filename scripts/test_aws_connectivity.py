"""Script to check whether the AWS server is reachable."""
import platform    # For getting the operating system name
import subprocess  # For executing a shell command
import tkinter as tk


def update_process_output(window, process, scrolled_text):
    try:
        scrolled_text['text'] += next(process.stdout).decode('utf8')
    except StopIteration:
        pass
    window.after(10, update_process_output, window, process, scrolled_text)


def main():
    window = tk.Tk()
    window.title("Hello World")

    scrolled_text = tk.Label(text="Hello, Tkinter\n", justify=tk.LEFT)
    scrolled_text.pack()

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
        window.after(10, update_process_output, window, process, scrolled_text)
        window.mainloop()


if __name__ == "__main__":
    main()
