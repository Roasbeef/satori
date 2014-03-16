import satori
import asyncio
import json

import logging
logger = logging.getLogger('http2')
logger.setLevel(logging.INFO)

@asyncio.coroutine
def client_example():
    http2_settings = {}
    conn = yield from satori.client.connect('localhost:8080', options=http2_settings)

    #def accept_push(stream):
    #    print(stream.ready())
    #
    #conn.on('push', accept_push)

    # Task returns a response object, as soon as we get the headers back.
    resp = yield from conn.request('GET', '/')
    print(resp.status_code)
    # Task to send out what was read, can be iterated over.
    print((yield from resp.read_body()))

    requests = map(asyncio.async, [conn.request('GET', '/'), conn.request('GET', '/')])
    for completed_resp in asyncio.as_completed(requests):
        print((yield from completed_resp.read_body()))

asyncio.get_event_loop().run_until_complete(client_example())
