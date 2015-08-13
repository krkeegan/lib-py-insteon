import binascii

HOUSE_TO_BYTE = {
    'a': 0x60,
    'b': 0xE0,
    'c': 0x20,
    'd': 0xA0,
    'e': 0x10,
    'f': 0x90,
    'g': 0x50,
    'h': 0xD0,
    'i': 0x70,
    'j': 0xF0,
    'k': 0x30,
    'l': 0xB0,
    'm': 0x00,
    'n': 0x80,
    'o': 0x40,
    'p': 0xC0
}

UNIT_TO_BYTE = {
    '1':  0x06,
    '2':  0x0E,
    '3':  0x02,
    '4':  0x0A,
    '5':  0x01,
    '6':  0x09,
    '7':  0x05,
    '8':  0x0D,
    '9':  0x07,
    '10': 0x0F,
    '11': 0x03,
    '12': 0x0B,
    '13': 0x00,
    '14': 0x08,
    '15': 0x04,
    '16': 0x0C,
}

CMD_TO_BYTE = {
    'on':           0x02,
    'off':          0x03,
    'bright':       0x05,
    'dim':          0x04,
    'preset_dim1':  0x0A,
    'preset_dim2':  0x0B,
    'all_off':      0x00,
    'all_lights_on': 0x01,
    'all_lights_off': 0x06,
    'status':       0x0F,
    'status_on':    0x0D,
    'status_off':   0x0E,
    'hail_ack':     0x09,
    'ext_code':     0x07,
    'ext_data':     0x0C,
    'hail_request': 0x08
}

# global helpers #
def BYTE_TO_HEX(data):
    '''Takes a bytearray or a byte and returns a string
    representation of the hex value'''
    return binascii.hexlify(data).decode().upper()

def BYTE_TO_ID(high, mid, low):
    return '{:02x}'.format(high, 'x').upper() + '{:02x}'.format(mid, 'x').upper() + '{:02x}'.format(low, 'x').upper() 