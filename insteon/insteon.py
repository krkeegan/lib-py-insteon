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
        for id, device in self.devices.items():
            device.process_device_queue()
        self.plm.process_queue()

    def add_device(self, device_id, **kwargs):
        #TODO better handle plm, should support multiple plms
        plm = self.plm
        if 'plm' in kwargs:
            plm = kwargs['plm']
        self.devices[device_id] = Device(self, plm, device_id=device_id)
        return self.devices[device_id]

class PLM(object):
    def __init__(self, port, core):
        self.core = core
        self._read_buffer = bytearray()
        self._last_msg = ''
        self._msg_queue = []
        self._wait_to_send = 0
        self._aldb = []
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
        msg = Insteon_Message(self.core, \
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
            except:
                # Use this to somehow keep messages in the queue??
                # Not sure that is really possible, won't we just end
                # up here again?
                pass
        else:
            print('received msg, but no action specified')
            pprint.pprint(msg.parsed)
        
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
        if msg_obj.details['plm_ack']:
            self.device_id = msg_obj.details['from_addr']
            self.dev_cat = msg_obj.details['dev_cat']
            self.sub_cat = msg_obj.details['sub_cat']
            self.firmware = msg_obj.details['firmware']

    def send_command(self,command):
        if command in PLM_COMMAND_SCHEMA:
            cmd_bytes = PLM_COMMAND_SCHEMA[command].copy()
            # This needs to get converted to a MSG object
        else:
            print("sorry I don't know the command", command)

    def process_unacked_msg(self):
        '''checks for unacked messages'''
        if self._is_ack_pending():
            msg = self._last_msg
        else:
            return
        # allow 75 milliseconds for the PLM to ack a message
        if msg.plm_ack == False: 
            if msg.time_sent < time.time() - (75/1000):
                print('PLM failed to ack the last message')
                if msg.plm_retry >= 3:
                    print('PLM retries exceeded, abandoning this message')
                    msg.failed = True
                else:
                    msg.plm_retry += 1
                    self._resend_msg()
            return
        if msg.device_ack == False:
            total_hops = msg.parsed['max_hops'] *2
            hop_delay = 87 if msg.parsed['msg_length'] == 'standard' else 183
            # These numbers come from real world use (87, 183)
            # 100ms for device to process the msg internally
            total_delay = total_hops * hop_delay + (100/1000)
            if msg.time_sent < time.time() - total_delay:
                print('device failed to ack a message')
                if msg.device_retry >= 3:
                    print('device retries exceeded, abandoning this message')
                    msg.failed = True
                else:
                    msg.device_retry += 1
                    self._resend_msg()
            return

    def process_queue(self):
        '''Sends the next message in the queue if there are no 
        conflicts'''
        if not self._is_ack_pending() and \
        self._msg_queue and \
        time.time() > self.wait_to_send:
            msg = self._msg_queue.pop(0)
            device = self.core.devices[msg.parsed['to_addr_str']]
            device.last_msg = msg
            self._send_msg(msg)

    def _is_ack_pending(self):
        ret = False
        if self._last_msg and \
           self._last_msg.failed != True and \
           (self._last_msg.plm_ack == False or \
           self._last_msg.device_ack == False):
            ret = True
        return ret

    def rcvd_plm_ack(self,msg):
        if self._last_msg.plm_ack == False\
        and msg.raw_msg[0:-1] == self._last_msg.raw_msg:
            if msg.raw_msg[-1] == 0x06:
                self._last_msg.plm_ack = True
            elif msg.raw_msg[-1] == 0x15:
                print('PLM sent NACK to last command')
                self.wait_to_send = time.time() + .5
            elif msg.raw_msg[-1] == 0x0F:
                print('PLM said bad command')
                self.wait_to_send = time.time() + .5
        else:
            print('received spurious plm ack')

class Insteon_Message(object):
    def __init__(self, core, **kwargs):
        self._core = core
        self._device_ack = False
        self._plm_ack = False
        self._is_incomming = False
        self._plm_retry = 0
        self._device_retry = 0
        self._failed = False
        if 'is_incomming' in kwargs:
            self._is_incomming = True
        if 'raw_data' in kwargs:
            self.msg_from_raw(kwargs['raw_data'])
        elif 'command' in kwargs:
            self.command_to_raw(kwargs['command'], kwargs['schema'])

    def msg_from_raw(self, data):
        self.parsed = {}
        self.parsed['prefix'] = data[1]
        self.plm_schema = PLM_SCHEMA[self.parsed['prefix']]
        self.parsed['plm_cmd_type'] = self.plm_schema['name']
        for attr, position in self.plm_schema['byte_pos'].items():
            if len(data) > position: 
                self.parsed[attr] = data[position]
        #Translate PLM Response Byte
        resp_type = 'plm_resp'
        if 'plm_resp_e' in self.parsed:
            resp_type = 'plm_resp_e'
        if resp_type in self.parsed:
            if self.parsed[resp_type] ==0x06:
                self.parsed['plm_ack'] = True
            elif self.parsed[resp_type] == 0x15:
                self.parsed['plm_nack'] = True
            elif self.parsed[resp_type] == 0x0F:
                self.parsed['plm_bad_cmd'] = True
        #Translate Insteon Msg Flag
        if 'msg_flags' in self.parsed:
            msg_flags = self.parsed['msg_flags']
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
            self.parsed['message_type'] = msg_types[message_type]
            self.parsed['msg_length'] = 'standard'
            if msg_flags & 16:
                self.parsed['msg_length'] = 'extended'
            hops_left = msg_flags & 0b00001100
            hops_left = hops_left >> 2
            self.parsed['hops_left'] = hops_left 
            max_hops = msg_flags & 0b00000011
            self.parsed['max_hops'] = max_hops
        #Translate device addresses
        if 'to_addr_hi' in self.parsed:
            to_addr = bytes((self.parsed['to_addr_hi'],self.parsed['to_addr_mid'],self.parsed['to_addr_low']))
            self.parsed['to_addr_str'] = BYTE_TO_HEX(to_addr)
        if 'from_addr_hi' in self.parsed:
            from_addr = bytes((self.parsed['from_addr_hi'],self.parsed['from_addr_mid'],self.parsed['from_addr_low']))
            self.parsed['from_addr_str'] = BYTE_TO_HEX(from_addr)

    def command_to_raw(self, command, schema):
        '''Takes a command dictionary and builds an Insteon
        message'''
        command['hops_left'] = command['max_hops']
        #TODO this is a bit sloppy
        command['message_type'] = schema['message_type']
        command['msg_length'] = schema['msg_length']
        #Construct the message flags
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
        msg_flags = msg_types[command['message_type']]
        msg_flags = msg_flags << 5
        if command['msg_length'] == 'extended':
            msg_flags = msg_flags | 16
        hops_left = command['hops_left'] << 2
        msg_flags = msg_flags | hops_left
        msg_flags = msg_flags | command['max_hops']
        command['msg_flags'] = msg_flags
        # Process functions if they exist
        device = self._core.devices[command['to_addr_str']]
        keys = ('cmd_1', 'cmd_2', 'usr_1', 'usr_2', 'usr_3', 'usr_4', 'usr_5', 'usr_6',
         'usr_7', 'usr_8', 'usr_9', 'usr_10', 'usr_11', 'usr_12', 'usr_13', 'usr_14')
        #could shorten this by just searching for callable keys in command
        for key in keys:
            if key in schema:
                if callable(schema[key]):
                    command[key] = schema[key](device)
                else:
                    command[key] = schema[key]
        self.parsed = command
        return self
    
    @property
    def raw_msg(self):
        #Construct the raw message
        cmd_structure = {}
        raw_msg = None
        for prefix in PLM_SCHEMA:
            if PLM_SCHEMA[prefix]['name'] == self.parsed['plm_cmd_type']:
                cmd_structure = PLM_SCHEMA[prefix]
                cmd_prefix = prefix
        if cmd_structure:
            #This looks a little sloppy
            msg_length = cmd_structure['send_len'][0]
            if self.parsed['msg_length'] == 'extended':
                msg_length = cmd_structure['send_len'][1]
            if self.is_incomming:
                msg_length = cmd_structure['rcvd_len'][0]
                if self.parsed['msg_length'] == 'extended':
                    msg_length = cmd_structure['rcvd_len'][1]
            raw_msg = bytearray(msg_length)
            raw_msg[0] = 0x02
            raw_msg[1] = cmd_prefix
            for attribute, position in cmd_structure['byte_pos'].items():
                try:
                    raw_msg[position] = self.parsed[attribute]
                except KeyError:
                    pass
        else:
            print("sorry I don't know that PLM command", self.parsed['plm_cmd_type'])
        return raw_msg

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
    def device_ack(self):
        return self._device_ack

    @device_ack.setter
    def device_ack(self,boolean):
        self._device_ack = boolean

    @property
    def core(self):
        return self._core

    @property
    def device_retry(self):
        return self._device_retry

    @device_retry.setter
    def device_retry(self,count):
        self._device_retry = count

    @property
    def plm_retry(self):
        return self._plm_retry

    @plm_retry.setter
    def plm_retry(self,count):
        self._plm_retry = count

class Device(object):
    def __init__(self, core, plm, **kwargs):
        self._core = core
        self._plm = plm
        self._dev_id_str_to_bytes(kwargs['device_id'])
        self.dev_cat = 0x01
        self.sub_cat = 0x20
        self.firmware = ''
        self.last_msg = ''
        self._aldb_delta = ''
        self.status = ''
        self._state_machine = 'default'
        self._state_machine_time = 0
        self._msb = ''
        self._lsb = ''
        self.aldb = {}
        self._recent_inc_msgs = {}
        self._msg_queue = {}
        self._hop_array = []

    @property
    def msb(self):
        return self._msb

    @property
    def lsb(self):
        return self._lsb

    @property
    def plm(self):
        return self._plm

    @property
    def device_id_str(self):
        return BYTE_TO_HEX(bytes([self._dev_id_hi,self._dev_id_mid,self._dev_id_low]))

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
        if self._state_machine_time <= (time.time() - 5) and \
        self._state_machine != 'default':
            print (self._state_machine, "state expired")
            self._state_machine = 'default'
            self._state_machine_time = time.time()
        return self._state_machine
    
    def remove_state_machine(self,value):
        if value == self.state_machine:
            print('finished', self.state_machine)
            self._state_machine = 'default'
            self._state_machine_time = time.time()
        else:
            print(value, 'was not the active state_machine')

    def _dev_id_str_to_bytes(self, dev_id_str):
        self._dev_id_hi = int(dev_id_str[0:2], 16)
        self._dev_id_mid = int(dev_id_str[2:4], 16)
        self._dev_id_low = int(dev_id_str[4:6], 16)

    def std_msg_rcvd(self,msg):
        if self._is_duplicate(msg):
            print ('Skipped duplicate msg')
            return
        # TODO add something to weed out unexpected ACKs
        if msg.parsed['message_type'] == 'direct_ack':
            self._process_direct_ack(msg)
        elif msg.parsed['message_type'] == 'broadcast':
            self._set_plm_wait(msg)
            self.dev_cat = msg.parsed['to_addr_hi']
            self.sub_cat = msg.parsed['to_addr_mid']
            self.firmware = msg.parsed['to_addr_low']
            print('was broadcast')

    def _process_direct_ack(self,msg):
        '''processes an incomming direct ack message'''
        self._set_plm_wait(msg, True)
        self._add_to_hop_tracking(msg)
        if not self._is_valid_direct_ack(msg):
            return
        elif self.last_msg.parsed['name'] == 'light_status_request':
            print('was status response')
            self._aldb_delta = msg.parsed['cmd_1']
            self.status = msg.parsed['cmd_2']
            self.last_msg.device_ack = True
        elif msg.parsed['cmd_1'] in STD_DIRECT_ACK_SCHEMA:
            command = STD_DIRECT_ACK_SCHEMA[msg.parsed['cmd_1']]
            search_list = [
                ['DevCat'    , self.dev_cat],
                ['SubCat'    , self.sub_cat],
                ['Firmware'  , self.firmware],
                ['Cmd2'      , self.last_msg.parsed['cmd_2']]
            ]
            for search_item in search_list:
                command = self._recursive_search_cmd(command,search_item)
                if not command:
                    print('not sure how to respond to this')
                    return
            command(self,msg)
            self.last_msg.device_ack = True
        elif self.last_msg.parsed['cmd_1'] == msg.parsed['cmd_1']:
            print('rcvd un coded ack')
            self.last_msg.device_ack = True
        else:
            print('ignoring an unmatched ack')
            pprint.pprint(msg.__dict__)

    def _is_valid_direct_ack(self,msg):
        ret = True
        if self.last_msg.plm_ack != True:
            print ('ignoring a device ack received before PLM ack')
            ret = False
        elif self.last_msg.device_ack != False:
            print ('ignoring an unexpected device ack')
            ret = False
        return ret

    def _add_to_hop_tracking(self,msg):
        hops_used = msg.parsed['max_hops'] - msg.parsed['hops_left']
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
        hop_delay = 87 if msg.parsed['msg_length'] == 'standard' else 183
        total_delay = hop_delay * msg.parsed['hops_left']
        if is_extra_slow:
            #Primarily used for Direct Ack messages where we want to ensure
            #accurate data.  We add an extra delay assuming a complete resend
            #of the prior message with +1 hops, as if the PLM ACK was never
            #received by the device
            total_delay += hop_delay * (msg.parsed['max_hops'] + 1) * 2
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
        hop_delay = 87 if msg.parsed['msg_length'] == 'standard' else 183
        total_delay = hop_delay * msg.parsed['hops_left']
        expire_time = time.time() + (total_delay / 1000)
        self._recent_inc_msgs[search_key] = expire_time

    def send_command(self, command_name, state = ''):
        command = {}
        try:
            cmd_schema = COMMAND_SCHEMA[command_name].copy()
        except:
            print('command not found')
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
        command['prefix'] = 0x62
        command['plm_cmd_type'] = 'insteon_send'
        command['name'] = command_name
        command['max_hops'] = self.smart_hops
        command['to_addr_str'] = self.device_id_str
        command['to_addr_hi'] = self._dev_id_hi
        command['to_addr_mid'] = self._dev_id_mid
        command['to_addr_low'] = self._dev_id_low
        message = Insteon_Message(self._core, command=command, schema=cmd_schema)
        self._queue_msg(message, state)

    def _queue_msg(self,message,state):
        if state == '': state = 'default'
        if state not in self._msg_queue:
            self._msg_queue[state] = []
        self._msg_queue[state].append(message)

    def process_device_queue(self):
        '''Sends the next message in the queue to the PLM if the state_machine
        is in the correct state'''
        next_state = False
        for state in self._msg_queue:
            if state != 'default':
                next_state = state
                break
        if self.state_machine != 'default' and \
        self._msg_queue[self.state_machine]:
            # Reset state_machine timer
            self._state_machine_time = time.time()
            msg = self._msg_queue[self.state_machine].pop(0)
            self.plm.queue_msg(msg)
        elif next_state and \
        self._msg_queue[next_state]:
            # Set new state_machine timer
            self._state_machine = next_state
            self._state_machine_time = time.time()
            msg = self._msg_queue[self.state_machine].pop(0)
            self.plm.queue_msg(msg)
        elif self.state_machine == 'default' and \
        'default' in self._msg_queue and \
        self._msg_queue['default']:
            msg = self._msg_queue['default'].pop(0)
            self.plm.queue_msg(msg)

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
           self.msb == msg.parsed['cmd_2']:
            self.peek_aldb()

    def ack_peek_aldb(self,msg):
        if self.state_machine == 'query_aldb' and \
           self.last_msg.parsed['name'] == 'peek_one_byte':
            if (self.lsb % 8) == 0:
                self.aldb[self._get_aldb_key()] = bytearray(8)
            self.aldb[self._get_aldb_key()][self.lsb % 8] = msg.parsed['cmd_2']
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
        