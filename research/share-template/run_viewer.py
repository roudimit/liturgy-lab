"""Serve only site/ on localhost using Python's standard library. No installs."""
import argparse
import functools
import http.server
from pathlib import Path
import threading
import webbrowser

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / 'site'
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    try:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    except OSError as error:
        raise SystemExit(f'Could not start port {args.port}: {error}. Try --port 8767.')
    url = f'http://127.0.0.1:{args.port}/'
    print(f'Open {url}\nKeep this terminal open. Control-C stops the viewer.', flush=True)
    if not args.no_browser:
        threading.Timer(.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
