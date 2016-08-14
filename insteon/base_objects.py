import time
import datetime
import pprint

from .helpers import *


class ALDB(object):

    def __init__(self, parent):
        self._parent = parent
        self._aldb = {}

    def edit_record(self, position, record):
        self._aldb[position] = record

    def delete_record(self, position):
        del(self._aldb[position])

    def get_record(self, position):
        return self._aldb[position]

    def get_all_records(self):
        return self._aldb.copy()

    def get_all_records_str(self):
        ret = {}
        for key, value in self._aldb.items():
            ret[key] = BYTE_TO_HEX(value)
        return ret

    def have_aldb_cache(self):
        # TODO distinguish between empty aldb and no aldb this is only used
        # for the PLM so far, perhaps move there?
        ret = True
        if len(self._aldb) == 0:
            ret = False
        return ret

    def load_aldb_records(self, records):
        for key, record in records.items():
            self.edit_record(key, bytearray.fromhex(record))

    def clear_all_records(self):
        self._aldb = {}

    def edit_record_byte(self, aldb_pos, byte_pos, byte):
        self._aldb[aldb_pos][byte_pos] = byte

    def get_matching_records(self, attributes):
        '''Returns an array of positions of each records that matches ALL
        attributes'''
        ret = []
        for position, record in self._aldb.items():
            parsed_record = self.parse_record(position)
            ret.append(position)
            for attribute, value in attributes.items():
                if parsed_record[attribute] != value:
                    ret.remove(position)
                    break
        return ret

    def parse_record(self, position):
        bytes = self._aldb[position]
        parsed = {
            'record_flag': bytes[0],
            'in_use':  bytes[0] & 0b10000000,
            'controller':  bytes[0] & 0b01000000,
            'responder': ~bytes[0] & 0b01000000,
            'highwater': ~bytes[0] & 0b00000010,
            'group': bytes[1],
            'dev_addr_hi': bytes[2],
            'dev_addr_mid': bytes[3],
            'dev_addr_low': bytes[4],
            'data_1': bytes[5],
            'data_2': bytes[6],
            'data_3': bytes[7],
        }
        for attr in ('in_use', 'controller', 'responder', 'highwater'):
            if parsed[attr]:
                parsed[attr] = True
            else:
                parsed[attr] = False
        return parsed

    def get_linked_obj(self, position):
        parsed_record = self.parse_record(position)
        high = parsed_record['dev_addr_hi']
        mid = parsed_record['dev_addr_mid']
        low = parsed_record['dev_addr_low']
        return self._parent.plm.get_device_by_addr(BYTE_TO_ID(high, mid, low))

    def is_last_aldb(self, key):
        ret = True
        if self.get_record(key)[0] & 0b00000010:
            ret = False
        return ret

    def is_empty_aldb(self, key):
        ret = True
        if self.get_record(key)[0] & 0b10000000:
            ret = False
        return ret


class Device_ALDB(ALDB):

    def __init__(self, parent):
        super().__init__(parent)
        self._msb = 0x00
        self._lsb = 0x00

    @property
    def msb(self):
        return self._msb

    @msb.setter
    def msb(self, value):
        self._msb = value

    @property
    def lsb(self):
        return self._lsb

    @lsb.setter
    def lsb(self, value):
        self._lsb = value

    def _get_aldb_key(self):
        offset = 7 - (self.lsb % 8)
        highest_byte = self.lsb + offset
        key = bytes([self.msb, highest_byte])
        return BYTE_TO_HEX(key)

    def query_aldb(self):
        if self._parent.attribute('engine_version') == 0:
            self._msb = 0x0F
            self._lsb = 0xF8
            self._parent.send_command('set_address_msb', 'query_aldb')
        else:
            self._msb = 0x00
            self._lsb = 0x00
            self._parent.send_command('read_aldb', 'query_aldb')

    def create_responder(self, controller, d1, d2, d3):
                # Device Responder
                # D1 On Level D2 Ramp Rate D3 Group of responding device i1 00
                # i2 01
        pass

    def create_controller(responder):
                # Device controller
                # D1 03 Hops?? D2 00 D3 Group 01 of responding device??
        pass


class PLM_ALDB(ALDB):

    def add_record(self, aldb):
        position = str(len(self._aldb) + 1)
        position = position.zfill(4)
        self._aldb[position] = aldb

    def query_aldb(self):
        '''Queries the PLM for a list of the link records saved on
        the PLM and stores them in the cache'''
        self.clear_all_records()
        self._parent.send_command('all_link_first_rec', 'query_aldb')

    def create_responder(self, controller, *args):
        self._write_link(controller, is_plm_controller=False)

    def create_controller(self, controller, *args):
        self._write_link(controller, is_plm_controller=True)

    def _write_link(self, linked_obj, is_plm_controller):
        group = linked_obj.group_number
        if is_plm_controller:
            group = self._parent.group_number
        link_bytes = {
            'controller': True if is_plm_controller else False,
            'responder': False if is_plm_controller else True,
            'group': group,
            'dev_addr_hi': linked_obj.dev_id_hi,
            'dev_addr_mid': linked_obj.dev_id_mid,
            'dev_addr_low': linked_obj.dev_id_low,
        }
        del link_bytes['controller']
        del link_bytes['responder']
        records = self.get_matching_records(link_bytes)
        link_flags = 0xE2 if is_plm_controller else 0xA2
        ctrl_code = 0x20
        if (len(records) == 0):
            ctrl_code = 0x40 if is_plm_controller else 0x41
        link_bytes.update({
            'ctrl_code': ctrl_code,
            'link_flags': link_flags,
            'data_1': linked_obj.dev_cat,
            'data_2': linked_obj.sub_cat,
            'data_3': linked_obj.firmware
        })
        self._parent.send_command('all_link_manage_rec', '', link_bytes)


class Base_Device(object):

    def __init__(self, core, plm, **kwargs):
        self._core = core
        self._plm = plm
        self._state_machine = 'default'
        self._state_machine_time = 0
        self._device_msg_queue = {}
        self._attributes = {}
        self._out_history = []
        if 'attributes' in kwargs:
            self._load_attributes(kwargs['attributes'])

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
        eliminated if it has not been updated within 8 seconds. You
        can update a state by calling update_state_machine or sending
        a command with the appropriate state value'''
        if self._state_machine_time <= (time.time() - 8) or \
                self._state_machine == 'default':
            # Always check for states other than default
            if self._state_machine != 'default':
                now = datetime.datetime.now().strftime("%M:%S.%f")
                print(now, self._state_machine, "state expired")
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

    def remove_state_machine(self, value):
        if value == self.state_machine:
            print('finished', self.state_machine)
            self._state_machine = 'default'
            self._state_machine_time = time.time()
        else:
            print(value, 'was not the active state_machine')

    def update_state_machine(self, value):
        if value == self.state_machine:
            self._state_machine_time = time.time()
        else:
            print(value, 'was not the active state_machine')

    def _queue_device_msg(self, message, state):
        if state == '':
            state = 'default'
        if state not in self._device_msg_queue:
            self._device_msg_queue[state] = []
        self._device_msg_queue[state].append(message)

    def _resend_msg(self, message):
        # This is a bit of a hack, assumes the state has not changed
        # Maybe move state to the message class?
        state = self.state_machine
        if state not in self._device_msg_queue:
            self._device_msg_queue[state] = []
        self._device_msg_queue[state].insert(0, message)
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

    def _update_message_history(self, msg):
        # Remove old messages first
        archive_time = time.time() - 120
        last_msg_to_del = 0
        for search_msg in self._out_history:
            if search_msg.time_sent < archive_time:
                last_msg_to_del += 1
            else:
                break
        if last_msg_to_del:
            del self._out_history[0:last_msg_to_del]
        # Add this message onto the end
        self._out_history.append(msg)

    def search_last_sent_msg(self, **kwargs):
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
                        msg.insteon_msg.device_cmd_name == kwargs['insteon_cmd']:
                    ret = msg
                    break
        return ret

    def attribute(self, attr, value=None):
        if value is not None:
            self._attributes[attr] = value
        try:
            ret = self._attributes[attr]
        except KeyError:
            ret = None
        return ret

    def _load_attributes(self, attributes):
        for name, value in attributes.items():
            if name == 'ALDB':
                self._aldb.load_aldb_records(value)
            elif name == 'Devices':  # should only be plm?
                self._load_devices(value)
            else:
                self.attribute(name, value)

    def _load_devices(self, devices):
        for id, attributes in devices.items():
            device = self.add_device(id, attributes=attributes)


class Insteon_Group(object):

    @property
    def group_number(self):
        # sub groups override that
        return 1

    @property
    def dev_id_hi(self):
        return self._parent._dev_id_hi

    @property
    def dev_id_mid(self):
        return self._parent._dev_id_mid

    @property
    def dev_id_low(self):
        return self._parent._dev_id_low

    @property
    def dev_cat(self):
        return self._parent.dev_cat

    @property
    def sub_cat(self):
        return self._parent.sub_cat

    @property
    def firmware(self):
        return self._parent.firmware

    def create_link(self, responder, d1, d2, d3):
        pass
        self._aldb.create_controller(responder)
        responder._aldb.create_responder(self, d1, d2, d3)


class Root_Insteon(Base_Device, Insteon_Group):

    def __init__(self, core, plm, **kwargs):
        self._groups = []
        super().__init__(core, plm, **kwargs)

    def create_group(self, group_num, Group_Class):
        self._groups.append(Group_Class(self, group_num))

    def get_object_by_group_num(self, search_num):
        ret = None
        if search_num == 0x00 or search_num == 0x01:
            ret = self
        else:
            for group_obj in self._groups:
                if group_obj.group_number == search_num:
                    ret = group_obj
                    break
        return ret


class Trigger_Manager(object):

    def __init__(self, parent):
        self._parent = parent
        self._triggers = {}

    def add_trigger(self, trigger_obj):
        self._triggers[time.time()] = trigger_obj

    # TODO remove expired triggers?

    def match_msg(self, msg):
        parsed_msg = msg.parsed_attributes
        delete_keys = []
        for trigger_key, trigger in self._triggers.items():
            if trigger.msg_name == msg.plm_cmd_type:
                trigger_match = True
                for test_key, test_val in trigger.attributes.items():
                    if test_key in parsed_msg:
                        if (
                                trigger.attributes[test_key] ==
                                parsed_msg[test_key]
                        ):
                            pass  # match
                        else:
                            trigger_match = False
                            break
                # end loop of test attributes
                if (trigger_match):
                    self.run_trigger(msg, trigger_key)
                    delete_keys.append(trigger_key)
        # end loop of triggers
        for trigger_key in delete_keys:
            del self._triggers[trigger_key]

    def run_trigger(self, msg, trigger_key):
        trigger = self._triggers[trigger_key]
        if msg.plm_resp_ack and trigger.ack_function != '':
            trigger.ack_function()
        elif msg.plm_resp_nack and trigger.nack_function != '':
            trigger.nack_function()
        elif msg.plm_resp_bad_cmd and trigger.bad_cmd_function != '':
            trigger.bad_cmd_function()

    def delete_matching_attr(self, msg_name, attributes={}):
        pass


class Trigger(object):

    def __init__(self, msg_name, attributes={}):
        '''Trigger functions will be called when a message matching all of the
        identified attributes is received.  The function matching the type of
        ack/nack/bad_cmd type is called.  In any case, even if no function
        is defined, the trigger is then deleted.'''
        self._msg_name = msg_name
        self._msg_attributes = attributes
        self._ack_function = ''
        self._nack_function = ''
        self._bad_cmd_function = ''

    @property
    def ack_function(self):
        """Contains a function to be called on an ACK trigger"""
        return self._ack_function

    @ack_function.setter
    def ack_function(self, function):
        self._ack_function = function

    @property
    def nack_function(self):
        """Contains a function to be called on an NACK trigger"""
        return self._nack_function

    @nack_function.setter
    def nack_function(self, function):
        self._nack_function = function

    @property
    def bad_cmd_function(self):
        """Contains a function to be called on an bad_cmd trigger"""
        return self._bad_cmd_function

    @bad_cmd_function.setter
    def bad_cmd_function(self, function):
        self._bad_cmd_function = function

    @property
    def attributes(self):
        return self._msg_attributes

    @property
    def msg_name(self):
        return self._msg_name
