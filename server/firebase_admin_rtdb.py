import os
import json
import time
import socket
import http.client
import urllib.error
import urllib.request
import firebase_admin
from firebase_admin import credentials, db

# ---- YOUR RTDB URL ----
DATABASE_URL = "https://self-balancing-7a9fe-default-rtdb.firebaseio.com/"

ROOT = "Traffic_Manage"
_USE_ADMIN = False
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 0.4


def _build_rest_url(path: str) -> str:
    base = DATABASE_URL.rstrip("/")
    node = path.strip("/")
    return f"{base}/{node}.json"


def _is_retryable_http_status(code: int) -> bool:
    return code in (408, 429, 500, 502, 503, 504)


def _rest_request(method: str, path: str, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(
            _build_rest_url(path),
            data=data,
            headers=headers,
            method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            msg = exc.read().decode("utf-8", errors="ignore")
            if not _is_retryable_http_status(exc.code) or attempt >= MAX_RETRIES:
                raise RuntimeError(f"Firebase REST {method} failed: {exc.code} {msg}") from exc
            last_exc = exc
        except (
            http.client.RemoteDisconnected,
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            ConnectionError,
            OSError
        ) as exc:
            if attempt >= MAX_RETRIES:
                raise RuntimeError(f"Firebase REST {method} failed after retries: {exc}") from exc
            last_exc = exc

        time.sleep(RETRY_DELAY_SECONDS * attempt)

    raise RuntimeError(f"Firebase REST {method} failed after retries: {last_exc}") from last_exc


def _rest_get(path: str):
    return _rest_request("GET", path)


def _rest_put(path: str, payload: dict):
    return _rest_request("PUT", path, payload)


def _rest_patch(path: str, payload: dict):
    return _rest_request("PATCH", path, payload)


def _rest_post(path: str, payload: dict):
    return _rest_request("POST", path, payload)

def init_firebase():
    global _USE_ADMIN

    server_dir = os.path.dirname(__file__)
    candidates = [
        os.path.join(server_dir, "serviceAccount.json"),
        os.path.join(os.path.dirname(server_dir), "serviceAccountKey.json"),
    ]

    sa_path = None
    for p in candidates:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            sa_path = p
            break

    if sa_path and not firebase_admin._apps:
        try:
            cred = credentials.Certificate(sa_path)
            firebase_admin.initialize_app(cred, {"databaseURL": DATABASE_URL})
            _USE_ADMIN = True
            return
        except Exception:
            _USE_ADMIN = False
            return

    _USE_ADMIN = bool(firebase_admin._apps)

def root_ref():
    return db.reference(ROOT)

def logs_ref():
    return db.reference(f"{ROOT}/Logs")

def write_defaults_if_missing():
    if _USE_ADMIN:
        cur = root_ref().get()
    else:
        cur = _rest_get(ROOT)

    if cur is None:
        payload = {
            "Density": 0,
            "Line": 1,
            "Mode": "A",
            "Signal": "RED",
            "Status": "Normal",
            "GreenTime": 15,
            "TimeLeft": 15,
            "Count": 0,
            "OccPct": 0.0,
            "UpdatedAt": int(time.time() * 1000)
        }
        if _USE_ADMIN:
            root_ref().set(payload)
        else:
            _rest_put(ROOT, payload)

def patch_root(data: dict):
    payload = dict(data)
    payload["UpdatedAt"] = int(time.time() * 1000)
    if _USE_ADMIN:
        root_ref().update(payload)
    else:
        _rest_patch(ROOT, payload)

def push_log(data: dict):
    payload = dict(data)
    payload["ts"] = int(time.time() * 1000)
    if _USE_ADMIN:
        logs_ref().push(payload)
    else:
        _rest_post(f"{ROOT}/Logs", payload)

def get_root():
    if _USE_ADMIN:
        return root_ref().get() or {}
    return _rest_get(ROOT) or {}
