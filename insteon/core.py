import binascii
import pprint
import json
import time
import atexit
import signal
import sys

from .plm import PLM
from .msg_schema import *
from .helpers import *

# TODO Load State

class Insteon_Core(object):
    '''Provides global management functions'''
    def __init__(self):
        self._plms = []
        self._last_saved_time = 0
        #Be sure to save before exiting
        atexit.register(self._save_state, True)
        signal.signal(signal.SIGINT, self._signal_handler)
        

    def loop_once(self):
        '''Perform one loop of processing the data waiting to be
        handled by the Insteon Core'''
        for plm in self._plms:
            plm.process_input()
            plm.process_unacked_msg()
            plm.process_queue()
        self._save_state()

    def add_plm(self,port):
        '''Inform the core of a plm that should be monitored as part
        of the core process'''
        ret = PLM(port, self)
        self._plms.append(ret)
        return ret

    def _save_state(self, is_exit = False):
        #Saves the config of the entire core to a file
        if self._last_saved_time < time.time() - 60 or is_exit:
            #Save once a minute, on on exit
            out_data = {'PLMs' : {}}
            for plm in self._plms:
                plm_point = {}
                plm_point = plm._attributes.copy()
                plm_point['ALDB'] = plm._aldb.get_all_records_str()
                plm_point['Devices'] = {}
                out_data['PLMs'][plm.device_id] = plm_point
                for address, device in plm._devices.items():
                    dev_point = device._attributes.copy()
                    dev_point['ALDB'] = device._aldb.get_all_records_str()
                    plm_point['Devices'][address] = dev_point
            with open('config.json', 'w') as outfile:
                json.dump(out_data, 
                          outfile, 
                          sort_keys = True, 
                          indent = 4, 
                          ensure_ascii=False)
            self._saved_state = out_data
            self._last_saved_time = time.time()

    def _signal_handler(self, signal, frame):
        #Catches a Ctrl + C and Saves the Config before exiting
        self._save_state(True)
        print('You pressed Ctrl+C!')
        sys.exit(0)
