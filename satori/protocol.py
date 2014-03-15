from .frame import (ConnectionSetting, GoAwayFrame, WindowUpdateFrame, SettingsFrame,
                    FrameFlag, MAX_FRAME_SIZE, SpecialFrameFlag)
from .parser import FrameParser
from .stream import Stream
from .hpack import HTTP2Codec
from .stream import MAX_STREAM_ID
from .exceptions import ProtocolError

import asyncio
import collections


class ConnectionSetting(Enum):
    HEADER_TABLE_SIZE = 0x01
    ENABLE_PUSH = 0x02
    MAX_CONCURRENT_STREAMS = 0x03
    INITIAL_WINDOW_SIZE = 0x04


def stream_id_generator(is_client):
    # TODO(roasbeef): When we support the HTTP 1.1 UPGRADE, then the sever must
    # start with stream_id=3, because the initial response to that request must
    # have stream_id of 1.
    stream_id = 2 if is_client else 3
    while True:
        # TODO(roasbeef): Also need to make sure that the stream ID's are
        # monotonically increasing.
        if stream_id > MAX_STREAM_ID:
            raise ProtocolError
        else:
            yield stream_id
            stream_id += 2


class HTTP2CommonProtocol(asyncio.StreamReaderProtocol):

    def __init__(self, is_client, loop=None):
        # Is the neccesary?
        self._ev_loop = asyncio.get_event_loop if loop is None else loop

        super().__init__(asyncio.StreamReader(), self.stream_open, self._ev_loop)

        self.__is_client = is_client

        self._stream_gen = stream_id_generator(self.__is_client)
        self._last_stream_id = None

        self._streams = {}
        self._settings = {ConnectionSetting.INITIAL_WINDOW_SIZE: 65535}

        self._frame_parser = FrameParser(self.reader)

        self._reader_task = asyncio.async(self.start_reader_task())
        self._writer_task = asyncio.asyncio(self.start_writer_task())

        # Make this a p-queue?
        self._outgoing_frames = asyncio.Queue()

        self._connection_header_exchanged = asyncio.Future()
        self._connection_closed = asyncio.Future()

        self._in_flow_control_window = 65535
        self._out_flow_control_window = 65535

        self._outgoing_window_update = asyncio.Event()

        self._header_codec = HTTP2Codec()


    def _get_next_stream_id(self):
        try:
            next_stream_id = next(self._stream_gen)
            self._last_stream_id = next_stream_id
        except ProtocolError:
            # TODO(roasbeef): Need to send a GOAWAY frame to the other side
            pass

        return next_stream_id

    def _new_stream(self, stream_id=None):
        new_stream_id = self.get_next_stream_id() if stream_id is None else stream_id
        stream = Stream(new_stream_id, self, self._header_codec)

        stream._outgoing_flow_control_window = self._settings[ConnectionSetting.INITIAL_WINDOW_SIZE]

        self._streams[new_stream_id] = stream
        return stream

    def update_settings(self, settings_frame):
        if ConnectionSetting.HEADER_TABLE_SIZE in settings_frame.settings:
            # TODO(metehan): Handle this.
            pass
        if ConnectionSetting.INITIAL_WINDOW_SIZE in settings_frame.settings:
            current_size = self._settings[ConnectionSetting.INITIAL_WINDOW_SIZE]
            updated_size = settings_frame.settings[ConnectionSetting.INITIAL_WINDOW_SIZE]
            size_diff = updated_size - current_size

            self._update_flow_control_all_streams(size_update)

            self._settings[ConnectionSetting.INITIAL_WINDOW_SIZE] = size_diff
        if ConnectionSetting.ENABLE_PUSH in settings_frame.settings:
            pass
        if ConnectionSetting.MAX_CONCURRENT_STREAMS in settings_frame.settings:
            pass

    def _update_flow_control_all_streams(size_update):
        for stream in self._streams.values():
            stream._out_flow_control_window += size_update

            # Notify any tasks that we've received a window update.
            stream._outgoing_window_update.set()
            stream._outgoing_window_update.clear()

    @asyncio.coroutines
    def handle_connection_frame(self, frame):
        if isinstance(frame, PingFrame):
            pong_frame = frame.pong_from_ping(frame)
            yield from self.write_frame(pong_frame)
        elif isinstance(frame, RstStreamFrame):
            pass
        elif isinstance(frame, GoAwayFrame):
            # Let the reader and writer coroutines know that the connection is
            # being closed.
            yield from self.close_connection(frame)
            self._connection_closed.set_result(True)
            # TODO(roasbeef): Do something with the last stream_id
            # and the error code...
        elif isinstance(frame, WindowUpdateFrame):
            # Window update frame for the entire connection, let all the
            # streams know they can send sum mo'.
            self._out_flow_control_window += frame.window_size_increment

            self._outgoing_window_update.set()
            self._outgoing_window_update.clear()

            self._update_flow_control_all_streams(frame.window_size_increment)
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
        yield from self._outgoing_frames.put(frame)

    @asyncio.coroutine
    def start_writer_task(self):
        yield from self._connection_header_exchanged
        # pop off the heapq
        # break larger frames into smaller chunks
        # put chunks back into the heapq?
        # need to handle a full outgoing window
        # wait till window opens up
        while not self._connection_closed.done():
            # Need to recognize outgoing PushPromises and make a spot for the
            # future stream
            frame = yield from self._outgoing_frames.get()

            if isinstance(frame, PushPromise):
                # Locally create and reserve the promised frame.
                promised_stream = self._new_stream(stream_id=frame.promised_stream_id)
                promised_stream.state = StreamState.RESERVED_LOCAL
                self._streams[frame.promised_stream_id] = promised_stream

                # Let the stream wish is promising a new stream know that it is
                # available.
                self._streams[frame.stream_id].receive_promised_stream(promised_stream)

            # Abstract a lot of this to a 'writer' class, just as the reader.
            # Also the heapq logic into a 'PriorityFrame' class.
            if isinstance(frame, DataFrame):
                # Wait to be notified that we've received a window update
                # frame.
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

        # Can also set a value to the connection closed future, like the last
        # frame that was processed or the reason we're closing the connection?
        while not self._connection_closed.done():
            # Parse a single frame from the connection.
            frame = yield from frame_parser.read_frame()

            # Figure out what to do with it.
            if frame.stream_id == 0:
                # Make into a task? Or call soon?
                asyncio.async(self.handle_connection_frame(frame))
            elif frame.stream_id in self._streams:
                self._streams[frame.stream_id].process_frame(frame)
            # should be a new headers frame at this point.
            elif not self.__client:
                # It's either gonna be a PushPromise frame or HeadersFrame
                # Should my client also support PushPromises?
                # Otherwise, this path will only be entered if this is being
                # run on a sever side?
                pass
                # Check if it's a headers frame, create new stream
                # Also look for a end headers, if so, create a task to process the
                # frame.
                # asyncio.async(stream.consume_request())
                # add a done call back on the task to close the connection?

    @asyncio.coroutine
    def update_incoming_flow_control(increment, stream_id=0):
        window_update = WindowUpdateFrame(stream_id=stream_id,
                                          window_size_increment=increment)

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
