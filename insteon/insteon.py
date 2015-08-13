import serial
import binascii
import pprint
import time
import datetime
import math
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
        self.devices[device_id] = Device(self, plm, device_id=device_id)
        return self.devices[device_id]

    def add_x10_device(self, address, **kwargs):        
        #TODO better handle plm, should support multiple plms
        #We convert the address to its 'byte' value immediately
        plm = self.plm
        if 'plm' in kwargs:
            plm = kwargs['plm']
        byte_address = HOUSE_TO_BYTE[address[0:1].lower()] | UNIT_TO_BYTE[address[1:2]]
        self.devices[byte_address] = X10_Device(self, plm, byte_address=byte_address)
        return self.devices[byte_address]

class Base_Device(object):
    def __init__(self, core, plm):
        self._core = core
        self._plm = plm
        self._state_machine = 'default'
        self._state_machine_time = 0
        self._device_msg_queue = {}

    @property
    def core(self):
        return self._core

    @property
    def plm(self):
        return self._plm

    @property
    def state_machine(self):
        '''The state machine tracks the 'state' that the device is in. This is necessary
        because Insteon is not a stateless protocol, interpreting some incoming messages
        requires knowing what commands were previously issued to the device.
        
        Whenever a state is set, only messages of that state will be sent to the device,
        all other messages will wait in a queue.  To avoid locking up a device, a state
        will automatically be eliminated if it has not been updated within 5 seconds.
        You can update a state by setting the state machine to the same value again or
        sending a command with the appropriate state value'''
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

    def pop_device_queue(self):
        '''Returns and removes the next message in the queue'''
        ret = None
        if self.state_machine in self._device_msg_queue and \
        self._device_msg_queue[self.state_machine]:
            ret = self._device_msg_queue[self.state_machine].pop(0)
            self._update_message_history(ret)
            self._state_machine_time = time.time()
            msg = self._device_msg_queue[self.state_machine].pop(0)
            self.plm.queue_msg(msg)
        elif self.state_machine == 'default' and \
        'default' in self._device_msg_queue and \
        self._device_msg_queue['default']:
            msg = self._device_msg_queue['default'].pop(0)
            self.plm.queue_msg(msg)

class PLM(Base_Device):
    def __init__(self, port, core):
        super().__init__(core, self)
        self._read_buffer = bytearray()
        self._last_msg = ''
        self._msg_queue = []
        self._wait_to_send = 0
        self._aldb = []
        self._last_x10_house = ''
        self._last_x10_unit = ''
        self._serial = serial.Serial(
                    port=port,
                    baudrate=19200,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                    timeout=0
                    )

    def _read(self):
        '''Reads bytes from PLM and loads them into a buffer'''
        while self._serial.inWaiting() > 0:
            self._read_buffer.extend(self._serial.read())

    def process_input(self):
        '''Reads available bytes from PLM, then parses the bytes
            into a message'''
        self._read()
        self._advance_to_msg_start()
        bytes = self._parse_read_buffer()
        if bytes: self.process_inc_msg(bytes)

    def _advance_to_msg_start(self):
        '''Removes extraneous bytes from start of read buffer'''
        if len(self._read_buffer) >= 2:
            #Handle Errors First
            good_prefix = bytes.fromhex('02')
            wait_prefix = bytes.fromhex('15')
            if not self._read_buffer.startswith((good_prefix,wait_prefix)):
                print('Removed bad starting string from', BYTE_TO_HEX(self._read_buffer))
                index = self._read_buffer.find(good_prefix)
                del self._read_buffer[0:index]
                print('resulting buffer is', BYTE_TO_HEX(self._read_buffer))
            if self._read_buffer.startswith(wait_prefix):
                # TODO need to slow down PLM sending
                print ('need to slow down!!', BYTE_TO_HEX(self._read_buffer))
                self.wait_to_send = time.time() + .5
                del self._read_buffer[0:1]
                self._advance_to_msg_start()

    def _parse_read_buffer(self):
        '''Parses messages out of the read buffer'''
        ret = None
        if len(self._read_buffer) >= 2:
            #Process the message
            cmd_prefix = self._read_buffer[1]
            if cmd_prefix in PLM_SCHEMA:
                byte_length = PLM_SCHEMA[cmd_prefix]['rcvd_len']
                # This solves Insteon stupidity.  0x62 messages can be either
                # standard or extended length.  The only way to determine
                # which length we have received is to look at the message flags
                is_extended = 0
                if cmd_prefix == 0x62 and \
                  len(self._read_buffer) >= 6 and \
                  self._read_buffer[5] & 16:
                    is_extended = 1

                msg_length = byte_length[is_extended]
                if msg_length <= len(self._read_buffer):
                    ret = self._read_buffer[0:msg_length]
                    del self._read_buffer[0:msg_length]
                else:
                    pass
                    #print('need more data',BYTE_TO_HEX(self._read_buffer)) # Need to read more data from PLM
            else:
                # TODO handle this
                print("error, I don't know this prefix")
                index = self._read_buffer.find(good_prefix)
                del self._read_buffer[0:index]
        return ret

    @property
    def wait_to_send(self):
        return self._wait_to_send

    @wait_to_send.setter
    def wait_to_send(self,value):
        self._wait_to_send = value

    def process_inc_msg(self,raw_msg):
        now = datetime.datetime.now().strftime("%M:%S.%f")
        # No matter what, pause for a short period before sending to PLM
        self.wait_to_send = time.time() + (20/1000)
        print(now, 'found legitimate msg', BYTE_TO_HEX(raw_msg))
        msg = PLM_Message(self.core, \
                              raw_data = raw_msg, 
                              is_incomming = True)
        if 'recv_act' in msg.plm_schema:
            try:
                obj = msg.plm_schema['recv_obj'](msg)
            except KeyError as e:
                #TODO this is not a good test an error in the recv_act
                #will cause it to appear as though this device doesn't exist
                print('received message from unknown device', e)
                return
            try:
                msg.plm_schema['recv_act'](obj, msg)
            except Exception as e:
                # Use this to somehow keep messages in the queue??
                # Not sure that is really possible, won't we just end
                # up here again?
                print('Error', e)
        else:
            print('received msg, but no action specified')
            pprint.pprint(msg.__dict__)
        
    def queue_msg(self,msg):
        self._msg_queue.append(msg)

    def _send_msg(self, msg):
        self._last_msg = msg
        self.write(msg)
    
    def _resend_msg(self):
        self._last_msg.plm_ack = False
        self._last_msg.device_ack = False
        msg = self._last_msg
        self._last_msg = {}
        self._msg_queue.insert(0,msg)

    def write(self, msg):
        now = datetime.datetime.now().strftime("%M:%S.%f")
        print(now, 'sending data', BYTE_TO_HEX(msg.raw_msg))
        msg.time_sent = time.time()
        self._serial.write(msg.raw_msg)
        return

    def plm_info(self,msg_obj):
        if self._last_msg.plm_cmd_type == 'plm_info' and msg_obj.plm_resp_ack:
            self._last_msg.plm_ack = True
            self.device_id = msg_obj.get_byte_by_name('from_addr')
            self.dev_cat = msg_obj.get_byte_by_name('dev_cat')
            self.sub_cat = msg_obj.get_byte_by_name('sub_cat')
            self.firmware = msg_obj.get_byte_by_name('firmware')

    def send_command(self,command, state = ''):
        message = PLM_Message(self.core, device=self, plm_cmd=command)
        self._queue_device_msg(message, state)

    def process_unacked_msg(self):
        '''checks for unacked messages'''
        if self._is_ack_pending():
            msg = self._last_msg
        else:
            return
        now = datetime.datetime.now().strftime("%M:%S.%f")
        # allow 75 milliseconds for the PLM to ack a message
        if msg.plm_ack == False: 
            if msg.time_sent < time.time() - (75/1000):
                print(now, 'PLM failed to ack the last message')
                if msg.plm_retry >= 3:
                    print(now, 'PLM retries exceeded, abandoning this message')
                    msg.failed = True
                else:
                    msg.plm_retry += 1
                    self._resend_msg()
            return
        if msg.insteon_msg and msg.insteon_msg.device_ack == False:
            total_hops = msg.insteon_msg.max_hops *2
            hop_delay = 87 if msg.insteon_msg.msg_length == 'standard' else 183
            # These numbers come from real world use (87, 183)
            # 100ms for device to process the msg internally
            total_delay = (total_hops * hop_delay/1000) + (100/1000)
            if msg.time_sent < time.time() - total_delay:
                print(now, 'device failed to ack a message, total delay =', total_delay, 'total hops=', total_hops)
                if msg.insteon_msg.device_retry >= 3:
                    print(now, 'device retries exceeded, abandoning this message')
                    msg.failed = True
                else:
                    msg.insteon_msg.device_retry += 1
                    self._resend_msg()
            return

    def process_queue(self):
        '''Loops through all of the devices and sends the 
        oldest message currently waiting in a device queue
        if there are no other conflicts'''
        if not self._is_ack_pending() and \
        time.time() > self.wait_to_send:
            devices = [self,]
            msg_time = 0
            sending_device = False
            for id, device in self.core.devices.items():
                devices.append(device)
            for device in devices:
                dev_msg_time = device.next_msg_create_time()
                if dev_msg_time and (msg_time == 0 or dev_msg_time < msg_time):
                    sending_device = device
                    msg_time = dev_msg_time
            if sending_device:
                dev_msg = sending_device.pop_device_queue()
                if dev_msg:
                    if dev_msg.insteon_msg:
                        device = dev_msg.insteon_msg.device
                        device.last_msg = dev_msg
                    self._send_msg(dev_msg)

    def _is_ack_pending(self):
        ret = False
        if self._last_msg and not self._last_msg.failed:
            if not self._last_msg.plm_ack:
                ret = True
            elif self._last_msg.insteon_msg and \
            not self._last_msg.insteon_msg.device_ack:
                ret = True
        return ret

    def rcvd_plm_ack(self,msg):
        if self._last_msg.plm_ack == False\
        and msg.raw_msg[0:-1] == self._last_msg.raw_msg:
            if msg.plm_resp_ack:
                self._last_msg.plm_ack = True
            elif msg.plm_resp_nack:
                if 'nack_act' in msg.plm_schema:
                    msg.plm_schema['nack_act'](self, msg)
                else:
                    print('PLM sent NACK to last command')
                    self.wait_to_send = time.time() + .5
            elif msg.plm_resp_bad_cmd:
                print('PLM said bad command')
                self.wait_to_send = time.time() + .5
        else:
            print('received spurious plm ack')

    def rcvd_plm_x10_ack(self,msg):
        #For some reason we have to slow down when sending X10 msgs to the PLM
        self.rcvd_plm_ack(msg)
        self.wait_to_send = time.time() + .5

    def rcvd_aldb_record(self,msg):
        self.add_aldb_to_cache(msg.raw_msg[2:])
        self.send_command('all_link_next_rec', 'query_aldb')

    def add_aldb_to_cache(self,aldb):
        self._aldb.append(aldb)

    def end_of_aldb(self,msg):
        self._last_msg.plm_ack = True
        self.remove_state_machine('query_aldb')
        print('reached the end of the PLMs ALDB')

    def rcvd_all_link_complete(self,msg):
        if msg.get_byte_by_name('link_code') == 0xFF:
            #DELETE THINGS
            pass
        else:
            #Fix stupid discrepancy in Insteon spec
            link_flag = 0xA2
            if msg.get_byte_by_name('link_code') == 0x01:
                link_flag = 0xE2
            self.add_aldb_to_cache(bytearray([link_flag, msg.raw_msg[3:]]))

    def rcvd_btn_event(self,msg):
        print("The PLM Button was pressed")
        #Currently there is no processing of this event

    def rcvd_plm_reset(self,msg):
        self._aldb = []
        print("The PLM was manually reset")

    def rcvd_x10(self,msg):
        if msg.get_byte_by_name('x10_flags') == 0x00:
            self.store_x10_address(msg.get_byte_by_name('raw_x10'))
        else:
            self._dispatch_x10_cmd(msg)

    def store_x10_address(self,byte):
        self._last_x10_house = byte & 0b11110000
        self._last_x10_unit = byte & 0b00001111

    def get_x10_address(self):
        return self._last_x10_house | self._last_x10_unit

    def _dispatch_x10_cmd(self,msg):
        if self._last_x10_house == msg.get_byte_by_name('raw_x10') & 0b11110000:
            try:
                device = self.core.devices[self.get_x10_address()]
                device.inc_x10_msg(msg)
            except KeyError:
                print('Received and X10 command for an unkown device')
        else:
            print("X10 Command House Code did not match expected House Code")
            print("Message ignored")

    def query_aldb (self):
        '''Queries the PLM for a list of the link records saved on
        the PLM and stores them in the cache'''
        self.send_command('all_link_first_rec', 'query_aldb')

class PLM_Message(object):
    #Initialization Functions
    def __init__(self, core, **kwargs):
        self._core = core
        self._plm_ack = False
        self._is_incomming = False
        self._plm_retry = 0
        self._failed = False
        self._plm_schema = {}
        self._raw_msg = bytes()
        self._insteon_msg = {}
        if 'is_incomming' in kwargs: self._is_incomming = True
        self.msg_from_raw(**kwargs)
        self.command_to_raw(**kwargs)

    @property
    def core(self):
        return self._core

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
                    self._insert_byte_into_raw(plm_bytes[key],key)

    def _init_insteon_msg(self, **kwargs):
        if self.plm_schema['name'] in ['insteon_received', \
        'insteon_ext_received', 'insteon_send']:
            self._insteon_msg = Insteon_Message(self, **kwargs)

    def _initialize_raw_msg(self,plm_cmd,plm_prefix):
        msg_direction = 'send_len'
        if self.is_incomming:
            msg_direction = 'rcvd_len'
        if msg_direction in self.plm_schema:
            self._raw_msg = bytearray(self.plm_schema[msg_direction][0])
            self._raw_msg[0] = 0x02
            self._raw_msg[1] = plm_prefix
            return True
        else:
            return False

    # Set Bytes in Message
    def _set_plm_schema(self,plm_cmd):
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

    def _insert_byte_into_raw(self,data_byte,pos_name):
        pos = self.attribute_positions[pos_name]
        self._raw_msg[pos] = data_byte
        return

    #Read Message Bytes
    @property
    def attribute_positions(self):
        msg_direction = 'send_byte_pos'
        if self.is_incomming:
            msg_direction = 'recv_byte_pos'
        return self.plm_schema[msg_direction]

    @property
    def plm_resp_flag(self):
        if 'plm_resp' in self.attribute_positions or \
        'plm_resp_e' in self.attribute_positions:
            byte_pos = self.attribute_positions['plm_resp']
            if 'plm_resp_e' in self.attribute_positions:
                byte_pos_e = self.attribute_positions['plm_resp']
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

    def get_byte_by_name(self,byte_name):
        ret = False
        if byte_name in self.attribute_positions:
            pos = self.attribute_positions[byte_name]
            if pos < len(self.raw_msg):
                ret = self.raw_msg[pos]
        return ret

    #Message Meta Data
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
    def failed(self,boolean):
        self._failed = boolean

    @property
    def plm_ack(self):
        return self._plm_ack

    @plm_ack.setter
    def plm_ack(self,boolean):
        self._plm_ack = boolean

    @property
    def plm_retry(self):
        return self._plm_retry

    @plm_retry.setter
    def plm_retry(self,count):
        self._plm_retry = count

    @property
    def insteon_msg(self):
        return self._insteon_msg

class Insteon_Message(object):
    def __init__(self, parent, **kwargs):
        self._device_ack = False
        self._device_retry = 0
        self._cmd_schema = {}
        self._device_cmd_name = ''
        self._parent = parent
        #Need to reinitialize the message length??? Extended message
        if 'device' in kwargs:
            self._device = kwargs['device']
        if 'dev_cmd' in kwargs:
            self._construct_insteon_send(kwargs['dev_cmd'])

    def _construct_insteon_send(self,dev_cmd):
        msg_flags = self._construct_msg_flags(dev_cmd)
        self._parent._insert_byte_into_raw(msg_flags,'msg_flags')
        self._parent._insert_byte_into_raw(self.device.dev_id_hi,'to_addr_hi')
        self._parent._insert_byte_into_raw(self.device.dev_id_mid,'to_addr_mid')
        self._parent._insert_byte_into_raw(self.device.dev_id_low,'to_addr_low')
        # Process functions if they exist
        keys = ('cmd_1', 'cmd_2', 'usr_1', 'usr_2', 'usr_3', 'usr_4', 'usr_5', 'usr_6',
         'usr_7', 'usr_8', 'usr_9', 'usr_10', 'usr_11', 'usr_12', 'usr_13', 'usr_14')
        #could shorten this by just searching for callable keys in command
        for key in keys:
            if key in dev_cmd and callable(dev_cmd[key]):
                value = dev_cmd[key](self.device)
                self._parent._insert_byte_into_raw(value,key)
            elif key in dev_cmd:
                self._parent._insert_byte_into_raw(dev_cmd[key],key)
        self._device_cmd_name = dev_cmd['name']

    def _construct_msg_flags(self,dev_cmd):
        msg_types = {
            'broadcast'             : 4,
            'direct'                : 0,
            'direct_ack'            : 1,
            'direct_nack'           : 5,
            'alllink_broadcast'     : 6,
            'alllink_cleanup'       : 2, 
            'alllink_cleanup_ack'   : 3,
            'alllink_cleanup_nack'  : 7,
        }
        msg_flags = msg_types[dev_cmd['message_type']]
        msg_flags = msg_flags << 5
        if dev_cmd['msg_length'] == 'extended':
            msg_flags = msg_flags | 16
        hops_left = self.device.smart_hops << 2
        msg_flags = msg_flags | hops_left
        msg_flags = msg_flags | self.device.smart_hops
        return msg_flags

    @property
    def device(self):
        return self._device

    @property
    def device_retry(self):
        return self._device_retry

    @device_retry.setter
    def device_retry(self,count):
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
                4:'broadcast',
                0:'direct',
                1:'direct_ack',
                5:'direct_nack',
                6:'alllink_broadcast',
                2:'alllink_cleanup',
                3:'alllink_cleanup_ack',
                7:'alllink_cleanup_nack'
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

    @property
    def max_hops(self):
        msg_flags = self._parent.get_byte_by_name('msg_flags')
        ret = False
        if msg_flags:
            ret = msg_flags & 0b00000011
        return ret

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
    def device_ack(self,boolean):
        self._device_ack = boolean

class Device(Base_Device):
    def __init__(self, core, plm, **kwargs):
        super().__init__(core, plm)
        self._dev_id_str_to_bytes(kwargs['device_id'])
        self.dev_cat = 0x01
        self.sub_cat = 0x20
        self.firmware = ''
        self.last_msg = ''
        self._aldb_delta = ''
        self.status = ''
        self._msb = ''
        self._lsb = ''
        self.aldb = {}
        self._recent_inc_msgs = {}
        self._hop_array = []

    @property
    def msb(self):
        return self._msb

    @property
    def lsb(self):
        return self._lsb

    @property
    def device_id_str(self):
        return BYTE_TO_HEX(bytes([self._dev_id_hi,self._dev_id_mid,self._dev_id_low]))

    def _dev_id_str_to_bytes(self, dev_id_str):
        self._dev_id_hi = int(dev_id_str[0:2], 16)
        self._dev_id_mid = int(dev_id_str[2:4], 16)
        self._dev_id_low = int(dev_id_str[4:6], 16)

    @property
    def dev_id_hi(self):
        return self._dev_id_hi

    @property
    def dev_id_mid(self):
        return self._dev_id_mid

    @property
    def dev_id_low(self):
        return self._dev_id_low

    def msg_rcvd(self,msg):
        if self._is_duplicate(msg):
            print ('Skipped duplicate msg')
            return
        if msg.insteon_msg.message_type == 'direct_ack':
            self._process_direct_ack(msg)
        elif msg.insteon_msg.message_type == 'broadcast':
            self._set_plm_wait(msg)
            self.dev_cat = msg.get_byte_by_name('to_addr_hi')
            self.sub_cat = msg.get_byte_by_name('to_addr_mid')
            self.firmware = msg.get_byte_by_name('to_addr_low')
            print('was broadcast')

    def _process_direct_ack(self,msg):
        '''processes an incomming direct ack message'''
        self._set_plm_wait(msg, True)
        self._add_to_hop_tracking(msg)
        if not self._is_valid_direct_ack(msg):
            return
        elif self.last_msg.insteon_msg.device_cmd_name == 'light_status_request':
            print('was status response')
            self._aldb_delta = msg.get_byte_by_name('cmd_1')
            self.status = msg.get_byte_by_name('cmd_2')
            self.last_msg.insteon_msg.device_ack = True
        elif msg.get_byte_by_name('cmd_1') in STD_DIRECT_ACK_SCHEMA:
            command = STD_DIRECT_ACK_SCHEMA[msg.get_byte_by_name('cmd_1')]
            search_list = [
                ['DevCat'    , self.dev_cat],
                ['SubCat'    , self.sub_cat],
                ['Firmware'  , self.firmware],
                ['Cmd2'      , self.last_msg.get_byte_by_name('cmd_2')]
            ]
            for search_item in search_list:
                command = self._recursive_search_cmd(command,search_item)
                if not command:
                    print('not sure how to respond to this')
                    return
            command(self,msg)
            self.last_msg.insteon_msg.device_ack = True
        elif self.last_msg.get_byte_by_name('cmd_1') == msg.get_byte_by_name('cmd_1'):
            print('rcvd un coded ack')
            self.last_msg.insteon_msg.device_ack = True
        else:
            print('ignoring an unmatched ack')
            pprint.pprint(msg.__dict__)

    def _is_valid_direct_ack(self,msg):
        ret = True
        if self.last_msg.plm_ack != True:
            print ('ignoring a device ack received before PLM ack')
            ret = False
        elif self.last_msg.insteon_msg.device_ack != False:
            print ('ignoring an unexpected device ack')
            ret = False
        return ret

    def _add_to_hop_tracking(self,msg):
        hops_used = msg.insteon_msg.max_hops - msg.insteon_msg.hops_left
        self._hop_array.append(hops_used)
        extra_data = len(self._hop_array) - 10
        if extra_data > 0:
            self._hop_array = self._hop_array[extra_data:]

    @property
    def smart_hops(self):
        if len(self._hop_array):
            avg = sum(self._hop_array) / float(len(self._hop_array))
        else:
            avg = 3
        return math.ceil(avg)

    def _set_plm_wait(self,msg,is_extra_slow = False):
        # These numbers come from real world use
        hop_delay = 87 if msg.insteon_msg.msg_length == 'standard' else 183
        total_delay = hop_delay * msg.insteon_msg.hops_left
        if is_extra_slow:
            #Primarily used for Direct Ack messages where we want to ensure
            #accurate data.  We add an extra delay assuming a complete resend
            #of the prior message with +1 hops, as if the PLM ACK was never
            #received by the device
            total_delay += hop_delay * (msg.insteon_msg.max_hops + 1) * 2
        expire_time = time.time() + (total_delay / 1000)
        self.plm.wait_to_send = expire_time

    def _is_duplicate(self,msg):
        '''Checks to see if this is a duplicate message'''
        ret = None
        self._clear_stale_dupes()
        if self._is_msg_in_recent(msg):
            ret = True
        else:
            self._store_msg_in_recent(msg)
            ret = False
        return ret

    def _clear_stale_dupes(self):
        current_time = time.time()
        msgs_to_delete = []
        for msg, wait_time in self._recent_inc_msgs.items():
            if wait_time < current_time:
                msgs_to_delete.append(msg)
        for msg in msgs_to_delete:
            del self._recent_inc_msgs[msg]

    def _get_search_key(self,msg):
        #Zero out max_hops and hops_left
        #arguable whether this should be done in the Insteon_Message class
        search_bytes = msg.raw_msg
        search_bytes[8] = search_bytes[8] & 0b11110000
        return BYTE_TO_HEX(search_bytes)

    def _is_msg_in_recent(self,msg):
        search_key = self._get_search_key(msg)
        if search_key in self._recent_inc_msgs:
            return True

    def _store_msg_in_recent(self,msg):
        search_key = self._get_search_key(msg)
        # These numbers come from real world use
        hop_delay = 87 if msg.insteon_msg.msg_length == 'standard' else 183
        total_delay = hop_delay * msg.insteon_msg.hops_left
        expire_time = time.time() + (total_delay / 1000)
        self._recent_inc_msgs[search_key] = expire_time

    def send_command(self, command_name, state = ''):
        try:
            cmd_schema = COMMAND_SCHEMA[command_name]
        except Exception as e:
            print('command not found', e)
            return False
        search_list = [
            ['DevCat'    , self.dev_cat],
            ['SubCat'    , self.sub_cat],
            ['Firmware'  , self.firmware]
        ]
        for search_item in search_list:
            cmd_schema = self._recursive_search_cmd(cmd_schema,search_item)
            if not cmd_schema:
                print('command not available for this device')
                return False
        command = cmd_schema.copy()
        command['name'] = command_name
        message = PLM_Message(self._core, device=self, plm_cmd='insteon_send', dev_cmd=command)
        self._queue_device_msg(message, state)

    def _recursive_search_cmd (self,command,search_item):
        unique_cmd = ''
        catch_all_cmd = ''
        for command_item in command:
            if isinstance(command_item[search_item[0]], tuple):
                if search_item[1] in command_item[search_item[0]]:
                    unique_cmd = command_item['value']
            elif command_item[search_item[0]] == 'all':
                catch_all_cmd = command_item['value']
        if unique_cmd != '':
            return unique_cmd
        elif catch_all_cmd != '':
            return catch_all_cmd
        else:
            return False

    def query_aldb (self):
        self._msb = 0x0F
        self._lsb = 0xF8
        self.send_command('set_address_msb', 'query_aldb')

    def _get_aldb_key(self):
        offset = 7 - (self.lsb % 8)
        highest_byte = self.lsb + offset
        key = bytes([self.msb, highest_byte])
        return BYTE_TO_HEX(key)
    
    def ack_set_msb (self, msg):
        '''currently called when set_address_msb ack received'''
        if self.state_machine == 'query_aldb' and \
           self.msb == msg.get_byte_by_name('cmd_2'):
            self.peek_aldb()

    def ack_peek_aldb(self,msg):
        if self.state_machine == 'query_aldb' and \
           self.last_msg.insteon_msg.device_cmd_name == 'peek_one_byte':
            if (self.lsb % 8) == 0:
                self.aldb[self._get_aldb_key()] = bytearray(8)
            self.aldb[self._get_aldb_key()][self.lsb % 8] = msg.get_byte_by_name('cmd_2')
            if self.is_last_aldb(self._get_aldb_key()):
                #this is the last entry on this device
                for key in sorted(self.aldb):
                    print (key, ":", BYTE_TO_HEX(self.aldb[key]))
                self.remove_state_machine('query_aldb')
            elif self.is_empty_aldb(self._get_aldb_key()):
                #this is an empty record
                print('empty record')
                self._lsb = self.lsb - (8 + (self.lsb % 8))
                self.peek_aldb()
            elif self.lsb == 7:
                #Change MSB
                self._msb -= 1
                self._lsb = 0xF8
                self.send_command('set_address_msb', 'query_aldb')
            elif (self.lsb % 8) == 7:
                self._lsb -= 15
                self.peek_aldb()
            else:
                self._lsb += 1
                self.peek_aldb()

    def is_last_aldb(self,key):
        ret = True
        if self.aldb[key][0] & 0b00000010:
            ret = False
        return ret

    def is_empty_aldb(self,key):
        ret = True
        if self.aldb[key][0] & 0b10000000:
            ret = False
        return ret

    def peek_aldb (self):
        self.send_command('peek_one_byte', 'query_aldb')

class X10_Device(Base_Device):
    def __init__(self, core, plm, **kwargs):
        super().__init__(core, plm)
        self.status = ''
        self._byte_address = kwargs['byte_address']

    def send_command(self, command, state = ''):
        if command.lower() in CMD_TO_BYTE:
            if state == '':
                state = command
            plm_bytes = {'raw_x10':self._byte_address, 'x10_flags':0x00}
            message = PLM_Message(self.core, device=self, plm_cmd='x10_send', plm_bytes=plm_bytes)
            self._queue_device_msg(message, state)
            self.plm.store_x10_address(self._byte_address)
            plm_bytes = {
                'raw_x10':self.house_byte | CMD_TO_BYTE[command.lower()], 
                'x10_flags':0x80
            }
            message = PLM_Message(self.core, device=self, plm_cmd='x10_send', plm_bytes=plm_bytes)
            self._queue_device_msg(message, state)
            self.status = command.lower()
        else:
            print("Unrecognized command " , command)

    @property
    def house_byte(self):
        return self._byte_address & 0b11110000

    def inc_x10_msg(self,msg):
        x10_cmd_code = msg.get_byte_by_name('raw_x10') & 0b00001111
        for cmd_name, value in CMD_TO_BYTE.items():
            if value == x10_cmd_code:
                break
        self.status = cmd_name;
        print('received X10 message, setting to state ', self.status)