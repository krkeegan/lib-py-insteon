import time

from .msg_schema import *
from .helpers import *


class PLM_Message(object):
    # Initialization Functions

    def __init__(self, plm, **kwargs):
        self._plm = plm
        self._plm_ack = False
        self._seq_time = 0
        self._seq_lock = False
        self._is_incomming = False
        self._plm_retry = 0
        self._failed = False
        self._plm_schema = {}
        self._raw_msg = bytes()
        self._insteon_msg = {}
        self._creation_time = time.time()
        self._time_sent = 0
        self._plm_success_callback = lambda: None
        self._msg_failed_callback = lambda: None
        if 'is_incomming' in kwargs:
            self._is_incomming = True
        self._device = None
        if 'device' in kwargs:
            self._device = kwargs['device']
        self.msg_from_raw(**kwargs)
        self.command_to_raw(**kwargs)

    @property
    def plm(self):
        return self._plm

    @property
    def device(self):
        return self._device

    @property
    def creation_time(self):
        return self._creation_time

    @property
    def time_sent(self):
        return self._time_sent

    @time_sent.setter
    def time_sent(self, value):
        self._time_sent = value

    @property
    def time_plm_ack(self):
        return self._time_plm_ack

    @time_plm_ack.setter
    def time_plm_ack(self, value):
        self._time_plm_ack = value

    def msg_from_raw(self, **kwargs):
        if 'raw_data' not in kwargs:
            return
        self._plm_schema = PLM_SCHEMA[kwargs['raw_data'][1]].copy()
        self._raw_msg = kwargs['raw_data']
        self._init_insteon_msg(**kwargs)

    def command_to_raw(self, **kwargs):
        '''Takes a command dictionary and builds an Insteon
        message'''
        if 'plm_cmd' not in kwargs:
            return
        plm_cmd = kwargs['plm_cmd']
        plm_prefix = self._set_plm_schema(plm_cmd)
        if not plm_prefix:
            return
        if not self._initialize_raw_msg(plm_cmd, plm_prefix):
            return
        self._init_plm_msg(**kwargs)
        self._init_insteon_msg(**kwargs)
        return self

    def _init_plm_msg(self, **kwargs):
        if 'plm_bytes' in kwargs:
            plm_bytes = kwargs['plm_bytes']
            for key in plm_bytes:
                if key in self.attribute_positions:
                    self._insert_byte_into_raw(plm_bytes[key], key)

    def _init_insteon_msg(self, **kwargs):
        if self.plm_schema['name'] in ['insteon_received',
                                       'insteon_ext_received', 'insteon_send']:
            self._insteon_msg = Insteon_Message(self, **kwargs)

    def _initialize_raw_msg(self, plm_cmd, plm_prefix):
        msg_direction = 'send_len'
        if self.is_incomming:
            msg_direction = 'rcvd_len'
        if msg_direction in self.plm_schema:
            self._msg_byte_length = self.plm_schema[msg_direction]
            self._raw_msg = bytearray(self.plm_schema[msg_direction][0])
            self._raw_msg[0] = 0x02
            self._raw_msg[1] = plm_prefix
            return True
        else:
            return False

    # Set Bytes in Message
    def _set_plm_schema(self, plm_cmd):
        plm_schema = False
        for plm_prefix, schema in PLM_SCHEMA.items():
            if schema['name'] == plm_cmd:
                plm_schema = schema
                break
        if plm_schema:
            self._plm_schema = plm_schema
            return plm_prefix
        else:
            print("I don't know that plm command")
            return False

    def _insert_byte_into_raw(self, data_byte, pos_name):
        pos = self.attribute_positions[pos_name]
        self._raw_msg[pos] = data_byte
        return

    def _insert_bytes_into_raw(self, byte_dict):
        for name, byte in byte_dict.items():
            self._insert_byte_into_raw(byte, name)
        return

    # Read Message Bytes
    @property
    def attribute_positions(self):
        msg_direction = 'send_byte_pos'
        if self.is_incomming:
            msg_direction = 'recv_byte_pos'
        return self.plm_schema[msg_direction]

    @property
    def parsed_attributes(self):
        '''Returns a dictionary of the attribute names associated with their
        byte values'''
        ret = {}
        for name in self.attribute_positions.keys():
            ret[name] = self.get_byte_by_name(name)
        return ret

    @property
    def plm_resp_flag(self):
        if 'plm_resp' in self.attribute_positions or \
                'plm_resp_e' in self.attribute_positions:
            byte_pos = self.attribute_positions['plm_resp']
            if 'plm_resp_e' in self.attribute_positions:
                byte_pos_e = self.attribute_positions['plm_resp_e']
                if byte_pos_e < len(self.raw_msg):
                    byte_pos = byte_pos_e
            return self.raw_msg[byte_pos]
        else:
            return False

    @property
    def plm_resp_ack(self):
        ret = False
        if self.plm_resp_flag == 0x06:
            ret = True
        return ret

    @property
    def plm_resp_nack(self):
        ret = False
        if self.plm_resp_flag == 0x15:
            ret = True
        return ret

    @property
    def plm_resp_bad_cmd(self):
        ret = False
        if self.plm_resp_flag == 0x0F:
            ret = True
        return ret

    @property
    def raw_msg(self):
        return self._raw_msg.copy()

    def get_byte_by_name(self, byte_name):
        ret = False
        if byte_name in self.attribute_positions:
            pos = self.attribute_positions[byte_name]
            if pos < len(self.raw_msg):
                ret = self.raw_msg[pos]
        return ret

    # Message Meta Data
    @property
    def plm_schema(self):
        return self._plm_schema.copy()

    @property
    def plm_cmd_type(self):
        return self.plm_schema['name']

    @property
    def is_incomming(self):
        return self._is_incomming

    @property
    def failed(self):
        return self._failed

    @failed.setter
    def failed(self, boolean):
        self._failed = boolean
        if boolean == True:
            self._msg_failed_callback()

    @property
    def plm_ack(self):
        return self._plm_ack

    @plm_ack.setter
    def plm_ack(self, boolean):
        self._plm_ack = boolean
        if boolean == True:
            self.plm_success_callback()

    @property
    def plm_retry(self):
        return self._plm_retry

    @plm_retry.setter
    def plm_retry(self, count):
        self._plm_retry = count

    @property
    def insteon_msg(self):
        return self._insteon_msg

    @property
    def seq_lock(self):
        return self._seq_lock

    @seq_lock.setter
    def seq_lock(self, boolean):
        self._seq_lock = boolean

    @property
    def seq_time(self):
        return self._seq_time

    @seq_time.setter
    def seq_time(self, int):
        self._seq_time = int

    @property
    def plm_success_callback(self):
        '''Function to run on successful plm ack'''
        return self._plm_success_callback

    @plm_success_callback.setter
    def plm_success_callback(self, value):
        self._plm_success_callback = value

    @property
    def msg_failure_callback(self):
        '''Function to run on failure of message.  Could be either a
        PLM or Device Nack or failure'''
        return self._msg_failed_callback

    @msg_failure_callback.setter
    def msg_failure_callback(self, value):
        self._msg_failed_callback = value


class Insteon_Message(object):

    def __init__(self, parent, **kwargs):
        self._device_ack = False
        self._device_retry = 0
        self._cmd_schema = {}
        self._device_cmd_name = ''
        self._parent = parent
        self._device_success_callback = lambda: None
        # Need to reinitialize the message length??? Extended message
        if 'dev_cmd' in kwargs:
            self._construct_insteon_send(kwargs['dev_cmd'])
        if 'dev_bytes' in kwargs:
            for name, byte in kwargs['dev_bytes'].items():
                self._parent._insert_byte_into_raw(byte, name)

    def _construct_insteon_send(self, dev_cmd):
        if dev_cmd['msg_length'] == 'extended':
            length_array = self._parent._msg_byte_length
            addl_length = length_array[1] - length_array[0]
            self._parent._raw_msg.extend(bytearray(addl_length))
        msg_flags = self._construct_msg_flags(dev_cmd)
        self._parent._insert_byte_into_raw(msg_flags, 'msg_flags')
        self._parent._insert_byte_into_raw(
            self._parent.device.dev_id_hi, 'to_addr_hi')
        self._parent._insert_byte_into_raw(
            self._parent.device.dev_id_mid, 'to_addr_mid')
        self._parent._insert_byte_into_raw(
            self._parent.device.dev_id_low, 'to_addr_low')
        # Process functions if they exist
        keys = ('cmd_1', 'cmd_2', 'usr_1', 'usr_2',
                'usr_3', 'usr_4', 'usr_5', 'usr_6',
                'usr_7', 'usr_8', 'usr_9', 'usr_10',
                'usr_11', 'usr_12', 'usr_13', 'usr_14')
        # could shorten this by just searching for callable keys in command
        for key in keys:
            if key in dev_cmd and callable(dev_cmd[key]):
                value = dev_cmd[key](self._parent.device)
                self._parent._insert_byte_into_raw(value, key)
            elif key in dev_cmd:
                self._parent._insert_byte_into_raw(dev_cmd[key], key)
        self._device_cmd_name = dev_cmd['name']

    def _construct_msg_flags(self, dev_cmd):
        msg_types = {
            'broadcast': 4,
            'direct': 0,
            'direct_ack': 1,
            'direct_nack': 5,
            'alllink_broadcast': 6,
            'alllink_cleanup': 2,
            'alllink_cleanup_ack': 3,
            'alllink_cleanup_nack': 7,
        }
        msg_flags = msg_types[dev_cmd['message_type']]
        msg_flags = msg_flags << 5
        if dev_cmd['msg_length'] == 'extended':
            msg_flags = msg_flags | 16
        hops_left = self._parent.device.smart_hops << 2
        msg_flags = msg_flags | hops_left
        msg_flags = msg_flags | self._parent.device.smart_hops
        return msg_flags

    def _set_i2cs_checksum(self):
        if (self.msg_length == 'extended' and
                self._parent.device.attribute('engine_version') == 0x02):
            checksum = self._calculate_i2cs_checksum()
            self._parent._insert_byte_into_raw(checksum, 'usr_14')
            return

    def _calculate_i2cs_checksum(self):
        # Sum Relevant Bytes
        keys = ('cmd_1', 'cmd_2', 'usr_1', 'usr_2',
                'usr_3', 'usr_4', 'usr_5', 'usr_6',
                'usr_7', 'usr_8', 'usr_9', 'usr_10',
                'usr_11', 'usr_12', 'usr_13')
        bytesum = 0
        for key in keys:
            bytesum += self._parent.get_byte_by_name(key)
        # Flip Bits
        bytesum = ~ bytesum
        # Add 1
        bytesum += 1
        # Truncate to a byte
        bytesum = bytesum & 0b11111111
        return bytesum

    @property
    def valid_i2cs_checksum(self):
        ret = False
        if (self._parent.get_byte_by_name('usr_14') ==
                self._calculate_i2cs_checksum()):
            ret = True
        return ret

    @property
    def device_retry(self):
        return self._device_retry

    @device_retry.setter
    def device_retry(self, count):
        self._device_retry = count

    @property
    def device_cmd_name(self):
        return self._device_cmd_name

    @property
    def message_type(self):
        msg_flags = self._parent.get_byte_by_name('msg_flags')
        ret = False
        if msg_flags:
            msg_types = {
                4: 'broadcast',
                0: 'direct',
                1: 'direct_ack',
                5: 'direct_nack',
                6: 'alllink_broadcast',
                2: 'alllink_cleanup',
                3: 'alllink_cleanup_ack',
                7: 'alllink_cleanup_nack'
            }
            message_type = msg_flags & 0b11100000
            message_type = message_type >> 5
            ret = msg_types[message_type]
        return ret

    @property
    def msg_length(self):
        msg_flags = self._parent.get_byte_by_name('msg_flags')
        ret = False
        if msg_flags:
            ret = 'standard'
            if msg_flags & 16:
                ret = 'extended'
        return ret

    @property
    def hops_left(self):
        msg_flags = self._parent.get_byte_by_name('msg_flags')
        ret = False
        if msg_flags:
            hops_left = msg_flags & 0b00001100
            ret = hops_left >> 2
        return ret

    @hops_left.setter
    def hops_left(self, value):
        msg_flags = self._parent.get_byte_by_name('msg_flags')
        if value < 0:
            value = 0
        if value > 3:
            value = 3
        # clear the hops left
        msg_flags = msg_flags & 0b11110011
        # set the hops left
        value = value << 2
        msg_flags = msg_flags | value
        self._parent._insert_byte_into_raw(msg_flags, 'msg_flags')

    @property
    def max_hops(self):
        msg_flags = self._parent.get_byte_by_name('msg_flags')
        ret = False
        if msg_flags:
            ret = msg_flags & 0b00000011
        return ret

    @max_hops.setter
    def max_hops(self, value):
        msg_flags = self._parent.get_byte_by_name('msg_flags')
        if value < 0:
            value = 0
        if value > 3:
            value = 3
        # clear the max hops
        msg_flags = msg_flags & 0b11111100
        # set the max hops
        msg_flags = msg_flags | value
        self._parent._insert_byte_into_raw(msg_flags, 'msg_flags')

    @property
    def to_addr_str(self):
        if 'to_addr_hi' in self._parent.attribute_positions:
            byte_pos_hi = self._parent.attribute_positions['to_addr_hi']
            byte_pos_mid = self._parent.attribute_positions['to_addr_mid']
            byte_pos_low = self._parent.attribute_positions['to_addr_low']
            return BYTE_TO_HEX(bytes((self._parent.raw_msg[byte_pos_hi],
                                      self._parent.raw_msg[byte_pos_mid],
                                      self._parent.raw_msg[byte_pos_low],
                                      )))
        else:
            return False

    @property
    def from_addr_str(self):
        if 'to_addr_hi' in self._parent.attribute_positions:
            byte_pos_hi = self._parent.attribute_positions['from_addr_hi']
            byte_pos_mid = self._parent.attribute_positions['from_addr_mid']
            byte_pos_low = self._parent.attribute_positions['from_addr_low']
            return BYTE_TO_HEX(bytes((self._parent.raw_msg[byte_pos_hi],
                                      self._parent.raw_msg[byte_pos_mid],
                                      self._parent.raw_msg[byte_pos_low],
                                      )))
        else:
            return False

    @property
    def device_ack(self):
        return self._device_ack

    @device_ack.setter
    def device_ack(self, boolean):
        self._device_ack = boolean
        if boolean == True:
            self._parent.device._add_to_hop_array(self.max_hops)
            self.device_success_callback()

    @property
    def device_success_callback(self):
        '''Function to run on successful device ack'''
        return self._device_success_callback

    @device_success_callback.setter
    def device_success_callback(self, value):
        self._device_success_callback = value
