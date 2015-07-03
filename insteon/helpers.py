import binascii

# global helpers #
def BYTE_TO_HEX(data):
    '''Takes a bytearray or a byte and returns a string
    representation of the hex value'''
    return binascii.hexlify(data).decode().upper()