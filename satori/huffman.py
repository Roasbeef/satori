import binascii

def conBitStrings(first_string, second_string):
    if len(first_string) == 0:
        return second_string
    else:
        return '0b'+first_string[2:]+ second_string[2:]

def binstring2hex(bin_string):
    if bin_string[0:2] != '0b':
        new_string = bin_string
    else:
        new_string = bin_string[2:]
    return int(new_string,2),len(new_string)

def pad_binstring(bin_string,bit_len):
    bin_string = bin_string[2:]
    return max(0,bit_len - len(bin_string))*'0' + bin_string

def pad_number_with(num,num_len,pad_with):
    padlen = 8 - (num_len%8)
    final_num = num
    if padlen != 8:
        final_num <<= padlen
        if pad_with == 1:
            final_num |= (1 <<(padlen))-1
        return final_num, padlen
    else:
        return final_num, 0



class Node(object):        
    def __init__(self, data):
        i = 0;
        self.data = data
        self.branches = {}
        if data is not None:
            self.isLeaf = True
        else:
            self.isLeaf = False
            
class HuffmanDecoder(object):
    def __init__(self):
        self.root = Node(None)
        self.current_node = self.root
        i = 0
        for entry in HUFFMAN_CODES:
            bin_string = pad_binstring(bin(entry[0]),entry[1])
            self.insert_node(bin_string,chr(i))
            i = i + 1

    def insert_node(self, bin_string, char):
        current_node = self.root
        for my_char in bin_string:
            if my_char not in current_node.branches:
                    current_node.branches[my_char] = Node(None)
            current_node = current_node.branches[my_char]
        if char is None or len(char) == 0:
            current_node.isLeaf = False
        else:
            current_node.isLeaf = True
        current_node.data = char

    def begin_decoding(self):
        self.current_node = self.root
        
    def traverse_tree(self, data, hex_data_len = None):
        if hex_data_len is not None:
            bin_string = bin(data)[2:]
            while len(bin_string) < hex_data_len:
                bin_string ='0'+bin_string
            while len(bin_string) > hex_data_len:
                bin_string = bin_string[1:]
        elif data[0:2] == '0b':
            bin_string = data[2:]
        else:
            bin_string = data
            

        i = 0
        for char in bin_string:
            self.current_node = self.current_node.branches[char]
            i = i + 1
            if self.current_node.isLeaf == True:
                return self.current_node.data,bin_string[i:]
        return None, None
            
        
    
class HuffmanEncoder(object):
    def __init__(self):
        self.myDict = {}
        i = 0
        for entry in HUFFMAN_CODES:
            self.myDict[chr(i)] = entry
            i += 1
            
    def encode_string(self, string):
        binString = ''
        binStringLen = 0;
        out_num = 0;
        out_num_len  = 0;
        for letter in string:
            codes = self.myDict[letter]
            my_num_len = codes[1]
            my_num = codes[0] & ((2**(my_num_len+1) - 1))
            out_num <<= my_num_len
            out_num |= my_num
            out_num_len += my_num_len
        out_num,inc_num_len = pad_number_with(out_num, out_num_len,1)
        out_num_len += inc_num_len
        out_num_str_fin = hex(out_num)
        out_num_str = out_num_str_fin[2:]

        if len(out_num_str)%2 != 0:
            out_num_str = '0'+out_num_str
        return bytes.fromhex(out_num_str), out_num_str_fin
        
            

HUFFMAN_CODES = [
    (0x7ffffba, 27),
    (0x7ffffbb, 27),
    (0x7ffffbc, 27),
    (0x7ffffbd, 27),
    (0x7ffffbe, 27),
    (0x7ffffbf, 27),
    (0x7ffffc0, 27),
    (0x7ffffc1, 27),
    (0x7ffffc2, 27),
    (0x7ffffc3, 27),
    (0x7ffffc4, 27),
    (0x7ffffc5, 27),
    (0x7ffffc6, 27),
    (0x7ffffc7, 27),
    (0x7ffffc8, 27),
    (0x7ffffc9, 27),
    (0x7ffffca, 27),
    (0x7ffffcb, 27),
    (0x7ffffcc, 27),
    (0x7ffffcd, 27),
    (0x7ffffce, 27),
    (0x7ffffcf, 27),
    (0x7ffffd0, 27),
    (0x7ffffd1, 27),
    (0x7ffffd2, 27),
    (0x7ffffd3, 27),
    (0x7ffffd4, 27),
    (0x7ffffd5, 27),
    (0x7ffffd6, 27),
    (0x7ffffd7, 27),
    (0x7ffffd8, 27),
    (0x7ffffd9, 27),
    (0xe8, 8),
    (0xffc, 12),
    (0x3ffa, 14),
    (0x7ffc, 15),
    (0x7ffd, 15),
    (0x24, 6),
    (0x6e, 7),
    (0x7ffe, 15),
    (0x7fa, 11),
    (0x7fb, 11),
    (0x3fa, 10),
    (0x7fc, 11),
    (0xe9, 8),
    (0x25, 6),
    (0x4, 5),
    (0x0, 4),
    (0x5, 5),
    (0x6, 5),
    (0x7, 5),
    (0x26, 6),
    (0x27, 6),
    (0x28, 6),
    (0x29, 6),
    (0x2a, 6),
    (0x2b, 6),
    (0x2c, 6),
    (0x1ec, 9),
    (0xea, 8),
    (0x3fffe, 18),
    (0x2d, 6),
    (0x1fffc, 17),
    (0x1ed, 9),
    (0x3ffb, 14),
    (0x6f, 7),
    (0xeb, 8),
    (0xec, 8),
    (0xed, 8),
    (0xee, 8),
    (0x70, 7),
    (0x1ee, 9),
    (0x1ef, 9),
    (0x1f0, 9),
    (0x1f1, 9),
    (0x3fb, 10),
    (0x1f2, 9),
    (0xef, 8),
    (0x1f3, 9),
    (0x1f4, 9),
    (0x1f5, 9),
    (0x1f6, 9),
    (0x1f7, 9),
    (0xf0, 8),
    (0xf1, 8),
    (0x1f8, 9),
    (0x1f9, 9),
    (0x1fa, 9),
    (0x1fb, 9),
    (0x1fc, 9),
    (0x3fc, 10),
    (0x3ffc, 14),
    (0x7ffffda, 27),
    (0x1ffc, 13),
    (0x3ffd, 14),
    (0x2e, 6),
    (0x7fffe, 19),
    (0x8, 5),
    (0x2f, 6),
    (0x9, 5),
    (0x30, 6),
    (0x1, 4),
    (0x31, 6),
    (0x32, 6),
    (0x33, 6),
    (0xa, 5),
    (0x71, 7),
    (0x72, 7),
    (0xb, 5),
    (0x34, 6),
    (0xc, 5),
    (0xd, 5),
    (0xe, 5),
    (0xf2, 8),
    (0xf, 5),
    (0x10, 5),
    (0x11, 5),
    (0x35, 6),
    (0x73, 7),
    (0x36, 6),
    (0xf3, 8),
    (0xf4, 8),
    (0xf5, 8),
    (0x1fffd, 17),
    (0x7fd, 11),
    (0x1fffe, 17),
    (0xffd, 12),
    (0x7ffffdb, 27),
    (0x7ffffdc, 27),
    (0x7ffffdd, 27),
    (0x7ffffde, 27),
    (0x7ffffdf, 27),
    (0x7ffffe0, 27),
    (0x7ffffe1, 27),
    (0x7ffffe2, 27),
    (0x7ffffe3, 27),
    (0x7ffffe4, 27),
    (0x7ffffe5, 27),
    (0x7ffffe6, 27),
    (0x7ffffe7, 27),
    (0x7ffffe8, 27),
    (0x7ffffe9, 27),
    (0x7ffffea, 27),
    (0x7ffffeb, 27),
    (0x7ffffec, 27),
    (0x7ffffed, 27),
    (0x7ffffee, 27),
    (0x7ffffef, 27),
    (0x7fffff0, 27),
    (0x7fffff1, 27),
    (0x7fffff2, 27),
    (0x7fffff3, 27),
    (0x7fffff4, 27),
    (0x7fffff5, 27),
    (0x7fffff6, 27),
    (0x7fffff7, 27),
    (0x7fffff8, 27),
    (0x7fffff9, 27),
    (0x7fffffa, 27),
    (0x7fffffb, 27),
    (0x7fffffc, 27),
    (0x7fffffd, 27),
    (0x7fffffe, 27),
    (0x7ffffff, 27),
    (0x3ffff80, 26),
    (0x3ffff81, 26),
    (0x3ffff82, 26),
    (0x3ffff83, 26),
    (0x3ffff84, 26),
    (0x3ffff85, 26),
    (0x3ffff86, 26),
    (0x3ffff87, 26),
    (0x3ffff88, 26),
    (0x3ffff89, 26),
    (0x3ffff8a, 26),
    (0x3ffff8b, 26),
    (0x3ffff8c, 26),
    (0x3ffff8d, 26),
    (0x3ffff8e, 26),
    (0x3ffff8f, 26),
    (0x3ffff90, 26),
    (0x3ffff91, 26),
    (0x3ffff92, 26),
    (0x3ffff93, 26),
    (0x3ffff94, 26),
    (0x3ffff95, 26),
    (0x3ffff96, 26),
    (0x3ffff97, 26),
    (0x3ffff98, 26),
    (0x3ffff99, 26),
    (0x3ffff9a, 26),
    (0x3ffff9b, 26),
    (0x3ffff9c, 26),
    (0x3ffff9d, 26),
    (0x3ffff9e, 26),
    (0x3ffff9f, 26),
    (0x3ffffa0, 26),
    (0x3ffffa1, 26),
    (0x3ffffa2, 26),
    (0x3ffffa3, 26),
    (0x3ffffa4, 26),
    (0x3ffffa5, 26),
    (0x3ffffa6, 26),
    (0x3ffffa7, 26),
    (0x3ffffa8, 26),
    (0x3ffffa9, 26),
    (0x3ffffaa, 26),
    (0x3ffffab, 26),
    (0x3ffffac, 26),
    (0x3ffffad, 26),
    (0x3ffffae, 26),
    (0x3ffffaf, 26),
    (0x3ffffb0, 26),
    (0x3ffffb1, 26),
    (0x3ffffb2, 26),
    (0x3ffffb3, 26),
    (0x3ffffb4, 26),
    (0x3ffffb5, 26),
    (0x3ffffb6, 26),
    (0x3ffffb7, 26),
    (0x3ffffb8, 26),
    (0x3ffffb9, 26),
    (0x3ffffba, 26),
    (0x3ffffbb, 26),
    (0x3ffffbc, 26),
    (0x3ffffbd, 26),
    (0x3ffffbe, 26),
    (0x3ffffbf, 26),
    (0x3ffffc0, 26),
    (0x3ffffc1, 26),
    (0x3ffffc2, 26),
    (0x3ffffc3, 26),
    (0x3ffffc4, 26),
    (0x3ffffc5, 26),
    (0x3ffffc6, 26),
    (0x3ffffc7, 26),
    (0x3ffffc8, 26),
    (0x3ffffc9, 26),
    (0x3ffffca, 26),
    (0x3ffffcb, 26),
    (0x3ffffcc, 26),
    (0x3ffffcd, 26),
    (0x3ffffce, 26),
    (0x3ffffcf, 26),
    (0x3ffffd0, 26),
    (0x3ffffd1, 26),
    (0x3ffffd2, 26),
    (0x3ffffd3, 26),
    (0x3ffffd4, 26),
    (0x3ffffd5, 26),
    (0x3ffffd6, 26),
    (0x3ffffd7, 26),
    (0x3ffffd8, 26),
    (0x3ffffd9, 26),
    (0x3ffffda, 26),
    (0x3ffffdb, 26),
    (0x3ffffdc, 2),
]

