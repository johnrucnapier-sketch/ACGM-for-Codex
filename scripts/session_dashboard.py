#!/usr/bin/env python3
"""Read-only, loopback-only live context panel for an explicitly selected project."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import secrets
import sqlite3
import time
import session_guardian as G


def display_metrics(reader, policy):
    sample = reader.status()
    used, window = reader.used, reader.window
    sample['stage'] = 'UNKNOWN'
    if sample['quality'] == 'UNKNOWN':
        return sample
    remaining = 100 * (1 - used / window)
    boundary = min(policy['compact_limit'], window * 90 // 95)
    room = boundary - used
    stage = ('CONFIRM' if remaining <= 10 or room <= policy['handoff_reserve'] + policy['reaction_margin']
             else 'CLOSING' if remaining <= 20 else 'CAUTION' if remaining <= 35 else 'NORMAL')
    sample.update(stage=stage, remaining_percent=round(max(0, remaining), 1),
                  compact_room=max(0, room), configured_raw_window=policy['raw_window'],
                  window_matches=window == policy['raw_window'] * 95 // 100)
    return sample


class Monitor:
    def __init__(self, project, home):
        self.project, self.home = project.resolve(), home
        self.readers = {}

    def snapshot(self):
        policy = json.loads((self.project / '.acgm/session-guardian.json').read_text())
        if policy.get('enabled') is not True:
            raise ValueError('Project session protection is disabled')
        with sqlite3.connect((self.home / 'state_5.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
            rows = db.execute("SELECT id, substr(title,1,90), rollout_path FROM threads WHERE cwd=? AND archived=0 AND source IN ('vscode','cli','appServer','app-server') ORDER BY updated_at DESC LIMIT 20", (str(self.project),)).fetchall()
        result = []
        active = {row[0] for row in rows}
        self.readers = {k:v for k,v in self.readers.items() if k in active}
        for thread, title, path in rows:
            reader = self.readers.setdefault(thread, G.RolloutReader(thread, self.project))
            try:
                reader.poll(Path(path))
                metrics = display_metrics(reader, policy)
            except (OSError, ValueError, TypeError):
                metrics = {'stage':'UNKNOWN', 'reason':'该任务的数据格式或身份暂不可验证。'}
            result.append({'id':thread, 'title':title, **metrics})
        return {'project': self.project.name, 'tasks':result, 'checked_at':time.time()}


def serve(project, home, port):
    monitor = Monitor(project, home)
    token = secrets.token_urlsafe(24)
    html = (Path(__file__).resolve().parents[1] / 'assets/session-dashboard/index.html').read_bytes()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}' or self.path not in (f'/{token}/', f'/{token}/status'):
                self.send_error(404); return
            if self.path.endswith('/status'):
                try:
                    body = json.dumps(monitor.snapshot(), ensure_ascii=False).encode()
                except (OSError, ValueError, sqlite3.Error):
                    body = json.dumps({'error':'暂时无法读取项目状态；不表示余量充足。'}).encode()
                content = 'application/json'
            else:
                body, content = html, 'text/html; charset=utf-8'
            self.send_response(200)
            self.send_header('Content-Type', content)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'http://127.0.0.1:{server.server_port}/{token}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--codex-home', type=Path, default=Path.home()/'.codex')
    p.add_argument('--port', type=int, default=0)
    args = p.parse_args()
    serve(args.project, args.codex_home, args.port)
