import math
import time

from .base_objects import Base_Device, ALDB, Group
from .msg_schema import *
from .message import PLM_Message, Insteon_Message
from .helpers import *

class Insteon_Device(Base_Device):
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
        elif msg.insteon_msg.message_type == 'alllink_cleanup_ack':
            #TODO set state of the device based on cmd acked
            # Clear queued cleanup messages if they exist
            self._remove_cleanup_msgs(msg)
            if self.last_msg and \
            self.last_msg.get_byte_by_name('cmd_1') == msg.get_byte_by_name('cmd_1') and \
            self.last_msg.get_byte_by_name('cmd_2') == msg.get_byte_by_name('cmd_2'):
                #Only set ack if this was sent by this device
                self.last_msg.insteon_msg.device_ack = True

    def _remove_cleanup_msgs(self,msg):
        cmd_1 = msg.get_byte_by_name('cmd_1')
        cmd_2 = msg.get_byte_by_name('cmd_2')
        for state, msgs in self._device_msg_queue.items():
            i = 0
            to_delete = []
            for msg in msgs:
                if msg.get_byte_by_name('cmd_1') == cmd_1 and \
                msg.get_byte_by_name('cmd_2') == cmd_2:
                    to_delete.append(i)
                i += 1
            for position in reversed(to_delete):
                del self._device_msg_queue[state][position]

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
        expire_time = (total_delay / 1000)
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

    def send_command(self, command_name, state = '', dev_bytes = {}):
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
        message = PLM_Message(self._core, device=self, plm_cmd='insteon_send', dev_cmd=command, dev_bytes=dev_bytes)
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
                self._aldb.edit_dev_record(self._get_aldb_key(),bytearray(8))
            self._aldb.edit_dev_record_byte(
                self._get_aldb_key(),
                self.lsb % 8, 
                msg.get_byte_by_name('cmd_2')
            )
            if self.is_last_aldb(self._get_aldb_key()):
                #this is the last entry on this device
                records = self._aldb.get_all_records()
                for key in sorted(records):
                    print (key, ":", BYTE_TO_HEX(records[key]))
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
        if self._aldb.get_record(key)[0] & 0b00000010:
            ret = False
        return ret

    def is_empty_aldb(self,key):
        ret = True
        if self._aldb.get_record(key)[0] & 0b10000000:
            ret = False
        return ret

    def peek_aldb (self):
        self.send_command('peek_one_byte', 'query_aldb')

