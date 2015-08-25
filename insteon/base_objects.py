import time
import pprint

from .helpers import *

class ALDB(object):
    def __init__(self, parent):
        self._parent = parent
        self._aldb = {}

    def edit_record(self,position,record):
        self._aldb[position] = record

    def get_record(self,position):
        return self._aldb[position]

    def get_all_records(self):
        return self._aldb.copy()

    def get_all_records_str(self):
        ret = {}
        for key, value in self._aldb.items():
            ret[key] = BYTE_TO_HEX(value)
        return ret

    def load_aldb_records(self,records):
        for key, record in records.items():
            self.edit_record(key, bytearray.fromhex(record))

    def clear_all_records(self):
        self._aldb = {}

    def edit_record_byte(self,aldb_pos,byte_pos,byte):
        self._aldb[aldb_pos][byte_pos] = byte

    def add_plm_record(self,record):
        position = str(len(self._aldb) + 1)
        position = position.zfill(4)
        self._aldb[position] = record

    def search_for_records(self,attributes):
        '''Performs an AND search for records on this device'''
        ret = []
        for position, record in self._aldb.items():
            parsed_record = self.parse_record(position)
            ret.append(position)
            for attribute, value in attributes.items():
                if parsed_record[attribute] != value:
                    ret.remove(position)
                    break
        return ret
        
    def parse_record(self,position):
        bytes = self._aldb[position]
        parsed = {
            'record_flag' : bytes[0],
            'in_use'    :  bytes[0] & 0b10000000,
            'controller':  bytes[0] & 0b01000000,
            'responder' : ~bytes[0] & 0b01000000,
            'highwater' : ~bytes[0] & 0b00000010,
            'group' : bytes[1],
            'dev_hi' : bytes[2],
            'dev_mid' : bytes[3],
            'dev_low' : bytes[4],
            'data_1' : bytes[5],
            'data_2' : bytes[6],
            'data_3' : bytes[7],
        }
        for attr in ('in_use','controller','responder','highwater'):
            if parsed[attr]:
                parsed[attr] = True
            else:
                parsed[attr] = False
        return parsed

    def linked_device(self,position):
        parsed_record = self.parse_record(position)
        high = parsed_record['dev_hi']
        mid = parsed_record['dev_mid']
        low = parsed_record['dev_low']
        return self._parent.plm.get_device_by_addr(BYTE_TO_ID(high,mid,low))

class Base_Device(object):
    #TODO Store Device State
    def __init__(self, core, plm):
        self._core = core
        self._plm = plm
        self._state_machine = 'default'
        self._state_machine_time = 0
        self._device_msg_queue = {}
        self._attributes = {}
        self._out_history = []
        self._aldb = ALDB(self)

    @property
    def core(self):
        return self._core

    @property
    def plm(self):
        return self._plm

    @property
    def state_machine(self):
        '''The state machine tracks the 'state' that the device is in. 
        This is necessary because Insteon is not a stateless protocol, 
        interpreting some incoming messages requires knowing what 
        commands were previously issued to the device.
        
        Whenever a state is set, only messages of that state will be 
        sent to the device, all other messages will wait in a queue.  
        To avoid locking up a device, a state will automatically be 
        eliminated if it has not been updated within 5 seconds. You 
        can update a state by setting the state machine to the same 
        value again or sending a command with the appropriate state 
        value'''
        if self._state_machine_time <= (time.time() - 5) or \
        self._state_machine == 'default':
            #Always check for states other than default
            if self._state_machine != 'default':
                print (self._state_machine, "state expired")
                pprint.pprint(self._device_msg_queue)
            self._state_machine = self._get_next_state_machine()
            if self._state_machine != 'default':
                self._state_machine_time = time.time()
        return self._state_machine

    def _get_next_state_machine(self):
        next_state = 'default'
        msg_time = 0
        for state in self._device_msg_queue:
            if state != 'default' and self._device_msg_queue[state]:
                test_time = self._device_msg_queue[state][0].creation_time
                if test_time and (msg_time == 0 or test_time < msg_time):
                    next_state = state
                    msg_time = test_time
        return next_state

    def remove_state_machine(self,value):
        if value == self.state_machine:
            print('finished', self.state_machine)
            self._state_machine = 'default'
            self._state_machine_time = time.time()
        else:
            print(value, 'was not the active state_machine')

    def _queue_device_msg(self,message,state):
        if state == '': state = 'default'
        if state not in self._device_msg_queue:
            self._device_msg_queue[state] = []
        self._device_msg_queue[state].append(message)

    def _resend_msg(self,message):
        #This is a bit of a hack, assumes the state has not changed
        #Maybe move state to the message class?
        state = self.state_machine
        if state not in self._device_msg_queue:
            self._device_msg_queue[state] = []
        self._device_msg_queue[state].append(message)
        self._state_machine_time = time.time()

    def pop_device_queue(self):
        '''Returns and removes the next message in the queue'''
        ret = None
        if self.state_machine in self._device_msg_queue and \
        self._device_msg_queue[self.state_machine]:
            ret = self._device_msg_queue[self.state_machine].pop(0)
            self._update_message_history(ret)
            self._state_machine_time = time.time()
        return ret

    def next_msg_create_time(self):
        '''Returns the creation time of the message to be sent in the queue'''
        ret = None
        if self.state_machine in self._device_msg_queue and \
        self._device_msg_queue[self.state_machine]:
            ret = self._device_msg_queue[self.state_machine][0].creation_time
        return ret

    def _update_message_history(self,msg):
        # Remove old messages first
        archive_time = time.time() - 120
        last_msg_to_del = 0
        for msg in self._out_history:
            if msg.time_sent < archive_time:
                last_msg_to_del += 1
            else:
                break
        if last_msg_to_del:
            del self._out_history[0:last_msg_to_del]
        # Add this message onto the end
        self._out_history.append(msg)

    def search_last_sent_msg(self,**kwargs):
        '''Return the most recently sent message of this type
        plm_cmd or insteon_cmd'''
        ret = None
        if 'plm_cmd' in kwargs:
            for msg in reversed(self._out_history):
                if msg.plm_cmd_type == kwargs['plm_cmd']:
                    ret = msg
                    break
        elif 'insteon_cmd' in kwargs:
            for msg in reversed(self._out_history):
                if msg.insteon_msg and \
                msg.device_cmd_name == kwargs['insteon_cmd']:
                    ret = msg
                    break
        return ret

    def attribute(self,attr,value = None):
        if value is not None:
            self._attributes[attr] = value
        try:
            ret = self._attributes[attr]
        except KeyError:
            ret = None
        return ret

    def _load_attributes(self,attributes):
        for name, value in attributes.items():
            if name == 'ALDB':
                self._aldb.load_aldb_records(value)
            elif name == 'Devices':
                pass
            else:
                self.attribute(name,value)
