import threading
import pprint
import json

from bottle import route, run, Bottle


class Rest_Server(Bottle):
    '''The REST front end'''

    def __init__(self, core):
        super(Rest_Server, self).__init__()
        self._core = core
        self.route('/plms', callback=self.list_plms)

    def start(self):
        threading.Thread(target=self.run, kwargs=dict(
            host='localhost', port=8080, debug=True)).start()

    def list_plms(self):
        '''
Returns an object containin all of the plms.

**Example request**:

.. sourcecode:: http

  GET /plms HTTP/1.1
  Host: example.com
  Accept: application/json

**Example response**:

.. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
        "20F5F5": {
            "dev_cat": 3,
            "firmware": 155,
            "port": "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A501LCKJ-if00-port0",
            "port_active": false,
            "sub_cat": 21
        },
        "3C4DB9": {
            "dev_cat": 3,
            "firmware": 158,
            "port": "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A403KDV3-if00-port0",
            "port_active": true,
            "sub_cat": 21
        }
    }

:statuscode 200: no error
        '''
        plms = self._core.get_all_plms()
        ret = {}
        for plm in plms:
            ret[plm.dev_addr_str] = {
                'dev_cat': plm.dev_cat,
                'sub_cat': plm.sub_cat,
                'firmware': plm.firmware,
                'port': plm.port,
                'port_active': plm.port_active
            }
        return self.jsonify(ret)

    def jsonify(self, data):
        return json.dumps(data, indent=4, sort_keys=True)
