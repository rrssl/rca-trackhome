"""Script to check whether the AWS server is reachable."""
import platform    # For getting the operating system name
import subprocess  # For executing a shell command
import tkinter as tk
from tkinter.scrolledtext import ScrolledText


def append_readonly_output(text_area, text):
    text_area.configure(state='normal')
    text_area.insert(tk.INSERT, text)
    text_area.configure(state='disabled')


def run_connectivity_test(window, input_field, output_area):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    command = ["ping", param, "3", input_field.get()]
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    ) as process:
        for line in process.stdout:
            append_readonly_output(output_area, line.decode())
        # window.after(10, update_process_output, window, process, output_area)


def main():
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
        command=lambda: run_connectivity_test(window, input_field, output_area)
    )
    action_btn.pack()
    output_area.pack()
    # Run the GUI event loop.
    window.mainloop()


if __name__ == "__main__":
    main()
