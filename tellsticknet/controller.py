import socket
import logging
from datetime import datetime, timedelta
from time import time
from . import discovery
from .protocol import encode_packet, decode_packet

COMMAND_PORT = 42314
TIMEOUT = timedelta(seconds=5)
REGISTRATION_INTERVAL = timedelta(minutes=10)

_LOGGER = logging.getLogger(__name__)


def discover():
    """
    Return all found controllers on the local network
    N.b this method blocks
    """
    return (Controller(controller[0]) for controller in discovery.discover())


class Controller:

    def __init__(self, address):
        _LOGGER.debug("creating controller with address %s", address)
        self._address = address
        self._last_registration = None
        self._stop = False
        self._sensors = {}

    def stop(self):
        self._stop = True

    def _send(self, sock, command, **args):
        """Send a command to the controller
        Available commands documented in
        https://github.com/telldus/tellstick-net/blob/master/
            firmware/tellsticknet.c"""
        packet = encode_packet(command, **args)
        _LOGGER.debug("sending packet to controller %s:%d <%s>",
                      self._address, COMMAND_PORT, packet)
        sock.sendto(packet, (self._address, COMMAND_PORT))

    def send(self, sock, what):
        self._send(sock, "send")

    def _register(self, sock):
        """ register self at controller """
        _LOGGER.info("registering self as listener for device at %s",
                     self._address)
        try:
            self._send(sock, "reglistener")
            self._last_registration = datetime.now()
        except OSError:  # e.g. Network is unreachable
            # just retry
            pass

    def _registration_needed(self):
        """Register self at controller"""
        if self._last_registration is None:
            return True
        since_last_check = datetime.now() - self._last_registration
        return since_last_check > REGISTRATION_INTERVAL

    def _recv_packet(self, sock):
        """Wait for a new packet from controller"""

        if self._registration_needed():
            self._register(sock)

        try:
            response, (address, port) = sock.recvfrom(1024)
            if address != self._address:
                return
            return response.decode("ascii")
        except (socket.timeout, OSError):
            pass

    def packets(self):
        """Listen forever for network events, yield stream of packets"""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setblocking(1)
            sock.settimeout(TIMEOUT.seconds)
            _LOGGER.debug("listening for signals from %s", self._address)
            while not self._stop:
                packet = self._recv_packet(sock)
                if packet is not None:
                    yield packet

    def values(self):
        for packet in self.packets():
            if packet is None:
                continue  # timeout
            packet = decode_packet(packet, lastUpdated=int(time()))
            _LOGGER.debug("got packet %s", packet)
            sensor_id = (  # controller/client-id,
                packet["sensorId"])
            if sensor_id in self._sensors:
                self._sensors[sensor_id] = packet
                _LOGGER.debug("updated state for sensor %s", sensor_id)
                # signal state change
            else:
                self._sensors[sensor_id] = packet
                _LOGGER.info("discovered new sensor %s", sensor_id)
                # signal discovery
            _LOGGER.debug("returning packet %s", packet)
            #  from pprint import pprint
            #  pprint(self._sensors)
            yield packet

    def async_listen(self, event_callback):
        """Listen forever for network events in a separate thread"""

        def listener(self):
            for packet in self.values():
                event_callback(packet)

        from threading import Thread
        Thread(target=listener).run()
