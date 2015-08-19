import unittest
# append parent directory to import path
import env
# now we can import the lib module
import insteon.plm

class MyTest(unittest.TestCase):
    def setUp(self):
        self.PLM = insteon.plm.PLM('test_fixture', None)
    
    def test_advance_to_msg_start(self):
        self.PLM._read_buffer = bytearray.fromhex('0002')
        self.PLM._advance_to_msg_start()
        self.assertEqual(self.PLM._read_buffer, bytes([0x02]))
        self.PLM._read_buffer = bytearray.fromhex('1502')
        self.PLM._advance_to_msg_start()
        self.assertEqual(self.PLM._read_buffer, bytes([0x02]))

    def test_parse_read_buffer(self):
        self.PLM._read_buffer = bytearray.fromhex(
            '02621CB587052BFB0602501CB58720F5F5212BF5')
        #TODO test each msg type, test handling of extended messages on 0x62
        self.assertEqual(self.PLM._parse_read_buffer(), 
                         bytearray.fromhex('02621CB587052BFB06'))
        self.assertEqual(self.PLM._parse_read_buffer(), 
                         bytearray.fromhex('02501CB58720F5F5212BF5'))
        
if __name__ == '__main__':
    unittest.main()