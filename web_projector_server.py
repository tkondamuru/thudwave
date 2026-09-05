"""
Interactive Whiteboard Projector Server
Provides:
1. Static web game hosting (HTML5 Canvas & Web Audio) from /web.
2. Real-time Server-Sent Events (SSE) on /events for ball impacts & lock state.
3. Ball impact receiver on /hit.
4. Tracker lock state receiver on /tracker_status (or /lock).
5. Whiteboard 4-pin corner calibration persistence on /calibration.

Zero external dependencies - 100% Python 3 Standard Library!
"""

import http.server
import json
import os
import queue
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, 'web')
CALIBRATION_FILE = os.path.join(BASE_DIR, 'projector_calibration.json')

# Thread-safe SSE client connections
client_queues = []
clients_lock = threading.Lock()
shutdown_event = threading.Event()

# Tracker lock state (manual [L] toggle in tracker)
is_locked = False
lock_state_lock = threading.Lock()


def broadcast_hit(nx, ny, hit_num=None):
    """Broadcasts a physical ball impact to all connected projector browsers."""
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


def broadcast_lock(locked):
    """Broadcasts whiteboard lock state (True/False) to all connected browsers."""
    global is_locked
    with lock_state_lock:
        is_locked = locked
    event = {
        "event": "TRACKER_STATUS",
        "locked": locked,
        "timestamp_ms": int(time.time() * 1000)
    }
    with clients_lock:
        for q in client_queues:
            q.put(event)


class ProjectorServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        if shutdown_event.is_set():
            return
        super().handle_error(request, client_address)


class ProjectorHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Lightweight HTTP & SSE handler for projector canvas game."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        url = urlparse(self.path)

        if url.path == '/events':
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

            try:
                # Send initial connection handshake and current lock state
                self.wfile.write(b"data: {\"event\": \"CONNECTED\"}\n\n")
                with lock_state_lock:
                    status_json = json.dumps({"event": "TRACKER_STATUS", "locked": is_locked})
                self.wfile.write(f"data: {status_json}\n\n".encode('utf-8'))
                self.wfile.flush()

                last_ping = time.time()
                while not shutdown_event.is_set():
                    try:
                        msg = q.get(timeout=0.5)
                        if msg is None:
                            break
                        self.wfile.write(f"data: {json.dumps(msg)}\n\n".encode('utf-8'))
                        self.wfile.flush()
                    except queue.Empty:
                        if time.time() - last_ping >= 10.0:
                            last_ping = time.time()
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
            except Exception:
                pass
            finally:
                with clients_lock:
                    if q in client_queues:
                        client_queues.remove(q)

        elif url.path == '/hit':
            # Trigger hit: /hit?x=0.45&y=0.60&num=1
            params = parse_qs(url.query)
            nx = float(params.get('x', [0.5])[0])
            ny = float(params.get('y', [0.5])[0])
            hit_num = int(params.get('num', [1])[0]) if 'num' in params else None
            broadcast_hit(nx, ny, hit_num)
            self._send_json({"status": "ok"})

        elif url.path in ['/tracker_status', '/lock']:
            # Toggle lock state: /tracker_status?locked=1 or /lock?locked=1
            params = parse_qs(url.query)
            locked = params.get('locked', ['0'])[0] in ['1', 'true', 'True']
            broadcast_lock(locked)
            self._send_json({"status": "ok", "locked": locked})

        elif url.path == '/calibration':
            # Retrieve saved 4-pin corner coordinates
            if os.path.exists(CALIBRATION_FILE):
                try:
                    with open(CALIBRATION_FILE, 'rb') as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    pass
            self._send_json({"corners": None})

        else:
            # Serve index.html or other static assets from /web
            super().do_GET()

    def do_POST(self):
        if self.path == '/calibration':
            # Save 4-pin corner coordinates
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode('utf-8'))
                with open(CALIBRATION_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                self._send_json({"status": "saved"})
                print("  [Calibration] Saved pin positions to projector_calibration.json")
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

    def _send_json(self, obj):
        data = json.dumps(obj).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        # Silence routine HTTP access logs
        return


def start_projector_server(port=PORT):
    server = ProjectorServer(('0.0.0.0', port), ProjectorHTTPHandler)

    print("\n" + "=" * 60)
    print(" 📽️  INTERACTIVE WHITEBOARD PROJECTOR SERVER")
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
