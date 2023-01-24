import fcntl
import os
import socket
from pathlib import Path


def is_online(host: str = "8.8.8.8", port: int = 53, timeout: int = 3) -> bool:
    """Check if the system has a working internet connection.

    Host: 8.8.8.8 (google-public-dns-a.google.com)
    OpenPort: 53/tcp
    Service: domain (DNS/TCP)

    Source: https://stackoverflow.com/a/33117579
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


def lock_file(path: Path) -> bool:
    """Lock a file if it is not already locked.

    The lock will be released when the program exits, or can be released if
    the file pointer is closed.

    Source: https://stackoverflow.com/a/384493
    """
    lock_path = Path(path)
    # Using `os.open` ensures that the file pointer won't be closed
    # by Python's garbage collector after the function's scope is exited.
    lock_file_pointer = os.open(lock_path, os.O_WRONLY | os.O_CREAT)
    try:
        fcntl.lockf(lock_file_pointer, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except IOError:
        return False