"""Read-only diagnostics alongside history instrumentation; never decides a pass."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
import time


class HistoryProgress:
    def __init__(self, directory, serial):
        self.directory = Path(directory)
        self.serial = serial
        self.stop = threading.Event()

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=False)
        self.started = time.monotonic()
        self.thread = threading.Thread(target=self.collect, daemon=True)
        self.thread.start()
        return self

    def command(self, *args, binary=False):
        result = subprocess.run(['adb', '-s', self.serial, *args],
            capture_output=True, text=not binary, timeout=15)
        if binary:
            if result.returncode:
                raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
            return result.stdout
        return {'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}

    def collect(self):
        index = 0
        while not self.stop.is_set():
            row = {'elapsed_seconds': round(time.monotonic()-self.started, 3),
                'utc': datetime.now(timezone.utc).isoformat()}
            try:
                row['processes'] = self.command('shell', 'ps', '-A', '-o', 'PID,NAME,TIME')
                row['graph_stat'] = self.command('shell', 'run-as',
                    'io.github.sussic.pyfa.dev', 'stat', '-c', '%s:%Y',
                    'no_backup/fits/graph.sqlite3')
                picture = self.command('exec-out', 'screencap', '-p', binary=True)
                if not picture.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('Diagnostic screenshot is not PNG')
                name = f'{index:03}-{int(row["elapsed_seconds"]):04}s.png'
                (self.directory/name).write_bytes(picture)
                row['screenshot'] = name
            except Exception as error:
                row['diagnostic_error'] = repr(error)
            with (self.directory/'progress.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row)+'\n')
            index += 1
            self.stop.wait(30)

    def __exit__(self, *exception):
        self.stop.set()
        self.thread.join(timeout=50)
        if self.thread.is_alive():
            raise RuntimeError('History diagnostic collector did not stop')
        result = self.command('logcat', '-d', '-t', '2000')
        (self.directory/'logcat.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
