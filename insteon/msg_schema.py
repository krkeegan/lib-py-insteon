'''
This schema defines all of the possible messages which can be received or
sent to the PLM.  The format of the schema is as follows, items in <> 
must be defined

{
    '<the plm byte prefix without 0x02>' : {
        'rcvd_len' : tuple - first value is standard message length,
                             second value is extended message length
        'name' : string - string suitable for use as a variable
        'recv_act' : function (obj, msg)
                        obj = the object on which the action should be run
                        msg = the message object
                        This function is the received action that should be
                        performed on the arrival of a message
        'recv_obj' : function (self)
                        self = the message object
                        Returns the object on which the recv_act should be
                        performed on
        'recv_byte_pos' : {
            '<name>' : <int> - the name is a standardized description of the
                           byte.
                       The int, is the position of the byte within the bytearray
        }
    }
}

'''
PLM_SCHEMA = {
    0x50: {
        'rcvd_len' : (11,),
        'send_len' : (0,),
        'name'     : 'insteon_received',
        'recv_act' : lambda obj, msg: obj.msg_rcvd(msg),
        'recv_obj' : lambda self : self.plm.get_device_by_addr(self.insteon_msg.from_addr_str),
        'recv_byte_pos'    : {
            'from_addr_hi'  : 2,
            'from_addr_mid' : 3,
            'from_addr_low' : 4,
            'to_addr_hi'    : 5,
            'to_addr_mid'   : 6,
            'to_addr_low'   : 7,
            'msg_flags'     : 8,
            'cmd_1'         : 9,
            'cmd_2'         : 10
        }
    },
    0x51: {
        'rcvd_len' : (25,),
        'send_len' : (0,),
        'name'     : 'insteon_ext_received',
        'recv_act' : lambda obj, msg: obj.msg_rcvd(msg),
        'recv_obj' : lambda self : self.plm.get_device_by_addr(self.insteon_msg.from_addr_str),
        'recv_byte_pos'    : {
            'from_addr_hi'  : 2,
            'from_addr_mid' : 3,
            'from_addr_low' : 4,
            'to_addr_hi'    : 5,
            'to_addr_mid'   : 6,
            'to_addr_low'   : 7,
            'msg_flags'     : 8,
            'cmd_1'         : 9,
            'cmd_2'         : 10,
            'usr_1'         : 11,
            'usr_2'         : 12,
            'usr_3'         : 13,
            'usr_4'         : 14,
            'usr_5'         : 15,
            'usr_6'         : 16,
            'usr_7'         : 17,
            'usr_8'         : 18,
            'usr_9'         : 19,
            'usr_10'        : 20,
            'usr_11'        : 21,
            'usr_12'        : 22,
            'usr_13'        : 23,
            'usr_14'        : 24,
        }
    },
    0x52: {
        'rcvd_len' : (4,),
        'send_len' : (0,),
        'recv_act' : lambda obj, msg: obj.rcvd_x10(msg),
        'recv_obj' : lambda self : self.plm,
        'name'     : 'x10_received',
        'recv_byte_pos'    : {    
            'raw_x10'   : 2,
            'x10_flags' : 3,
        }
    },
    0x53: {
        'rcvd_len' : (10,),
        'send_len' : (0,),
        'name'     : 'all_link_complete',
        'recv_act' : lambda obj, msg: obj.rcvd_all_link_complete(msg),
        'recv_obj' : lambda self : self.plm,
        'recv_byte_pos'    : {
            'link_code'     : 2,
            'group'         : 3,
            'from_addr_hi'  : 4,
            'from_addr_mid' : 5,
            'from_addr_low' : 6,
            'dev_cat'       : 7,
            'sub_cat'       : 8,
            'firmware'      : 9,
        }
    },
    0x54: {
        'rcvd_len' : (3,),
        'send_len' : (0,),
        'recv_act' : lambda obj, msg: obj.rcvd_btn_event(msg),
        'recv_obj' : lambda self : self.plm,
        'name'     : 'plm_button_event',
        'recv_byte_pos'    : {    
            'btn_event' : 2,
        }
    },
    0x55: {
        'rcvd_len' : (2,),
        'send_len' : (0,),
        'recv_act' : lambda obj, msg: obj.rcvd_plm_reset(msg),
        'recv_obj' : lambda self : self.plm,
        'name'     : 'user_plm_reset',
        'recv_byte_pos'    : {
            # No other recv_byte_pos
        }
    },
    0x56: {
        'rcvd_len' : (7,),
        'send_len' : (0,),
        'name'     : 'all_link_clean_failed',
        'recv_act' : lambda obj, msg: obj.rcvd_all_link_clean_failed(msg),
        'recv_obj' : lambda self : self.plm,
        'recv_byte_pos'    : {
            'link_fail'     : 2,
            'group'         : 3,
            'fail_addr_hi'  : 4,
            'fail_addr_mid' : 5,
            'fail_addr_low' : 6,
        }
    },
    0x57: {
        'rcvd_len' : (10,),
        'send_len' : (0,),
        'recv_act' : lambda obj, msg: obj.rcvd_aldb_record(msg),
        'recv_obj' : lambda self : self.plm,
        'name'     : 'all_link_record',
        'recv_byte_pos'    : {
            'link_flags'    : 2,
            'group'         : 3,
            'dev_addr_hi'   : 4,
            'dev_addr_mid'  : 5,
            'dev_addr_low'  : 6,
            'data_1'        : 7,
            'data_2'        : 8,
            'data_3'        : 9,
        }
    },
    0x58: {
        'rcvd_len' : (3,),
        'send_len' : (0,),
        'recv_act' : lambda obj, msg: obj.rcvd_all_link_clean_status(msg),
        'recv_obj' : lambda self : self.plm,
        'name'     : 'all_link_clean_status',
        'recv_byte_pos'    : {
            'plm_resp'  : 2,
        }
    },
    0x60: {
        'rcvd_len' : (9,),
        'send_len' : (2,),        
        'name'     : 'plm_info',
        'recv_act' : lambda obj, msg: obj.plm_info(msg),
        'recv_obj' : lambda self : self.plm,
        'recv_byte_pos'    : {
            'plm_addr_hi'   : 2,
            'plm_addr_mid'  : 3,
            'plm_addr_low'  : 4,
            'dev_cat'       : 5,
            'sub_cat'       : 6,
            'firmware'      : 7,
            'plm_resp'      : 8
        },
        'send_byte_pos'    : {
        }
    },
    0x61: {
        'rcvd_len' : (6,),
        'send_len' : (5,),
        'name'     : 'all_link_send',
        'recv_act' : lambda obj, msg: obj.rcvd_plm_ack(msg),
        'recv_obj' : lambda self : self.plm,
        'recv_byte_pos'    : {
            'group'     : 2,
            'cmd_1'     : 3,
            'cmd_2'     : 4,
            'plm_resp'  : 5
        },
        'send_byte_pos'    : {
            'group'     : 2,
            'cmd_1'     : 3,
            'cmd_2'     : 4,
        }
    },
    0x62: {
        'rcvd_len' : (9,23),
        'send_len' : (8,22),
        'name'     : 'insteon_send',
        'recv_act' : lambda obj, msg: obj.rcvd_plm_ack(msg),
        'recv_obj' : lambda self : self.plm,
        'recv_byte_pos'    : {
            'to_addr_hi'    : 2,
            'to_addr_mid'   : 3,
            'to_addr_low'   : 4,
            'msg_flags'     : 5,
            'cmd_1'         : 6,
            'cmd_2'         : 7,
            'plm_resp'      : 8,
            'usr_1'         : 8,
            'usr_2'         : 9,
            'usr_3'         : 10,
            'usr_4'         : 11,
            'usr_5'         : 12,
            'usr_6'         : 13,
            'usr_7'         : 14,
            'usr_8'         : 15,
            'usr_9'         : 16,
            'usr_10'        : 17,
            'usr_11'        : 18,
            'usr_12'        : 19,
            'usr_13'        : 20,
            'usr_14'        : 21,
            'plm_resp_e'    : 22,
        },
        'send_byte_pos'    : {
            'to_addr_hi'    : 2,
            'to_addr_mid'   : 3,
            'to_addr_low'   : 4,
            'msg_flags'     : 5,
            'cmd_1'         : 6,
            'cmd_2'         : 7,
            'usr_1'         : 8,
            'usr_2'         : 9,
            'usr_3'         : 10,
            'usr_4'         : 11,
            'usr_5'         : 12,
            'usr_6'         : 13,
            'usr_7'         : 14,
            'usr_8'         : 15,
            'usr_9'         : 16,
            'usr_10'        : 17,
            'usr_11'        : 18,
            'usr_12'        : 19,
            'usr_13'        : 20,
            'usr_14'        : 21,
        },
    },
    0x63: {
        'rcvd_len' : (5,),
        'send_len' : (4,),
        'recv_act' : lambda obj, msg: obj.rcvd_plm_x10_ack(msg),
        'recv_obj' : lambda self : self.plm,
        'name'     : 'x10_send',
        'recv_byte_pos'    : {
            'raw_x10'   : 2,
            'x10_flags' : 3,
            'plm_resp'  : 4,
        },
        'send_byte_pos'    : {
            'raw_x10'   : 2,
            'x10_flags' : 3,
        }
    },
    0x64: {
        'rcvd_len' : (5,),
        'name'     : 'all_link_start',
        'recv_byte_pos'    : {
            'link_code' : 2,
            'group'     : 3,
            'plm_resp'  : 4
        }
    },
    0x65: {
        'rcvd_len' : (3,),
        'name'     : 'all_link_cancel',
        'recv_byte_pos'    : {
            'plm_resp'  : 2,
        }
    },
    0x66: {
        'rcvd_len' : (6,),
        'name'     : 'set_host_device_cat',
        'recv_byte_pos'    : {
            'dev_cat'   : 2,
            'sub_cat'   : 3,
            'firmware'  : 4,
            'plm_resp'  : 5
        }
    },            
    0x67: {
        'rcvd_len' : (3,),
        'name'     : 'plm_reset',
        'recv_byte_pos'    : {
            'plm_resp'  : 2,
        }
    },
    0x68: {
        'rcvd_len' : (4,),
        'name'     : 'set_insteon_ack_cmd2',
        'recv_byte_pos'    : {
            'cmd_2'     : 2,
            'plm_resp'  : 3,
        }
    },
    0x69: {
        'rcvd_len' : (3,),
        'send_len' : (2,),
        'recv_act' : lambda obj, msg: obj.rcvd_plm_ack(msg),
        'recv_obj' : lambda self : self.plm,
        'name'     : 'all_link_first_rec',
        'recv_byte_pos'    : {
            'plm_resp'  : 2,
        },
        'send_byte_pos'    : {
        }
    },
    0x6A: {
        'rcvd_len' : (3,),
        'send_len' : (2,),
        'recv_act' : lambda obj, msg: obj.rcvd_plm_ack(msg),
        'recv_obj' : lambda self : self.plm,
        'nack_act' : lambda obj, msg: obj.end_of_aldb(msg),
        'name'     : 'all_link_next_rec',
        'recv_byte_pos'    : {
            'plm_resp'  : 2,
        },
        'send_byte_pos'    : {
        }
    },
    0x6B: {
        'rcvd_len' : (4,),
        'name'     : 'plm_set_config',
        'recv_byte_pos'    : {
            'conf_flags': 2,
            'plm_resp'  : 3
        }
    },
    0x6C: {
        'rcvd_len' : (3,),
        'name'     : 'get_sender_all_link_rec',
        'recv_byte_pos'    : {
            'plm_resp'  : 2,
        }
    },
    0x6D: {
        'rcvd_len' : (3,),
        'name'     : 'plm_led_on',
        'recv_byte_pos'    : {
            'plm_resp'  : 2,
        }
    },
    0x6E: {
        'rcvd_len' : (3,),
        'name'     : 'plm_led_off',
        'recv_byte_pos'    : {
            'plm_resp'  : 2,
        }
    },
    0x6F: {
        'rcvd_len' : (12,),
        'name'     : 'all_link_manage_rec',
        'recv_byte_pos'    : {
            'ctrl_code'     : 2,
            'link_flags'    : 3,
            'group'         : 4,
            'dev_addr_hi'   : 5,
            'dev_addr_mid'  : 6,
            'dev_addr_low'  : 7,
            'data_1'        : 8,
            'data_2'        : 9,
            'data_3'        : 10,
            'plm_resp'      : 11
        }
    },
    0x70: {
        'rcvd_len' : (4,),
        'name'     : 'insteon_nak',
        'recv_byte_pos'    : {
            'cmd_1'     : 2,
            'cmd_2'     : 3,
            'plm_resp'  : 4,
        }
    },
    0x71: {
        'rcvd_len' : (4,),
        'name'     : 'insteon_ack',
        'recv_byte_pos'    : {
            'cmd_2'     : 2,
            'plm_resp'  : 3,
        }
    },
    0x72: {
        'rcvd_len' : (5,),
        'name'     : 'rf_sleep',
        'recv_byte_pos'    : {
            'cmd_1'     : 2,
            'cmd_2'     : 3,
            'plm_resp'  : 4,
        }
    },
    0x73: {
        'rcvd_len' : (6,),
        'send_len' : (2,),
        'name'     : 'plm_get_config',
        'recv_byte_pos'    : {
            'conf_flags': 2,
            'spare_1'   : 3,
            'spare_2'   : 4,
            'plm_resp'  : 5
        },
        'send_byte_pos'    : {
        }
    },
}

# I think the PLM processes all standard direct messages sent to it
STD_DIRECT_SCHEMA = {
}

# The acks that either contain data, or require subsequent action
STD_DIRECT_ACK_SCHEMA = {
    # The Cmd2 in this Schema is the Cmd2 sent to cause this direct_ack,
    # not the value of the Cmd2 in the ack
    0x0D : [
        {   'name'  : 'get_engine_version',
            'DevCat' : 'all',
            'value' : [
                {   'SubCat' : 'all', 
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : 'all',
                                    'value' : lambda x, y : x._set_engine_version(y)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    # 19 also contains data, but Cmd1 is dynamic (stupid Insteon)
    0x1F : [
        {   'name' :'get_operating_flags', 
            'DevCat' : ('00'),
            'value' : [
                {   'SubCat' : ('04', #2430-ControLinc
                                '06', #2830-Icon Tabletop Controller
                               ),
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : ('00'),
                                    'value' : {                        
                                        0 : lambda x, y : x.program_lock(y),
                                        1 : lambda x, y : x.led_on_transmit(y),
                                        2 : lambda x, y : x.key_beep(y),
                                    }
                                },
                                {   'Cmd2' : ('01'),
                                    'value' : lambda x, y : x.aldb_delta(y)
                                }
                            ]
                        }
                    ]
                },
                {   'SubCat' : ('05', #2440-RemoteLinc
                               ),
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : ('00'),
                                    'value' : {                        
                                        0 : lambda x, y : x.program_lock(y),
                                        1 : lambda x, y : x.led_on_transmit(y),
                                        2 : lambda x, y : x.key_beep(y),
                                        3 : lambda x, y : x.stay_awake(y),
                                        4 : lambda x, y : x.receive_only(y),
                                        5 : lambda x, y : x.disable_heartbeat(y),
                                    }
                                },
                                {   'Cmd2' : ('01'),
                                    'value' : lambda x, y : x.aldb_delta(y)
                                }
                            ]
                        }
                    ]
                }
            ]
        },
        {   'DevCat' : ('01'),
            'value' : [
                {   'SubCat' : ('09', #2486D-KeypadLinc Dimmer
                                '0A',  #2886D-Icon In Wall Controller
                               ),
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : ('00'),
                                    'value' : {                        
                                        0 : lambda x, y : x.program_lock(y),
                                        1 : lambda x, y : x.led_on_transmit(y),
                                        2 : lambda x, y : x.resume_dim(y),
                                        3 : lambda x, y : x.eight_keys(y),
                                        4 : lambda x, y : x.backlight(y),
                                        5 : lambda x, y : x.key_beep(y),
                                    }
                                },
                                {   'Cmd2' : ('01'),
                                    'value' : lambda x, y : x.aldb_delta(y)
                                }
                            ]
                        }
                    ]
                },
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : ('00'),
                                    'value' : {                        
                                        0 : lambda x, y : x.program_lock(y),
                                        1 : lambda x, y : x.led_on_transmit(y),
                                        2 : lambda x, y : x.resume_dim(y),
                                        4 : lambda x, y : x.backlight(y),
                                        5 : lambda x, y : x.load_sense(y),
                                    }
                                },
                                {   'Cmd2' : ('01'),
                                    'value' : lambda x, y : x.aldb_delta(y)
                                },
                                {   'Cmd2' : ('02'),
                                    'value' : lambda x, y : x.signal_to_noise(y)
                                },
                            ]
                        }
                    ]
                }
            ]
        },
        {   'DevCat' : ('02'),
            'value' : [
                {   'SubCat' : ('0F', #2486S-KeypandLinc Relay
                               ),
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : ('00'),
                                    'value' : {                        
                                        0 : lambda x, y : x.program_lock(y),
                                        1 : lambda x, y : x.led_on_transmit(y),
                                        2 : lambda x, y : x.resume_dim(y),
                                        3 : lambda x, y : x.eight_keys(y),
                                        4 : lambda x, y : x.backlight(y),
                                        5 : lambda x, y : x.key_beep(y),
                                    }
                                },
                                {   'Cmd2' : ('01'),
                                    'value' : lambda x, y : x.aldb_delta(y)
                                },
                                {   'Cmd2' : ('02'),
                                    'value' : lambda x, y : x.signal_to_noise(y)
                                },
                            ]
                        }
                    ]
                },
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : ('00'),
                                    'value' : {                        
                                        0 : lambda x, y : x.program_lock(y),
                                        1 : lambda x, y : x.led_on_transmit(y),
                                        2 : lambda x, y : x.resume_dim(y),
                                        4 : lambda x, y : x.backlight(y),
                                        5 : lambda x, y : x.load_sense(y),
                                    }
                                },
                                {   'Cmd2' : ('01'),
                                    'value' : lambda x, y : x.aldb_delta(y)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    0x28 : [
        {   'name' :'set_address_msb', 
            'DevCat' : 'all',
            'value' : [
                {   'SubCat' : 'all', 
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : 'all',
                                    'value' : lambda x, y : x.ack_set_msb(y)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    0x2B : [
        {   'name' :'peek_one_byte', 
            'DevCat' : 'all',
            'value' : [
                {   'SubCat' : 'all', 
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : 'all',
                                    'value' : lambda x, y : x.ack_peek_aldb(y)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    0x2C : [ 
        {   'name' :'peek_one_byte_internal', 
            'DevCat' : 'all',
            'value' : [
                {   'SubCat' : 'all', 
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : 'all',
                                    'value' : lambda x, y : x.peek_byte_internal(y)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    0x2F : [ 
        {   'name' :'ext_aldb_ack', #ACK is diff for std and ext sent messages
            'DevCat' : 'all',
            'value' : [
                {   'SubCat' : 'all', 
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : 'all',
                                    'value' : lambda x, y : None
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    0x44 : [ 
        {   'name' :'sprinkler_control', 
            'DevCat' : 'all',
            'value' : [
                {   'SubCat' : 'all', 
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : ('02'),
                                    'value' : lambda x, y : x.valve_status(y)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    0x6A : [ 
        {   'name' :'thermostat_get_zone_info', 
            'DevCat' : 'all',
            'value' : [
                {   'SubCat' : 'all', 
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : ('02'),
                                    'value' : lambda x, y : x.zone_info(y)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    0x6B : [ 
        {   'name' :'thermostat_control', 
            'DevCat' : ('05'), # Thermostat
            'value' : [
                {   'SubCat' : 'all', 
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : ('02'),
                                    'value' : lambda x, y : x.thermo_mode(y),
                                },
                                {   'Cmd2' : ('03'),
                                    'value' : lambda x, y : x.thermo_ambient(y),
                                },
                                {   'Cmd2' : ('0D'),
                                    'value' : lambda x, y : x.thermo_equip_state(y),
                                },
                                {   'Cmd2' : ('0F'),
                                    'value' : lambda x, y : x.thermo_get_temp(y),
                                },
                                {   'Cmd2' : ('12'),
                                    'value' : lambda x, y : x.fan_speed(y)
                                },
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}

#Extended Direct Messages
EXT_DIRECT_SCHEMA = {
    0x2F : [
        {   'name'  : 'aldb_entry',
            'DevCat' : 'all',
            'value' : [
                {   'SubCat' : 'all', 
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : [
                                {   'Cmd2' : (0x00,),
                                    'value' : lambda x, y : x._ext_aldb_rcvd(y)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    ]
}

# Outgoing message formats
COMMAND_SCHEMA = {
    #CmdName
    'product_data_request' : [
        {   'DevCat' : 'all',
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x03,
                                'cmd_2'   : 0x00,
                                'msg_length' : 'standard',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'get_engine_version' : [
        {   'DevCat' : 'all',
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x0D,
                                'cmd_2'   : 0x00,
                                'msg_length' : 'standard',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'light_status_request' : [
        {   'DevCat' : (0x01,0x02),
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x19,
                                'cmd_2'   : 0x00,
                                'msg_length' : 'standard',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'id_request' : [
        {   'DevCat' : 'all',
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x10,
                                'cmd_2'   : 0x00,
                                'msg_length' : 'standard',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'on' : [
        {   'DevCat' : (0x01,),
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x11,
                                'cmd_2'   : lambda x: x.desired_on_level,
                                'msg_length' : 'standard',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'on' : [
        {   'DevCat' : (0x02,),
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x11,
                                'cmd_2'   : 0xFF,
                                'msg_length' : 'standard',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'on_cleanup' : [
        {   'DevCat' : (0x01,0x02),
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x11,
                                'cmd_2'   : 0x00,
                                'msg_length' : 'standard',
                                'message_type' : 'alllink_cleanup'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'off' : [
        {   'DevCat' : (0x01,0x02),
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x13,
                                'cmd_2'   : 0x00,
                                'msg_length' : 'standard',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'off_cleanup' : [
        {   'DevCat' : (0x01,0x02),
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x13,
                                'cmd_2'   : 0x00,
                                'msg_length' : 'standard',
                                'message_type' : 'alllink_cleanup'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'set_address_msb' : [
        {   'DevCat' : 'all',
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   :0x28,
                                'cmd_2'   : lambda x: x.msb,
                                'msg_length' : 'standard',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'peek_one_byte' : [
        {   'DevCat' : 'all',
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x2B,
                                'cmd_2'   : lambda x: x.lsb,
                                'msg_length' : 'standard',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ],
    'read_aldb' : [
        {   'DevCat' : 'all',
            'value'  : [
                {   'SubCat' : 'all',
                    'value' : [
                        {   'Firmware' : 'all',
                            'value' : {
                                'cmd_1'   : 0x2F,
                                'cmd_2'   : 0x00,
                                'usr_1'   : 0x00, #Unused
                                'usr_2'   : 0x00, #Read ALDB
                                'usr_3'   : lambda x: x.msb, #Addr Hi
                                'usr_4'   : lambda x: x.lsb, #Addr Low
                                'usr_5'   : 0x01, #0x00 = All, 0x01 = 1 Record 
                                'usr_6'   : 0x00, #Unused
                                'usr_7'   : 0x00, #Unused
                                'usr_8'   : 0x00, #Unused
                                'usr_9'   : 0x00, #Unused
                                'usr_10'  : 0x00, #Unused
                                'usr_11'  : 0x00, #Unused
                                'usr_12'  : 0x00, #Unused
                                'usr_13'  : 0x00, #Unused
                                'usr_14'  : 0x00, #Unused
                                'msg_length' : 'extended',
                                'message_type' : 'direct'
                            }
                        }
                    ]
                }
            ]
        }
    ]
}