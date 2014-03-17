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
    print("CLIENT HAS ALL THE DATA")
    print(resp.status_code)

    # Task to send out what was read, can be iterated over.
    print("Client has response: ", (yield from resp.read_body()))

    print('TRYING BATCH REQUEST')
    requests = [asyncio.Task(conn.request('GET', '/')) for _ in range(10)]
    for response_future in asyncio.as_completed(requests):
        print('RESP HAS BEEN COMPLETED')
        completed_resp = yield from response_future
        print("Client has batch response: ", (yield from completed_resp.read_body()))

asyncio.get_event_loop().run_until_complete(client_example())
