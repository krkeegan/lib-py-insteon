import binascii
import pprint
import json
import time
import atexit
import signal
import sys
import threading

from .plm import PLM
from .msg_schema import *
from .helpers import *
from .rest_server import *


class Insteon_Core(object):
    '''Provides global management functions'''

    def __init__(self):
        self._plms = []
        self._last_saved_time = 0
        self._load_state()
        # Be sure to save before exiting
        atexit.register(self._save_state, True)
        signal.signal(signal.SIGINT, self._signal_handler)

    def start_rest_server(self):
        server = http.server.HTTPServer(('', 8080), HTTPHandler)
        server.core = self
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

    def loop_once(self):
        '''Perform one loop of processing the data waiting to be
        handled by the Insteon Core'''
        for plm in self._plms:
            plm.process_input()
            plm.process_unacked_msg()
            plm.process_queue()
        self._save_state()

    def add_plm(self, **kwargs):
        '''Inform the core of a plm that should be monitored as part
        of the core process'''
        device_id = ''
        ret = None
        if 'device_id' in kwargs:
            device_id = kwargs['device_id']
        if 'attributes' in kwargs:
            attributes = kwargs['attributes']
            ret = PLM(self, device_id=device_id, attributes=attributes)
        elif 'port' in kwargs:
            port = kwargs['port']
            for plm in self._plms:
                if plm.attribute('port') == port:
                    ret = plm
            if ret is None:
                ret = PLM(self, device_id=device_id, port=port)
        else:
            print('you need to define a port for this plm')
        if ret is not None:
            self._plms.append(ret)
        return ret

    def get_plm_by_id(self, id):
        ret = None
        for plm in self._plms:
            if plm.device_id == id:
                ret = plm
        return ret

    def get_all_plms(self):
        ret = []
        for plm in self._plms:
            ret.append(plm)
        return ret

    def _save_state(self, is_exit=False):
        # Saves the config of the entire core to a file
        if self._last_saved_time < time.time() - 60 or is_exit:
            # Save once a minute, on on exit
            out_data = {'PLMs': {}}
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
            try:
                json_string = json.dumps(out_data,
                                         sort_keys=True,
                                         indent=4,
                                         ensure_ascii=False)
            except Exception:
                print ('error writing config to file')
            else:
                outfile = open('config.json', 'w')
                outfile.write(json_string)
                outfile.close()
            self._saved_state = out_data
            self._last_saved_time = time.time()

    def _load_state(self):
        try:
            with open('config.json', 'r') as infile:
                read_data = infile.read()
            read_data = json.loads(read_data)
        except FileNotFoundError:
            read_data = {}
        except ValueError:
            read_data = {}
            print('unable to read config file, skipping')
        if 'PLMs' in read_data:
            for plm_id, plm_data in read_data['PLMs'].items():
                self.add_plm(attributes=plm_data, device_id=plm_id)

    def _signal_handler(self, signal, frame):
        # Catches a Ctrl + C and Saves the Config before exiting
        self._save_state(True)
        print('You pressed Ctrl+C!')
        sys.exit(0)
