from .frame import (ConnectionSetting, GoAwayFrame, WindowUpdateFrame, SettingsFrame,
                    FrameFlag, MAX_FRAME_SIZE, ConnectionSetting)
from .parser import FrameParser

import asyncio
import collections


class HTTP2CommonProtocol(asyncio.StreamReaderProtocol):

    def __init__(self, loop=None):
        # Is the neccesary?
        self._ev_loop = asyncio.get_event_loop if loop is None else loop

        super().__init__(asyncio.StreamReader(), self.stream_open, self._ev_loop)

        self._streams = {}
        self._settings = {ConnectionSetting.INITIAL_WINDOW_SIZE: 65535}

        self._frame_parser = FrameParser(self.reader)

        self._reader_task = asyncio.async(self.start_reader_task())
        self._writer_task = None

        # Make this a p-queue?
        self._outgoing_frames = async.Queue()

        self._connection_header_exchanged = asyncio.Future()
        self._connection_closed = asyncio.Future()

        self._in_flow_control_window = 65535
        self._out_flow_control_window = 65535

        self._outgoing_window_update = asyncio.Event()


    def update_settings(self, settings_frame):
        if ConnectionSetting.HEADER_TABLE_SIZE in settings_frame.settings:
            pass
        if ConnectionSetting.INITIAL_WINDOW_SIZE in settings_frame.settings:
            current_size = self._settings[ConnectionSetting.INITIAL_WINDOW_SIZE]
            updated_size = settings_frame.settings[ConnectionSetting.INITIAL_WINDOW_SIZE]
            size_diff = updated_size - current_size

            # Also loop through and update the window sizes of each of the
            # streams?
            self._settings[ConnectionSetting.INITIAL_WINDOW_SIZE] = size_diff
        if ConnectionSetting.ENABLE_PUSH in settings_frame.settings:
            pass
        if ConnectionSetting.MAX_FRAME_SIZE in settings_frame.settings:
            pass


    @asyncio.coroutines
    def handle_connection_frame(self, frame):
        if isinstance(frame, GoAwayFrame):
            # Let the reader and writer coroutines know that the connection is
            # being closed.
            yield from self.close_connection(frame)
            self._connection_closed.set_result(True)
            # TODO(roasbeef): Do something with the last stream_id
            # and the error code...
        elif isinstance(frame, WindowUpdateFrame):
            self._out_flow_control_window += frame.window_size_increment

            # Trigger some event? or something else in the sync asyncio
            # Existence of a race condition here?
            self._outgoing_window_update.set()
            self._outgoing_window_update.clear()

        elif isinstance(frame, SettingsFrame):
            # If it isn't just a settings ACK, then ya know, do something.
            if not frame.is_ack:
                # Do that something.
                self.update_settings(frame)

                # Fling over a Settings ACK frame.
                settings_ack = SettingsFrame(stream_id=0, flags={SpecialFrameFlag.ACK})
                yield from self._outgoing_frames.put(settings_ack)

            # TODO(roasbeef): Need to handle an ACK somehow?


    @asyncio.coroutine
    def write_frame(self, frame):
        # serialize frame, send it off
        yield from self._outgoing_frames.put(frame)

    @asyncio.coroutine
    def start_writer_task(self):
        yield from self._connection_header_exchanged
        # pop off the heapq
        # break larger frames into smaller chunks
        # put chunks back into the heapq?
        # need to handle a full outgoing window
        #  wait till window opens up
        while not self._connection_closed.done():
            frame, is_flow_controlled = yield from self._outgoing_frames.get()

            if is_flow_controlled:
                # Wait to be notified that we've received a window update
                # frame.
                # Hmmm, we may be waiting for a current frame that's too big,
                # while some other frames could possibly be sent? In this case,
                # should be out the current frame back into the queue, and pop
                # off a new one?
                while len(frame) > self._out_flow_control_window:
                    yield from self._outgoing_window_update.wait()

                # Reduce our outgoing window.
                self._out_flow_control_window -= len(frame)

            frame_bytes = frame.serialize()
            self.writer.write(frame_bytes)


    @asyncio.coroutine
    def start_reader_task(self):
        # Pause until the connection header has been exchanged by both sides.
        yield from self._connection_header_exchanged

        while not self._connection_closed.done():
            # Parse a single frame from the connection.
            frame, is_flow_controlled = yield from frame_parser.read_frame()

            if is_flow_controlled:
                # Let the other side know we're ready to receive more.
                asyncio.async(self.update_incoming_flow_control(len(frame)))

            # Figure out what to do with it.
            if frame.stream_id == 0:
                # Make into a task? Or call soon?
                asyncio.async(self.handle_connection_frame(frame))
            else:
                self._streams[frame.stream_id].process_frame(frame)

    @asyncio.coroutine
    def update_incoming_flow_control(increment, stream_id=0):
        window_update = WindowUpdateFrame(stream_id=stream_id,
                                          window_size_increment=increment))

        # Possibly block until there's room in the queue.
        yield from self.write_frame(window_update)

    @asyncio.coroutine
    def settings_handshake(self):
        # Server needs to wait for the 24 bytes of the client connection
        # header. Then send over the initial settings frame. Can set
        # sometimeout also, then handle it how ever.

        # Client needs to send over the 24 bytes of the client conneciton
        # header. Then also send the initla settings frame.
        raise NotImplementedError

    @asyncio.coroutine
    def close_connection(go_away_frame=None):
        # self.writer.close()
        # self.writer.write_eof()
        # some shit with futures for the running tasks.
        pass

    # Need a connection made in the server class.
    def stream_open(self, reader, writer):
        self.reader = reader
        self.writer = writer

    def connection_lost(self, exc):
        # Set the connection closed future result
        if not self._connection_closed.done():
            self._connection_closed.set_result(True)
        super().connection_lost(exc)
