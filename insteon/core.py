import binascii
import pprint

from .plm import PLM
from .msg_schema import *
from .helpers import *

class Insteon_Core(object):
    '''Provides global management functions'''
    def __init__(self):
        self._plms = []
        # TODO move devices dict to the PLM object
        self.devices = {}

    def loop_once(self):
        '''Perform one loop of processing the data waiting to be
        handled by the Insteon Core'''
        for plm in self._plms:
            plm.process_input()
            plm.process_unacked_msg()
            plm.process_queue()

    def add_plm(self,port):
        '''Inform the core of a plm that should be monitored as part
        of the core process'''
        ret = PLM(port, self)
        self._plms.append(ret)
        return ret

    
