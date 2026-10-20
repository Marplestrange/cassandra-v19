import http.server
import socketserver
import os

class DevHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"{self.address_string()} - - [{self.log_date_time_string()}] {format%args}")

    def translate_path(self, path):
        original_path = path
        if '?' in path:
            path = path.split('?')[0]
            
        print(f"REQUEST PATH: {path}")

        if path == '/interface/CN_index.html' or path == '/':
            res = os.path.abspath('interface/CN_index.html')
            print(f" -> {res}")
            return res

        if path.startswith('/routes/'):
            base = path.replace('/routes/', '')
            cn_path = f"interface/routes/CN_{base}"
            if os.path.exists(cn_path):
                print(f" -> {os.path.abspath(cn_path)}")
                return os.path.abspath(cn_path)
            int_path = f"interface/routes/{base}"
            if os.path.exists(int_path):
                print(f" -> {os.path.abspath(int_path)}")
                return os.path.abspath(int_path)

        if path.startswith('/'):
            base = path[1:]
            
            if not base.startswith('interface/') and not base.startswith('CN_') and base.endswith('.js'):
                cn_path = f"interface/CN_{base}"
                if os.path.exists(cn_path):
                    print(f" -> {os.path.abspath(cn_path)}")
                    return os.path.abspath(cn_path)
                    
            if base.startswith('interface/'):
                base = base.replace('interface/', '')
                
            if not base.startswith('CN_') and '/' not in base:
                cn_path = f"interface/CN_{base}"
                if os.path.exists(cn_path):
                    print(f" -> {os.path.abspath(cn_path)}")
                    return os.path.abspath(cn_path)

            int_path = f"interface/{base}"
            if os.path.exists(int_path):
                print(f" -> {os.path.abspath(int_path)}")
                return os.path.abspath(int_path)

        res = super().translate_path(original_path)
        print(f" -> DEFAULT: {res}")
        return res

if __name__ == '__main__':
    PORT = 9002
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("", PORT), DevHandler)
    print(f"Serveur de dev Playwright sur le port {PORT}")
    httpd.serve_forever()
