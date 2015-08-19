import binascii
import pprint

from .plm import PLM
from .insteon_device import Insteon_Device
from .msg_schema import *
from .helpers import *

class Insteon_Core(object):
    '''Provides global management functions'''
    def __init__(self, port):
        # TODO Config_File, array of PLMs
        self.plm = PLM(port, self)
        # TODO move devices dict to the PLM object
        self.devices = {}

    def loop_once(self):
        '''Perform one loop of processing the data waiting to be
        handled by the Insteon Core'''
        self.plm.process_input()
        self.plm.process_unacked_msg()
        self.plm.process_queue()

    def add_device(self, device_id, **kwargs):
        #TODO better handle plm, should support multiple plms
        plm = self.plm
        if 'plm' in kwargs:
            plm = kwargs['plm']
        self.devices[device_id] = Insteon_Device(self, 
                                                 plm, 
                                                 device_id=device_id)
        return self.devices[device_id]

    def add_x10_device(self, address, **kwargs):        
        #TODO better handle plm, should support multiple plms
        #We convert the address to its 'byte' value immediately
        plm = self.plm
        if 'plm' in kwargs:
            plm = kwargs['plm']
        byte_address = (
            HOUSE_TO_BYTE[address[0:1].lower()] | UNIT_TO_BYTE[address[1:2]])
        self.devices[byte_address] = X10_Device(self, 
                                                plm, 
                                                byte_address=byte_address)
        return self.devices[byte_address]
