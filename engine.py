#!/usr/bin/env python3
"""
DarkSQ Security Engine
Handles scanning, quarantine, encryption, and real-time protection.
"""
import os
import hashlib
import shutil
import json
import threading
import time
import datetime
import struct
from pathlib import Path
from typing import Callable, Optional

# Quarantine and config directories
HOME = Path.home()
DARKSQ_DIR = HOME / '.darksq'
QUARANTINE_DIR = DARKSQ_DIR / 'quarantine'
CONFIG_FILE = DARKSQ_DIR / 'config.json'
LOG_FILE = DARKSQ_DIR / 'events.json'
ENCRYPTION_KEY_FILE = DARKSQ_DIR / 'key.bin'

DARKSQ_DIR.mkdir(exist_ok=True)
QUARANTINE_DIR.mkdir(exist_ok=True)

# Simulated malware signatures (SHA256 hashes)
MALWARE_SIGNATURES = {
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855": "EICAR.Test.File",
    "44d88612fea8a8f36de82e1278abb02f": "Trojan.Generic.Test",
}

SUSPICIOUS_EXTENSIONS = {'.sh', '.bin', '.run', '.appimage'}
SUSPICIOUS_PATTERNS = ['eval(base64', 'exec(compile', '/dev/tcp', 'nc -e /bin/sh']

class SecurityEvent:
    def __init__(self, event_type: str, message: str, severity: str = 'info'):
        self.event_type = event_type
        self.message = message
        self.severity = severity  # info, warning, danger
        self.timestamp = datetime.datetime.now()

    def to_dict(self):
        return {
            'type': self.event_type,
            'message': self.message,
            'severity': self.severity,
            'timestamp': self.timestamp.isoformat()
        }

class Config:
    defaults = {
        'realtime_protection': True,
        'zexis_ecosystem': True,
        'daily_scan': False,
        'files_scanned_today': 0,
        'last_scan_date': '',
        'version': '1.2.0'
    }

    def __init__(self):
        self._data = dict(self.defaults)
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    saved = json.load(f)
                    self._data.update(saved)
            except Exception:
                pass

    def save(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self._data, f, indent=2)

    def get(self, key):
        return self._data.get(key, self.defaults.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()

class EventLog:
    def __init__(self):
        self.events = []
        self.load()

    def load(self):
        if LOG_FILE.exists():
            try:
                with open(LOG_FILE) as f:
                    data = json.load(f)
                    # Keep last 100 events
                    self.events = data[-100:]
            except Exception:
                self.events = []

    def add(self, event: SecurityEvent):
        self.events.append(event.to_dict())
        self.events = self.events[-100:]
        try:
            with open(LOG_FILE, 'w') as f:
                json.dump(self.events, f, indent=2)
        except Exception:
            pass

    def get_recent(self, n=20):
        return list(reversed(self.events[-n:]))

class EncryptionEngine:
    MAGIC = b'ZXFE'
    VERSION = 1

    @staticmethod
    def _get_key() -> bytes:
        if ENCRYPTION_KEY_FILE.exists():
            return ENCRYPTION_KEY_FILE.read_bytes()
        key = os.urandom(32)
        ENCRYPTION_KEY_FILE.write_bytes(key)
        return key

    @staticmethod
    def _xor_data(data: bytes, key: bytes) -> bytes:
        result = bytearray(len(data))
        for i, byte in enumerate(data):
            result[i] = byte ^ key[i % len(key)]
        return bytes(result)

    @classmethod
    def encrypt_file(cls, source_path: str, dest_path: str = None) -> str:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source_path}")

        key = cls._get_key()
        data = source.read_bytes()
        encrypted = cls._xor_data(data, key)

        # Build .zxfe file: MAGIC(4) + VERSION(1) + orig_name_len(2) + orig_name + data
        orig_name = source.name.encode('utf-8')
        header = cls.MAGIC + struct.pack('>BH', cls.VERSION, len(orig_name)) + orig_name
        payload = header + encrypted

        if dest_path is None:
            dest_path = str(source.with_suffix('.zxfe'))

        Path(dest_path).write_bytes(payload)
        return dest_path

    @classmethod
    def decrypt_file(cls, source_path: str, dest_dir: str = None) -> str:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source_path}")
        if source.suffix != '.zxfe':
            raise ValueError("Not a .zxfe encrypted file")

        payload = source.read_bytes()
        if not payload.startswith(cls.MAGIC):
            raise ValueError("Invalid .zxfe file (bad magic)")

        offset = len(cls.MAGIC)
        version, name_len = struct.unpack('>BH', payload[offset:offset+3])
        offset += 3
        orig_name = payload[offset:offset+name_len].decode('utf-8')
        offset += name_len
        encrypted = payload[offset:]

        key = cls._get_key()
        data = cls._xor_data(encrypted, key)

        dest_dir = Path(dest_dir) if dest_dir else source.parent
        dest_path = dest_dir / orig_name
        dest_path.write_bytes(data)
        return str(dest_path)

class Scanner:
    def __init__(self, config: Config, event_log: EventLog,
                 progress_cb: Callable = None, found_cb: Callable = None):
        self.config = config
        self.event_log = event_log
        self.progress_cb = progress_cb
        self.found_cb = found_cb
        self._stop = False
        self.scanned = 0
        self.threats = 0

    def stop(self):
        self._stop = True

    def _check_file(self, path: Path) -> Optional[str]:
        try:
            # Check extension
            if path.suffix.lower() in SUSPICIOUS_EXTENSIONS and path.stat().st_size < 10 * 1024 * 1024:
                # Check content for suspicious patterns
                try:
                    content = path.read_text(errors='ignore')
                    for pattern in SUSPICIOUS_PATTERNS:
                        if pattern in content:
                            return f"Suspicious.Pattern.{pattern[:10]}"
                except Exception:
                    pass

            # Check hash (only small files)
            if path.stat().st_size < 5 * 1024 * 1024:
                h = hashlib.sha256(path.read_bytes()).hexdigest()
                if h in MALWARE_SIGNATURES:
                    return MALWARE_SIGNATURES[h]
        except PermissionError:
            pass
        except Exception:
            pass
        return None

    def scan_path(self, scan_path: str):
        self._stop = False
        self.scanned = 0
        self.threats = 0
        path = Path(scan_path)

        files = []
        if path.is_file():
            files = [path]
        else:
            try:
                files = list(path.rglob('*'))
            except PermissionError:
                files = []

        total = len([f for f in files if f.is_file()])

        for i, f in enumerate(files):
            if self._stop:
                break
            if not f.is_file():
                continue

            self.scanned += 1
            threat = self._check_file(f)

            if self.progress_cb:
                self.progress_cb(self.scanned, total, str(f))

            if threat:
                self.threats += 1
                if self.found_cb:
                    self.found_cb(str(f), threat)
                ev = SecurityEvent('threat', f'Tehdit bulundu: {f.name} → {threat}', 'danger')
                self.event_log.add(ev)

            # Small delay to not freeze UI
            if self.scanned % 50 == 0:
                time.sleep(0.01)

        # Update daily count
        today = datetime.date.today().isoformat()
        if self.config.get('last_scan_date') != today:
            self.config.set('files_scanned_today', self.scanned)
            self.config.set('last_scan_date', today)
        else:
            self.config.set('files_scanned_today',
                          self.config.get('files_scanned_today') + self.scanned)

        ev = SecurityEvent(
            'scan_complete',
            f'Tarama tamamlandı: {self.scanned} dosya, {self.threats} tehdit',
            'warning' if self.threats > 0 else 'info'
        )
        self.event_log.add(ev)
        return self.scanned, self.threats

class QuarantineManager:
    def __init__(self, event_log: EventLog):
        self.event_log = event_log

    def quarantine(self, file_path: str) -> str:
        src = Path(file_path)
        dest = QUARANTINE_DIR / (src.name + '.qrn')
        shutil.move(str(src), str(dest))
        ev = SecurityEvent('quarantine', f'Karantinaya alındı: {src.name}', 'warning')
        self.event_log.add(ev)
        return str(dest)

    def restore(self, quarantine_path: str, restore_dir: str = None) -> str:
        src = Path(quarantine_path)
        orig_name = src.stem  # remove .qrn
        dest_dir = Path(restore_dir) if restore_dir else Path.home()
        dest = dest_dir / orig_name
        shutil.move(str(src), str(dest))
        ev = SecurityEvent('restore', f'Geri yüklendi: {orig_name}', 'info')
        self.event_log.add(ev)
        return str(dest)

    def delete(self, quarantine_path: str):
        Path(quarantine_path).unlink(missing_ok=True)
        ev = SecurityEvent('delete', f'Kalıcı silindi: {Path(quarantine_path).stem}', 'info')
        self.event_log.add(ev)

    def list_quarantined(self):
        return list(QUARANTINE_DIR.glob('*.qrn'))

class RealTimeMonitor:
    """Simulates real-time monitoring by periodically checking /tmp and ~/Downloads"""
    def __init__(self, config: Config, event_log: EventLog, alert_cb: Callable = None):
        self.config = config
        self.event_log = event_log
        self.alert_cb = alert_cb
        self._thread = None
        self._stop = False
        self._seen = set()

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True

    def _monitor_loop(self):
        watch_dirs = [
            Path.home() / 'Downloads',
            Path('/tmp'),
        ]
        while not self._stop:
            if not self.config.get('realtime_protection'):
                time.sleep(5)
                continue
            for d in watch_dirs:
                if not d.exists():
                    continue
                try:
                    for f in d.iterdir():
                        if str(f) not in self._seen:
                            self._seen.add(str(f))
                            if f.is_file():
                                ev = SecurityEvent(
                                    'realtime',
                                    f'Yeni dosya tarandı: {f.name} ✓',
                                    'info'
                                )
                                self.event_log.add(ev)
                                if self.alert_cb:
                                    self.alert_cb(ev)
                except PermissionError:
                    pass
            time.sleep(10)
