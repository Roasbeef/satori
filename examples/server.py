import satori
import asyncio
import json

# Like load the static resources?
http2_options = {}
app = yield from satori.create_server(http2_settings=http2_options,
                                      port=8080)

# Handler is, itself a coroutine function.
@app.async_route('/')
def index(request, response, context):
    # Just to document some of the API.
    if request.json:
        message = request.json['greetings']

    response.headers[':status'] = 200
    response.headers['content-type'] = 'application/json'
    yield from response.end_headers()

    # Call backs for pushes instead?
    push_headers = {':path': '/img/testing.jpg'}
    push_stream = yield from response.init_push(push_headers)
    push_status = yield from push_stream.static_file(path='/img/testing.jpg', end_stream=True)  # Equiv `write_many` method? and just `write`
        # Need to handle a rejected push.
        #if push_status.exception():
        #    pass

    # Some stuff with settings priority.
    yield from response.write(json.dumps({'testing': 'is cool'}), end_stream=True)

asyncio.get_event_loop().run_until_complete(app)
asyncio.get_event_loop().run_forever()
