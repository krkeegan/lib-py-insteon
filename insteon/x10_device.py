class X10_Device(Base_Device):

    def __init__(self, core, plm, **kwargs):
        super().__init__(core, plm)
        self.status = ''
        self._byte_address = kwargs['byte_address']

    def send_command(self, command, state=''):
        if command.lower() in CMD_TO_BYTE:
            if state == '':
                state = command
            plm_bytes = {'raw_x10': self._byte_address, 'x10_flags': 0x00}
            message = PLM_Message(self.plm,
                                  device=self,
                                  plm_cmd='x10_send',
                                  plm_bytes=plm_bytes)
            self._queue_device_msg(message, state)
            self.plm.store_x10_address(self._byte_address)
            plm_bytes = {
                'raw_x10': self.house_byte | CMD_TO_BYTE[command.lower()],
                'x10_flags': 0x80
            }
            message = PLM_Message(self.plm,
                                  device=self,
                                  plm_cmd='x10_send',
                                  plm_bytes=plm_bytes)
            self._queue_device_msg(message, state)
            self.status = command.lower()
        else:
            print("Unrecognized command ", command)

    @property
    def house_byte(self):
        return self._byte_address & 0b11110000

    def inc_x10_msg(self, msg):
        x10_cmd_code = msg.get_byte_by_name('raw_x10') & 0b00001111
        for cmd_name, value in CMD_TO_BYTE.items():
            if value == x10_cmd_code:
                break
        self.status = cmd_name
        print('received X10 message, setting to state ', self.status)
