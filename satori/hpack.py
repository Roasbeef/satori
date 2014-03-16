# Copyright (c) 2012-2013, Canon Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted only for the purpose of developing standards
# within the HTTPbis WG and for testing and promoting such standards within the
# IETF Standards Process. The following conditions are required to be met:
# - Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# - Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# - Neither the name of Canon Inc. nor the names of its contributors may be
#   used to endorse or promote products derived from this software without
#   specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY CANON INC. AND ITS CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL CANON INC. AND ITS CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from struct import pack, unpack
from .huffman import *
class HeaderEntry(object):
  """
  Object representing an entry in the header table.
  """
  def __init__(self, header, referenced=False, emitted=False):
    self.header = header
    self.age = 0
    self.referenced = referenced
    self.emitted = emitted

INDEXED               = 1
LITERAL_NOT_INDEXED   = 2
LITERAL_INCREMENTAL   = 3


class HTTP2Codec(object):
  """
  Codec implementing HTTP2 format.
  """
  def __init__(self,
    buffer_size=4096):
    """Initialize the codec object."""
    self.max_encoder_size = buffer_size
    self.max_decoder_size = buffer_size
    self.huffman_decoder = HuffmanDecoder()
    self.huffman_encoder = HuffmanEncoder()

    self.init_codec()

  def init_codec(self):
    """Initialize the codec."""
    # Encoder side variables.
    self.encoder_table = []
    self.encoder_table_size = 0
    # Decoder side variables.
    self.decoder_table = []
    self.decoder_table_size = 0

  def entry_len(self, entry):
    """Compute the length of an entry."""
    name, value = entry
    return len(name) + len(value) + 32
  def change_max_size(self,new_size):
    self.max_encoder_size = buffer_size
    self.max_decoder_size = buffer_size
    while (self.decoder_table_size > self.max_decoder_size and self.last_decoder_table_index() != -1):
        removed = self.decoder_table.pop(self.last_decoder_table_index())
        self.decoder_table_size -= self.entry_len(removed.header)

    while (self.encoder_table_size > self.max_encoder_size and self.last_encoder_table_index() != -1):
        removed = self.encoder_table.pop(self.last_encoder_table_index())
        self.encoder_table_size -= self.entry_len(removed.header)

  ############################################################
  # Decoder functions
  ############################################################
  def last_decoder_table_index(self):
    if self.decoder_table is not None:
      return len(self.decoder_table) - 1
    return -1

  def get_decoder_index_space_entry(self,index):
    """indices between 1 and len(header_table), inclusive refer to entries in the header table"""
    if 1 <= index <= len(self.decoder_table):
      return self.decoder_table[index-1]
    elif len(self.decoder_table) + 1 <= index:
      return HeaderEntry(STATIC_TABLE[index-len(self.decoder_table)-1],referenced=False, emitted=False)

  def prepend_decoded_header(self, entry):
    """Add a new entry to the beginning of the decoder header table."""
    size = self.entry_len(entry.header)
    dropped_number = 0

    while (self.decoder_table_size + size > self.max_decoder_size and self.last_decoder_table_index() != -1):
        removed = self.decoder_table.pop(self.last_decoder_table_index())
        self.decoder_table_size -= self.entry_len(removed.header)
        dropped_number += 1

    if self.decoder_table_size + size <= self.max_decoder_size:
      self.decoder_table.insert(0,entry)
      self.decoder_table_size += size

    return dropped_number


  def decode_headers(self, stream):
    self.decoded_stream = stream
    self.decoded_stream_index = 0

    # Initialize variables.
    headers = []
    for entry in self.decoder_table:
      entry.emitted = False

    # Decode the headers.
    stream_length = len(self.decoded_stream)
    while self.decoded_stream_index < stream_length:
      byte = self.read_next_byte()

      # Indexed header.
      if byte & 0x80:
        index = self.read_integer(byte, 7)
        if index == 0:
            for entry in self.decoder_table:
                entry.referenced = false
            for entry in self.encoder_table:
                entry.referenced = false
        else:
            entry = self.get_decoder_index_space_entry(index)
            # Check if this is a deletion.
            if entry.referenced:
                entry.referenced = False
                entry.emitted = False
            # Otherwise, this is an addition.
            else:
                entry.referenced = True
                entry.emitted = True
                headers.append(entry.header)

      # Literal
      else:
        if byte & 0xC0 == 0x40:
          mode = LITERAL_NOT_INDEXED
          name_index = self.read_integer(byte, 6)
        elif byte & 0xC0 == 0X00:
          mode = LITERAL_INCREMENTAL
          name_index = self.read_integer(byte, 6)

        # Decode header.
        if name_index == 0:
          name = self.read_literal_string()
        else:
          name = self.get_decoder_index_space_entry(name_index).header[0]
        value = self.read_literal_string()

        # Update header table and working set.
        if mode == LITERAL_INCREMENTAL:
          self.prepend_decoded_header(HeaderEntry((name, value), referenced=True, emitted=True))
        headers.append((name, value))

    # Emit remaining headers.
    for entry in self.decoder_table:
      if entry.referenced and not entry.emitted:
        headers.append(entry.header)

    return dict(headers)

  def read_next_byte(self):
    """Read a byte from the encoded stream."""
    (byte, ) = unpack("!B", self.decoded_stream[self.decoded_stream_index:self.decoded_stream_index + 1])
    self.decoded_stream_index += 1
    return byte

  def read_integer(self, byte, prefix_size):
    """Decode an integer value."""
    if prefix_size <= 8:
      value = byte & MAX_VALUES[prefix_size]
    else:
      value = byte & MAX_VALUES[prefix_size-8]
      b = self.read_next_byte()
      value = (value << 8) | (b)

    if value == MAX_VALUES[prefix_size]:
      b = self.read_next_byte()
      shift = 0
      while b & 0x80 > 0:
        value += (b & 0x7f) << shift
        shift += 7
        b = self.read_next_byte()
      value += (b & 0x7f) << shift

    return value

  def read_literal_string(self):
    """Decode a literal string."""
    value = ''
    byte = self.read_next_byte()
    length = self.read_integer(byte,7)
    if byte & 0x80:
      i = 0
      self.huffman_decoder.begin_decoding()
      last_path = None
      while i < length:
        if last_path is None or last_path == '':
          byte = self.read_next_byte()
          result_set = self.huffman_decoder.traverse_tree(byte,8)
        else:
          result_set = self.huffman_decoder.traverse_tree(last_path)
        if result_set[0] is not None:
          if result_set[0] != '':
            i +=  1
            value = value + result_set[0]
            self.huffman_decoder.begin_decoding()
        last_path = result_set[1]
    else:
      value = self.decoded_stream[self.decoded_stream_index:self.decoded_stream_index + length]
      self.decoded_stream_index += length
    return value

  ############################################################
  # Encoder functions
  ############################################################
  def last_encoder_table_index(self):
    if self.encoder_table is not None:
      return len(self.encoder_table) - 1
    return -1

  def end_encoder_table_index(self):
    if self.encoder_table is not None:
      return len(self.encoder_table)
    return 0

  def get_encoder_index_space_entry(self,index):
    if 1 <= index <= len(self.encoder_table):
      return self.encoder_table[index-1]
    elif len(self.encoder_table) + 1 <= index:
      return HeaderEntry(STATIC_TABLE[index-1-len(self.encoder_table)])

  def get_encoder_index_space_header(self,index):
    if 1 <= index <= len(self.encoder_table):
      return self.encoder_table[index-1].header
    elif len(self.encoder_table) + 1 <= index:
      return STATIC_TABLE[index-1-len(self.encoder_table)]


  def last_of_encoder_index_space(self):
    return len(self.encoder_table) + len(STATIC_TABLE)
  def end_of_encoder_index_space(self):
    return len(self.encoder_table) + len(STATIC_TABLE) + 1

  def find_header(self, header):
    for index in range(1,self.end_of_encoder_index_space()):
      if header == self.get_encoder_index_space_header(index):
        return index
    return -1

  def find_header_name(self, header):
    name, _ = header
    for index in range(1,self.end_of_encoder_index_space()):
      if name == self.get_encoder_index_space_header(index)[0]:
        return index
    return -1

  def update_encoder_table(self):
    """Update the encoder table, depending on its length."""
    for entry in self.encoder_table:
      if not entry.referenced:
        entry.age += 1
      else:
        entry.age = 0
      entry.emitted = False

  def compute_diff(self, headers):
    """
    Compute the difference with the previous header set.

    Returns:
      - headers removed from reference set,
      - headers kept in reference set,
      - headers not in reference set.
    """
    removed_headers = []
    referenced_headers = []
    remaining_headers = []

    for entry in self.encoder_table:
      entry.emitted = False

    # Mark entries in reference set, keep entries not in reference set.
    for header in headers:
      index = self.find_header(header)
      if index == -1 or index-1 > self.last_encoder_table_index():
        remaining_headers.append(header)
      else:
        entry = self.encoder_table[index-1]
        if entry.referenced:
          entry.emitted = True
          referenced_headers.append(header)
        else:
          remaining_headers.append(header)

    # Find entries from reference set not in header set (those not marked).
    for index in range(0,self.end_encoder_table_index()):
      entry = self.encoder_table[index]
      if entry.referenced:
        if not entry.emitted:
          removed_headers.append(index+1)
        else:
          entry.emitted = False

    return removed_headers, referenced_headers, remaining_headers

  def prepend_encoded_header(self, entry):
    size = self.entry_len(entry.header)

    while (self.encoder_table_size + size > self.max_encoder_size and self.encoder_table):
      removed = self.encoder_table.pop(self.last_encoder_table_index())
      self.encoder_table_size -= self.entry_len(removed.header)
      removed.referenced = False
      removed.emitted = False
    if self.encoder_table_size + size <= self.max_encoder_size:
      self.encoder_table.insert(0,entry)
      self.encoder_table_size += size

  def determine_representation(self, header):
    """Determine the best representation for a header."""
    # Find if header is in table.
    index = self.find_header(header)
    if index != -1:
      return INDEXED, index

    # Some headers are not indexed.
    if header[0] == ":path":
      return LITERAL_NOT_INDEXED, None

    # Otherwise always add incrementally.
    return LITERAL_INCREMENTAL, None

  def encode_header(self, header):
    """Encode one header."""
    type, index = self.determine_representation(header)
    name_index = self.find_header_name(header)


    # Indexed.
    if type == INDEXED:
      reference = self.get_encoder_index_space_entry(index)
      if not reference.referenced:
        self.write_integer(0x80, 7, index)
      reference.referenced = True
      reference.emitted = True

    # Literal, no indexing.
    elif type == LITERAL_NOT_INDEXED:
      if name_index >= 1:
        self.write_integer(0x40, 6, name_index)
      elif name_index == -1:
        self.write_integer(0x40, 6, 0)
        self.write_literal_string(header[0],True)
      self.write_literal_string(header[1],True)

    # Literal, incremental indexing.
    elif type == LITERAL_INCREMENTAL:
      if name_index == -1:
        self.write_integer(0x00, 6, 0)
        self.write_literal_string(header[0], True)
        self.write_literal_string(header[1], True)
      else:
        self.write_integer(0x00, 6, name_index)
        self.write_literal_string(header[1], True)

      # Update table.
      self.prepend_encoded_header(HeaderEntry(header, referenced=True, emitted=True))
    else:
      pass

  def encode_headers(self, dict_headers):
    """Encode a set of headers."""
    headers = dict_headers.items()
    # Compute diff with reference set.
    removed_headers, referenced_headers, remaining_headers = self.compute_diff(headers)

    # Update header table.
    self.update_encoder_table()

    # Initialize the encoded stream
    self.encoded_stream = bytearray()

    # Encode the removed headers
    for index in removed_headers:
      self.write_integer(0x80, 7, index)
      entry = self.encoder_table[index-1]
      entry.referenced = False
      entry.emitted = False

    # Encode the headers
    for header in remaining_headers:
      self.encode_header(header)

    # Check that referenced headers were not evicted.
    encoded_headers = True
    while referenced_headers and encoded_headers:
      encoded_headers = False
      remaining_headers = []
      for header in referenced_headers:
        if self.find_header(header) == -1:
          self.encode_header(header)
          encoded_headers = True
        else:
          remaining_headers.append(header)
    return self.encoded_stream

  def write_integer(self, byte, prefix_size, value):
    """Encoding an integer."""
    if value < MAX_VALUES[prefix_size]:
      if prefix_size <= 8:
        byte = byte + value
        self.encoded_stream += pack("!B", byte)
      else:
        byte = byte | (value >> 8)
        byte = (byte << 8) | (value & 0xFF)
        self.encoded_stream += pack("!H", byte)
    else:
      if prefix_size > 0:
        byte = byte + MAX_VALUES[prefix_size]
        self.encoded_stream += pack("!B", byte)
      value -= MAX_VALUES[prefix_size]
      if value == 0:
        self.encoded_stream += pack("!B", 0)
      while value > 0:
        q = value >> 7
        if q > 0:
          byte = 0x80
        else:
          byte = 0
        self.encoded_stream += pack("!B", byte | (value & 0x7F))
        value = q

  def write_literal_string(self, value, huffman = None):
    if huffman is None or huffman == False:
      self.write_integer(0x00, 7, len(value))
      for char in value:
        self.encoded_stream.append(ord(char))
    else:
      self.write_integer(0x80,7,len(value))
      encoded_data = self.huffman_encoder.encode_string(value)
      encoded_byte_array = bytearray(encoded_data[0])
      self.encoded_stream = self.encoded_stream + encoded_byte_array


#===============================================================================
# Predefined headers
#===============================================================================
STATIC_TABLE = [
    (":authority",""),
    (":method","GET"),
    (":method","POST"),
    (":path","/"),
    (":path","/index.html"),
    (":scheme","http"),
    (":scheme","https"),
    (":status","200"),
    (":status","500"),
    (":status","404"),
    (":status","403"),
    (":status","400"),
    (":status","401"),
    ("accept-charset",""),
    ("accept-encoding",""),
    ("accept-language",""),
    ("accept-ranges",""),
    ("accept",""),
    ("access-control-allow-origin",""),
    ("age",""),
    ("allow",""),
    ("authorization",""),
    ("cache-control",""),
    ("content-disposition",""),
    ("content-encoding",""),
    ("content-language",""),
    ("content-length",""),
    ("content-location",""),
    ("content-range",""),
    ("content-type",""),
    ("cookie",""),
    ("date",""),
    ("etag",""),
    ("expect",""),
    ("expires",""),
    ("from",""),
    ("host",""),
    ("if-match",""),
    ("if-modified-since",""),
    ("if-none-match",""),
    ("if-range",""),
    ("if-unmodified-since",""),
    ("last-modified",""),
    ("link",""),
    ("location",""),
    ("max-forwards",""),
    ("proxy-authenticate",""),
    ("proxy-authorization",""),
    ("range",""),
    ("referer",""),
    ("refresh",""),
    ("retry-after",""),
    ("server",""),
    ("set-cookie",""),
    ("strict-transport-security",""),
    ("transfer-encoding",""),
    ("user-agent",""),
    ("vary",""),
    ("via",""),
    ("www-authenticate","")
    ]
STATIC_TABLE_LEN = len(STATIC_TABLE)
MAX_VALUES = {
  0 : 0x00,
  1 : 0x01,
  2 : 0x03,
  3 : 0x07,
  4 : 0x0f,
  5 : 0x1f,
  6 : 0x3f,
  7 : 0x7f,
  8 : 0xff,
  14: 0x3fff}

# vim:et:sw=2:tw=78
