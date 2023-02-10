"""Check whether systemd's poweroff can be called from python."""
import asyncio
import logging

from dbus_next.aio import MessageBus
from dbus_next import BusType


def init_logger():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_formatter = logging.Formatter(
        fmt='|{asctime}|{levelname}|{name}|{funcName}|{message}',
        datefmt='%Y-%m-%d %H:%M:%S',
        style='{'
    )
    stream_handler.setFormatter(stream_formatter)
    root_logger.addHandler(stream_handler)


async def amain():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    bus_name = "org.freedesktop.login1"
    path = "/org/freedesktop/login1"
    iface = "org.freedesktop.login1.Manager"
    introspection = await bus.introspect(bus_name, path)
    proxy_object = bus.get_proxy_object(bus_name, path, introspection)
    interface = proxy_object.get_interface(iface)
    res = await interface.call_can_power_off()
    logging.info(res)


def main():
    init_logger()
    asyncio.run(amain())


if __name__ == "__main__":
    main()
