import serial
import time
import datetime

from .base_objects import Base_Device, ALDB, Group
from .message import PLM_Message
from .helpers import *
from .msg_schema import *

class PLM(Base_Device):
    def __init__(self, port, core):
        super().__init__(core, self)
        self._read_buffer = bytearray()
        self._last_msg = ''
        self._msg_queue = []
        self._wait_to_send = 0
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
        for number in range(0x01,0xFF):
            self.add_group(number)

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
                self.wait_to_send = .5
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
        if self._wait_to_send < time.time():
            self._wait_to_send = time.time()
        self._wait_to_send += value

    def process_inc_msg(self,raw_msg):
        now = datetime.datetime.now().strftime("%M:%S.%f")
        # No matter what, pause for a short period before sending to PLM
        self.wait_to_send = (20/1000)
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

    def send_command(self,command, state = '', plm_bytes = {}):
        message = PLM_Message(self.core, device=self, plm_cmd=command, plm_bytes=plm_bytes)
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
        if msg.seq_lock == True: 
            if msg.time_sent < time.time() - msg.seq_time:
                print(now, 'PLM sequence lock expired, moving on')
                msg.seq_lock = False
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
            if self._last_msg.seq_lock:
                ret = True
            elif not self._last_msg.plm_ack:
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
                    self.wait_to_send = .5
            elif msg.plm_resp_bad_cmd:
                print('PLM said bad command')
                self.wait_to_send = .5
        else:
            print('received spurious plm ack')

    def rcvd_plm_x10_ack(self,msg):
        #For some reason we have to slow down when sending X10 msgs to the PLM
        self.rcvd_plm_ack(msg)
        self.wait_to_send = .5

    def rcvd_aldb_record(self,msg):
        self.add_aldb_to_cache(msg.raw_msg[2:])
        self.send_command('all_link_next_rec', 'query_aldb')

    def add_aldb_to_cache(self,aldb):
        self._aldb.add_plm_record(aldb)

    def end_of_aldb(self,msg):
        self._last_msg.plm_ack = True
        self.remove_state_machine('query_aldb')
        print('reached the end of the PLMs ALDB')
        records = self._aldb.get_all_records()
        for key in sorted(records):
            print (key, ":", BYTE_TO_HEX(records[key]))

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
        self._aldb.clear_all_records()
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
                print('Received and X10 command for an unknown device')
        else:
            print("X10 Command House Code did not match expected House Code")
            print("Message ignored")

    def query_aldb (self):
        '''Queries the PLM for a list of the link records saved on
        the PLM and stores them in the cache'''
        self.send_command('all_link_first_rec', 'query_aldb')

    def send_group_cmd(self,group,cmd):
        '''Send an on/off command from a plm group'''
        plm_bytes = {
            'group'     : group,
            'cmd_1'     : cmd,
            'cmd_2'     : 0x00,
        }
        message = PLM_Message(self.core, device=self, plm_cmd='all_link_send', plm_bytes=plm_bytes)
        #Until all link status is complete, sending any other cmds to PLM
        #will cause it to abandon all link process
        message.seq_lock = True
        #TODO Calculate sequence lock time based on number of items in group
        message.seq_time = 5
        #Queue up indiv device cleanup messages
        self._queue_device_msg(message, 'all_link_send')
        records = self._aldb.search_for_records({
            'controller' : True,
            'group': group,
            'in_use': True
        })
        for position in records:
            linked_device = self._aldb.linked_device(position)
            # Queue a cleanup message on each device, this msg will
            # be cleared from the queue on receipt of a cleanup
            # ack
            ##TESTING ONLY, need to pick on or off
            linked_device.send_command('off_cleanup', '', {'cmd_2' : group})

    def rcvd_all_link_clean_status(self,msg):
        if self._last_msg.plm_cmd_type == 'all_link_send':
            self._last_msg.seq_lock = False
            if msg.plm_resp_ack:
                print('Send All Link - Success')
                self.remove_state_machine('all_link_send')
                #TODO do we update the device state here? or rely on arrival of
                #alllink_cleanup acks?  As it stands, our own alllink cleanups
                #will be sent if this msg is rcvd, but no official device alllink
                #cleanup arrives
            elif msg.plm_resp_nack:
                print('Send All Link - Error')
                #We don't remove the state machine, so that further
                #direct cleanups can use it
        else:
            print('Ignored spurious all link clean status')

    def rcvd_all_link_clean_failed(self,msg):
        print('A specific device faileled to ack the cleanup msg')
        #TODO ensure that this is marked as false in item list

