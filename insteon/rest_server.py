import http.server


class HTTPHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/':
            self.send_html_headers()
            html = (
                '''
<html>
    <head>
        <title> Configuration </title>
    </head>
    <body>
'''
            )
            core = self.server.core
            plms = core.get_all_plms()
            html += "<h3>PLMS</h3>\n"
            for plm in plms:
                html += plm.device_id + "<br>\n"
                devices = plm.get_all_devices()
                html += "<h4>Devices</h4>\n"
                for device in devices:
                    html += device.device_id_str + "<br>\n"
            self.wfile.write(bytes(html, 'UTF-8'))
        return

    def send_html_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'html')
        self.end_headers()
