D = {}
H2 = HTTP2Codec()
D[':method'] = 'GET'
D[':scheme'] = 'http'
D[':path'] ='/'
D[':authority'] = 'www.example.com'
H2.encode_headers(D)
