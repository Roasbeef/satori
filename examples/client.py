import satori
import asyncio
import json

@asyncio.coroutine
def client_example():
    http2_settings = {}
    conn = yield from satori.connect('localhost:8080', settings=http2_settings)

    #def accept_push(stream):
    #    print(stream.ready())
    #
    #conn.on('push', accept_push)

    # Task returns a response object, as soon as we get the headers back.
    resp = yield from connection.request('GET', '/')
    print(resp.status_code)
    # Task to send out what was read, can be iterated over.
    print(yield from resp.read_body())

    requests = map(asyncio.async, [conn.get('/'), conn.get('/help'), conn.get('/test')])
    for completed_resp in asyncio.as_completed(requests):
        print(yield from completed_resp.read_body())

asyncio.get_event_loop().run_until_complete(client_example)
