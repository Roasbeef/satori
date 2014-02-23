class ConnectionError(Exception):
    pass


class StreamError(Exception):
    pass


class SettingsTimeout(ConnectionError):
    pass


class ProtocolError(ConnectionError):
    pass


class FrameSizeError(ConnectionError):
    pass


class FlowControlError(ConnectionError):
    pass
