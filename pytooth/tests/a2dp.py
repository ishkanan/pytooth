"""Defines a test application for A2DP."""

import logging

from tornado.ioloop import IOLoop

import pytooth
from pytooth.a2dp import AdvancedAudioProfile
from pytooth.a2dp.sbc import SBCDecoder
from pytooth.a2dp.sinks import AlsaAudioSink
from pytooth.adapters import OpenPairableAdapter

logger = logging.getLogger(__name__)


class TestApplication:
    """Test application for the A2DP profile. The logic of this code is suitable
    for use in a real-world application.
    """

    def __init__(self, session_bus, system_bus, config):
        self.sink = None

        # profile setup
        a2dp = AdvancedAudioProfile(
            system_bus=system_bus,
            adapter_class=OpenPairableAdapter,
            preferred_address=config["preferredaddress"],
            retry_interval=config["retryinterval"],
            io_loop=IOLoop.current())
        a2dp.on_adapter_connected_changed = self._adapter_connected_changed
        a2dp.on_audio_setup_error = self._audio_setup_error
        a2dp.on_audio_stream_state_changed = self._audio_stream_state_changed
        a2dp.on_audio_track_changed = self._audio_track_changed
        a2dp.on_device_connected_changed = self._device_connected_changed
        a2dp.on_profile_status_changed = self._profile_status_changed
        self.a2dp = a2dp

    def start(self):
        # let's go
        self.a2dp.start()

    def stop(self):
        # cleanup
        if self.a2dp.adapter_connected:
            self.a2dp.set_discoverable(enabled=False)
            self.a2dp.set_pairable(enabled=False)
        self.a2dp.stop()
        self._stop_audio()

    def _adapter_connected_changed(self, adapter, connected):
        logger.debug("Adapter {} is now {}.".format(
            adapter, "connected" if connected else "disconnected"))

        # be discoverable and pairable if adapter is connected
        # note: it is an error to call this if no adapter is avilable
        if connected:
            self.a2dp.set_discoverable(enabled=True)
            self.a2dp.set_pairable(enabled=True)

    def _audio_setup_error(self, adapter, error):
        """Fired if an audio link could not be established. This higher-level
        class doesn't have to do anything to cleanup the connection(s) or audio
        paths.
        """
        logger.error("Cannot establish audio link on adapter {} - {}".format(
            adapter, error))

    def _audio_stream_state_changed(self, adapter, transport, state):
        """Fired when the audio stream state changes. There is no explicit
        connected/disconnected as it is more suitable to simply react off the
        status rather than a binary flag.
        """
        if state == "playing" and self.sink is None:
            self._start_audio(transport=transport)
        elif state == "released" and self.sink:
            self._stop_audio()

    def _audio_track_changed(self, track):
        logger.info("Track changed - {}".format(track))
        
    def _device_connected_changed(self, device, connected):
        """Fired when a device connects but has not completed initial handshake
        with the protocol.
        """
        logger.info("Device {} has {}connected.".format(
            device, "" if connected else "not "))

    def _profile_status_changed(self, available):
        """Fired when the profile is enabled/disabled at the Bluez5 level. This
        really only occurs if a serious issue with the Bluetooth stack is
        encountered by the OS.
        """
        logger.info("A2DP profile is {}avaiable.".format(
            "" if avaiable else "not "))

    def _start_audio(self, transport=None):
        # streaming has started, obviously

        self.sink = AlsaAudioSink(
            decoder=SBCDecoder(
                libsbc_so_file="/usr/lib/x86_64-linux-gnu/libsbc.so.1.2.2"),
            socket=transport.socket,
            read_mtu=transport.read_mtu,
            device_name="default")
        self.sink.start()
        logger.info("Built new AlsaAudioSink with SBCDecoder.")

    def _stop_audio(self):
        # no more streaming, obviously

        if self.sink:
            self.sink.stop()
            self.sink = None
            logger.info("Destroyed AlsaAudioSink.")
