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
        threading.Thread(target=self.run, kwargs=dict(host='localhost', port=8080, debug=True)).start()

    def list_plms(self):
        plms = self._core.get_all_plms()
        ret = {}
        for plm in plms:
            ret[plm.dev_addr_str] = {
                'dev_cat'       : plm.dev_cat,
                'sub_cat'       : plm.sub_cat,
                'firmware'      : plm.firmware,
                'port'          : plm.port,
                'port_active'   : plm.port_active
            }
        return self.jsonify(ret)

    def jsonify(self, data):
        return json.dumps(data, indent=4, sort_keys=True)
