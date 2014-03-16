import satori
import asyncio
import json
import sys

import logging
logger = logging.getLogger('http2')
logger.setLevel(logging.INFO)
if not logger.handlers:
    out_hdlr = logging.StreamHandler(sys.stdout)
    out_hdlr.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    out_hdlr.setLevel(logging.INFO)
    logger.addHandler(out_hdlr)


# Handler is, itself a coroutine function.
@asyncio.coroutine
def index(request, response, context):
    # Just to document some of the API.
    #if request.json:
    #    message = request.json['greetings']

    response.headers[':status'] = 200
    response.headers['content-type'] = 'application/json'
    yield from response.end_headers()

    # Call backs for pushes instead?
    #push_headers = {':path': '/img/testing.jpg'}
    #push_stream = yield from response.init_push(push_headers)
    #push_status = yield from push_stream.static_file(path='/img/testing.jpg', end_stream=True)  # Equiv `write_many` method? and just `write`
        # Need to handle a rejected push.
        #if push_status.exception():
        #    pass

    # Some stuff with settings priority.
    yield from response.write(json.dumps({'testing': 'is cool'}), end_stream=True)

# Like load the static resources?
http2_options = {}
app = satori.server.serve(index, http2_options, 8080)

logger.info('Server created')
asyncio.get_event_loop().run_until_complete(app)
logger.info('Server running?')
asyncio.get_event_loop().run_forever()
logger.info('still Server running?')
