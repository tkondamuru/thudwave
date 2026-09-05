"""
Interactive Whiteboard Projector Server (macOS Edition)
Provides:
1. Static web game hosting (HTML5 Canvas & Web Audio) from /web.
2. Real-time Server-Sent Events (SSE) on /events for zero-latency ball impacts.
3. Whiteboard 4-pin corner calibration persistence (/calibration) to projector_calibration.json.
4. Camera tracker status broadcast (/tracker_status) to show identified markers on projector.

Zero external dependencies - 100% Python 3 Standard Library!
"""

import http.server
import socketserver
import threading
import json
import time
import os
import sys
import queue

try:
    from queue import Empty
except ImportError:
    class Empty(Exception): pass

try:
    import _queue
    _Empty = _queue.Empty
except Exception:
    _Empty = Empty

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')
CALIBRATION_FILE = os.path.join(BASE_DIR, 'projector_calibration.json')

# Thread-safe queue of connected SSE clients (browser canvas)
client_queues = []
clients_lock = threading.Lock()
shutdown_event = threading.Event()

class ProjectorServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        if shutdown_event.is_set():
            return
        super().handle_error(request, client_address)

class ProjectorHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """
    Lightweight HTTP & SSE server for macOS.
    Serves static canvas game from /web and broadcasts impact events over /events.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        if self.path == '/events':
            # Server-Sent Events (SSE) Stream
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            q = queue.Queue()
            with clients_lock:
                client_queues.append(q)

            last_ping = time.time()
            try:
                # Send initial connection event
                self.wfile.write(b"data: {\"event\": \"CONNECTED\"}\n\n")
                self.wfile.flush()

                while not shutdown_event.is_set():
                    try:
                        msg = q.get(timeout=0.5)
                        if msg is None:
                            break
                        payload = f"data: {json.dumps(msg)}\n\n".encode('utf-8')
                        self.wfile.write(payload)
                        self.wfile.flush()
                    except (Empty, _Empty, queue.Empty):
                        if shutdown_event.is_set():
                            break
                        now = time.time()
                        if now - last_ping >= 10.0:
                            last_ping = now
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                    except Exception:
                        break
            except Exception:
                pass
            finally:
                with clients_lock:
                    if q in client_queues:
                        client_queues.remove(q)

        elif self.path == '/calibration':
            # Returns saved 4-corner pin calibration
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            if os.path.exists(CALIBRATION_FILE):
                try:
                    with open(CALIBRATION_FILE, 'rb') as f:
                        self.wfile.write(f.read())
                    return
                except Exception:
                    pass
            self.wfile.write(b'{"corners": null}')

        elif self.path.startswith('/hit'):
            # Trigger hit event via HTTP GET /hit?x=0.45&y=0.60&num=1
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            nx = float(query.get('x', [0.5])[0])
            ny = float(query.get('y', [0.5])[0])
            hit_num = int(query.get('num', [1])[0]) if 'num' in query else None
            broadcast_hit(nx, ny, hit_num)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        elif self.path.startswith('/tracker_status'):
            # Broadcast ArUco identification status from Python tracker to browser
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            markers_str = query.get('markers', [''])[0]
            is_locked = query.get('locked', ['0'])[0] in ['1', 'true', 'True']
            markers = [int(m) for m in markers_str.split(',') if m.strip().isdigit()]
            msg = query.get('msg', [''])[0]
            event = {
                "event": "TRACKER_STATUS",
                "markers": sorted(markers),
                "count": len(markers),
                "locked": is_locked,
                "message": msg,
                "timestamp_ms": int(time.time() * 1000)
            }
            with clients_lock:
                for q in client_queues:
                    q.put(event)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        else:
            # Serve index.html or other static files from /web
            super().do_GET()

    def do_POST(self):
        if self.path == '/calibration':
            # Save 4-corner pin calibration to projector_calibration.json
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode('utf-8'))
                with open(CALIBRATION_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(b'{"status": "saved"}')
                print("  [Calibration] Saved pin positions to projector_calibration.json")
                return
            except Exception:
                self.send_response(400)
                self.end_headers()
                return
        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        # Silence routine HTTP requests
        return

def broadcast_hit(nx, ny, hit_num=None):
    """
    Broadcasts a physical ball impact to all connected projector browsers.
    Coordinates (nx, ny) are normalized [0.0 to 1.0] relative to whiteboard bounds.
    """
    event = {
        "event": "HIT",
        "nx": max(0.0, min(1.0, float(nx))),
        "ny": max(0.0, min(1.0, float(ny))),
        "hit_num": hit_num,
        "timestamp_ms": int(time.time() * 1000)
    }
    with clients_lock:
        for q in client_queues:
            q.put(event)

def start_projector_server(port=PORT):
    server = ProjectorServer(('0.0.0.0', port), ProjectorHTTPHandler)

    print("\n" + "=" * 60)
    print(" 📽️  INTERACTIVE WHITEBOARD PROJECTOR SERVER (macOS)")
    print("=" * 60)
    print(f" • Projector Display URL: http://localhost:{port}")
    print(f" • Calibration Config:   {CALIBRATION_FILE}")
    print(f" • Static Web Directory:  {WEB_DIR}")
    print("\n👉 Open in browser on Magcubic Projector: http://localhost:8000")
    print("   Press [C] on canvas anytime to toggle Calibration / Game Mode")
    print("=" * 60 + "\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping projector server...")
    finally:
        shutdown_event.set()
        with clients_lock:
            for q in client_queues:
                q.put(None)
        server.server_close()
        print("Projector server stopped cleanly.")

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else PORT
    start_projector_server(port)
