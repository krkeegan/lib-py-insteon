import math
import time
import pprint

from .base_objects import Base_Device, Device_ALDB
from .msg_schema import *
from .message import PLM_Message, Insteon_Message
from .helpers import *

class Insteon_Device(Base_Device):
    def __init__(self, core, plm, **kwargs):
        self._aldb = Device_ALDB(self)
        super().__init__(core, plm, **kwargs)
        id_bytes = ID_STR_TO_BYTES(kwargs['device_id'])
        self._dev_id_hi = id_bytes[0]
        self._dev_id_mid = id_bytes[1]
        self._dev_id_low = id_bytes[2]
        self.last_msg = ''
        self._recent_inc_msgs = {}
        if self.attribute('engine_version') is None:
            self.send_command('get_engine_version')
        if (self.attribute('dev_cat') is None or
                self.attribute('sub_cat') is None or
                self.attribute('firmware') is None):
            self.send_command('id_request')
        self.send_command('light_status_request')

    @property
    def device_id_str(self):
        ret = BYTE_TO_HEX(
            bytes([self._dev_id_hi,self._dev_id_mid,self._dev_id_low]))
        return ret

    @property
    def dev_id_hi(self):
        return self._dev_id_hi

    @property
    def dev_id_mid(self):
        return self._dev_id_mid

    @property
    def dev_id_low(self):
        return self._dev_id_low

    @property
    def smart_hops(self):
        if self.attribute('hop_array') is not None:
            avg = ( 
                    sum(self.attribute('hop_array')) /
                    float(len(self.attribute('hop_array')))
                  )
        else:
            avg = 3
        return math.ceil(avg)

    ###################################################################
    ## 
    ## Incoming Message Handling
    ##
    ###################################################################

    def msg_rcvd(self,msg):
        self._set_plm_wait(msg)
        if self._is_duplicate(msg):
            print ('Skipped duplicate msg')
            return
        if msg.insteon_msg.message_type == 'direct':
            self._process_direct_msg(msg)
        elif msg.insteon_msg.message_type == 'direct_ack':
            self._process_direct_ack(msg)
        elif msg.insteon_msg.message_type == 'direct_nack':
            self._process_direct_nack(msg)
        elif msg.insteon_msg.message_type == 'broadcast':
            self.attribute('dev_cat', msg.get_byte_by_name('to_addr_hi'))
            self.attribute('sub_cat', msg.get_byte_by_name('to_addr_mid'))
            self.attribute('firmware', msg.get_byte_by_name('to_addr_low'))
            print('rcvd, broadcast updated devcat, subcat, and firmware')
        elif msg.insteon_msg.message_type == 'alllink_cleanup_ack':
            #TODO set state of the device based on cmd acked
            # Clear queued cleanup messages if they exist
            self._remove_cleanup_msgs(msg)
            if (self.last_msg and 
                    self.last_msg.get_byte_by_name('cmd_1') == 
                    msg.get_byte_by_name('cmd_1') and 
                    self.last_msg.get_byte_by_name('cmd_2') == 
                    msg.get_byte_by_name('cmd_2')):
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

    def _process_direct_msg(self,msg):
        '''processes an incomming direct message'''
        self._add_to_hop_tracking(msg)
        if (msg.insteon_msg.msg_length == 'extended' and 
                msg.get_byte_by_name('cmd_1') in EXT_DIRECT_SCHEMA):
            command = EXT_DIRECT_SCHEMA[msg.get_byte_by_name('cmd_1')]
            search_list = [
                ['DevCat'    , self.attribute('dev_cat')],
                ['SubCat'    , self.attribute('sub_cat')],
                ['Firmware'  , self.attribute('firmware')],
                ['Cmd2'      , msg.get_byte_by_name('cmd_2')]
            ]
            for search_item in search_list:
                command = self._recursive_search_cmd(command,search_item)
                if not command:
                    print('not sure how to respond to this')
                    return
            command(self,msg)
        else:
            print('direct message, that I dont know how to handle')
            pprint.pprint(msg.__dict__)

    def _process_direct_ack(self,msg):
        '''processes an incomming direct ack message'''
        self._add_to_hop_tracking(msg)
        if not self._is_valid_direct_ack(msg):
            return
        elif (self.last_msg.insteon_msg.device_cmd_name == 
                'light_status_request'):
            print('was status response')
            aldb_delta = msg.get_byte_by_name('cmd_1')
            if self.state_machine == 'set_aldb_delta':
                self.attribute('aldb_delta', aldb_delta)
                self.remove_state_machine('set_aldb_delta')
            elif self.attribute('aldb_delta') != aldb_delta:
                print('aldb has changed, rescanning')
                self._aldb.query_aldb()
            #TODO, we want to change aldb_deltas that are at 0x00
            self.attribute('status',msg.get_byte_by_name('cmd_2'))
            self.last_msg.insteon_msg.device_ack = True
        elif (self.last_msg.get_byte_by_name('cmd_1') == 
                msg.get_byte_by_name('cmd_1')):
            if msg.get_byte_by_name('cmd_1') in STD_DIRECT_ACK_SCHEMA:
                command = STD_DIRECT_ACK_SCHEMA[msg.get_byte_by_name('cmd_1')]
                search_list = [
                    ['DevCat'    , self.attribute('dev_cat')],
                    ['SubCat'    , self.attribute('sub_cat')],
                    ['Firmware'  , self.attribute('firmware')],
                    ['Cmd2'      , self.last_msg.get_byte_by_name('cmd_2')]
                ]
                for search_item in search_list:
                    command = self._recursive_search_cmd(command,search_item)
                    if not command:
                        print('not sure how to respond to this')
                        return
                command(self,msg)
                self.last_msg.insteon_msg.device_ack = True
            else:
                print('rcvd ack, nothing to do')
                self.last_msg.insteon_msg.device_ack = True
        else:
            print('ignoring an unmatched ack')
            pprint.pprint(msg.__dict__)

    def _process_direct_nack(self,msg):
        '''processes an incomming direct nack message'''
        self._add_to_hop_tracking(msg)
        if not self._is_valid_direct_ack(msg):
            return
        elif (self.last_msg.get_byte_by_name('cmd_1') == 
                msg.get_byte_by_name('cmd_1')):
            if (self.attribute('engine_version') == 0x02 or
                self.attribute('engine_version') is None):
                cmd_2 = msg.get_byte_by_name('cmd_2')
                if cmd_2 == 0xFF:
                    print('nack received, senders ID not in database')
                    self.last_msg.insteon_msg.device_ack = True
                elif cmd_2 == 0xFE:
                    print('nack received, no load')
                    self.last_msg.insteon_msg.device_ack = True
                elif cmd_2 == 0xFD:
                    print('nack received, checksum is incorrect, resending')
                    self.plm.wait_to_send = 1
                    self._resend_msg(self.last_msg)
                elif cmd_2 == 0xFC:
                    print('nack received, Pre nack in case database search takes too long')
                    self.last_msg.insteon_msg.device_ack = True
                elif cmd_2 == 0xFB:
                    print('nack received, illegal value in command')
                    self.last_msg.insteon_msg.device_ack = True
                else:
                    print('device nack`ed the last command, no further details, resending')
                    self.plm.wait_to_send = 1
                    self._resend_msg(self.last_msg)
            else:
                print('device nack`ed the last command, resending')
                self.plm.wait_to_send = 1
        else:
            print('ignoring unmatched nack')

    def _is_valid_direct_ack(self,msg):
        ret = True
        if self.last_msg.plm_ack != True:
            print ('ignoring a device response received before PLM ack')
            ret = False
        elif self.last_msg.insteon_msg.device_ack != False:
            print ('ignoring an unexpected device response')
            ret = False
        return ret

    def _add_to_hop_tracking(self,msg):
        hops_used = msg.insteon_msg.max_hops - msg.insteon_msg.hops_left
        hop_array = self.attribute('hop_array')
        if hop_array is None:
            hop_array = []
        hop_array.append(hops_used)
        extra_data = len(hop_array) - 10
        if extra_data > 0:
            hop_array = hop_array[extra_data:]
        self.attribute('hop_array', hop_array)

    def _set_plm_wait(self,msg):
        # Wait for additional hops to arrive
        hop_delay = 50 if msg.insteon_msg.msg_length == 'standard' else 109
        total_delay = hop_delay * msg.insteon_msg.hops_left
        expire_time = (total_delay / 1000)
        # Force a 5 millisecond delay for all
        self.plm.wait_to_send = expire_time + (5/1000)

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

    def ack_set_msb (self, msg):
        '''currently called when set_address_msb ack received'''
        if (self.state_machine == 'query_aldb' and 
               (self.last_msg.get_byte_by_name('cmd_2') == 
                msg.get_byte_by_name('cmd_2'))
               ):
            self.peek_aldb()

    def ack_peek_aldb(self,msg):
        if self.state_machine == 'query_aldb' and \
           self.last_msg.insteon_msg.device_cmd_name == 'peek_one_byte':
            if (self._aldb.lsb % 8) == 0:
                self._aldb.edit_record(self._aldb._get_aldb_key(),bytearray(8))
            self._aldb.edit_record_byte(
                self._aldb._get_aldb_key(),
                self._aldb.lsb % 8, 
                msg.get_byte_by_name('cmd_2')
            )
            if self._aldb.is_last_aldb(self._aldb._get_aldb_key()):
                #this is the last entry on this device
                records = self._aldb.get_all_records()
                for key in sorted(records):
                    print (key, ":", BYTE_TO_HEX(records[key]))
                self.remove_state_machine('query_aldb')
                self.send_command('light_status_request', 'set_aldb_delta')
            elif self._aldb.is_empty_aldb(self._aldb._get_aldb_key()):
                #this is an empty record
                print('empty record')
                self._aldb.lsb = self._aldb.lsb - (8 + (self._aldb.lsb % 8))
                self.peek_aldb()
            elif self._aldb.lsb == 7:
                #Change MSB
                self._aldb.msb -= 1
                self._aldb.lsb = 0xF8
                self.send_command('set_address_msb', 'query_aldb')
            elif (self._aldb.lsb % 8) == 7:
                self._aldb.lsb -= 15
                self.peek_aldb()
            else:
                self._aldb.lsb += 1
                self.peek_aldb()

    def _ext_aldb_rcvd(self,msg):
        msg_msb = msg.get_byte_by_name('usr_3')
        msg_lsb = msg.get_byte_by_name('usr_4')
        if (self._aldb.lsb == 0x00 and self._aldb.msb == 0x00):
            self._aldb.lsb = msg_lsb
            self._aldb.msb = msg_msb
        elif (self._aldb.lsb != msg_lsb or self._aldb.msb != msg_msb):
            #this is not the record that we requested
            return
        aldb_entry = bytearray([
            msg.get_byte_by_name('usr_6'),
            msg.get_byte_by_name('usr_7'),
            msg.get_byte_by_name('usr_8'),
            msg.get_byte_by_name('usr_9'),
            msg.get_byte_by_name('usr_10'),
            msg.get_byte_by_name('usr_11'),
            msg.get_byte_by_name('usr_12'),
            msg.get_byte_by_name('usr_13')
        ])
        self._aldb.edit_record(self._aldb._get_aldb_key(),aldb_entry)
        self.last_msg.insteon_msg.device_ack = True
        if self.state_machine == 'query_aldb':
            if self._aldb.is_last_aldb(self._aldb._get_aldb_key()):
                self.remove_state_machine('query_aldb')
                #this is the last entry on this device
                records = self._aldb.get_all_records()
                for key in sorted(records):
                    print (key, ":", BYTE_TO_HEX(records[key]))
                self.send_command('light_status_request', 'set_aldb_delta')
            else:
                if self._aldb.lsb == 0x07:
                    self._aldb.msb -= 1
                    self._aldb.lsb = 0xFF
                else:
                    self._aldb.lsb -= 8
                self.send_command('read_aldb', 'query_aldb')

    def _set_engine_version(self,msg):
        version = msg.get_byte_by_name('cmd_2')
        if version >= 0xFB:
            #Insteon Hack
            #Some I2CS Devices seem to have a bug in that they ack
            #a message when they mean to nack it, but the cmd_2
            #value is still the correct nack reason
            self.attribute('engine_version', 0x02)
            self._process_direct_nack(msg)
        else:
            self.attribute('engine_version', version)

    ###################################################################
    ## 
    ## Outgoing Message Handling
    ##
    ###################################################################

    def send_command(self, command_name, state = '', dev_bytes = {}):
        try:
            cmd_schema = COMMAND_SCHEMA[command_name]
        except Exception as e:
            print('command not found', e)
            return False
        search_list = [
            ['DevCat'    , self.attribute('dev_cat')],
            ['SubCat'    , self.attribute('sub_cat')],
            ['Firmware'  , self.attribute('firmware')]
        ]
        for search_item in search_list:
            cmd_schema = self._recursive_search_cmd(cmd_schema,search_item)
            if not cmd_schema:
                #TODO figure out some way to allow queuing prior to dev cat?
                print('command not available for this device')
                return False
        command = cmd_schema.copy()
        command['name'] = command_name
        message = PLM_Message(self.plm, 
                              device=self, 
                              plm_cmd='insteon_send', 
                              dev_cmd=command, 
                              dev_bytes=dev_bytes)
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
    
    def peek_aldb (self):
        self.send_command('peek_one_byte', 'query_aldb')

    def write_aldb_record(self,msb,lsb):
        dev_bytes = {'usr_3' : msb, 'usr_4' : lsb}
        self.send_command('write_aldb', '', dev_bytes = dev_bytes)
    