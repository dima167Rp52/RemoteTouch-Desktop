import os
import re
import time
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)
LOCK = threading.RLock()
DEVICES = {}
LOOKUPS = {}
CODE_RE = re.compile(r"^[A-Z0-9]{4}$")
TTL = 180
LOOKUP_WINDOW = 60
LOOKUP_LIMIT = 18

def clean_expired(now):
    for code, item in list(DEVICES.items()):
        if now - item["seen"] > TTL:
            DEVICES.pop(code, None)
    for ip, hits in list(LOOKUPS.items()):
        LOOKUPS[ip] = [t for t in hits if now - t < LOOKUP_WINDOW]
        if not LOOKUPS[ip]:
            LOOKUPS.pop(ip, None)

@app.get("/health")
def health():
    return {"ok": True, "service": "RemoteTouch directory"}

@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).upper()
    url = str(data.get("url", "")).strip()
    pin = str(data.get("pin", ""))
    if not CODE_RE.fullmatch(code):
        return jsonify(error="Invalid code"), 400
    if not (url.startswith("https://") and ".ts.net" in url and len(url) < 300):
        return jsonify(error="Invalid public address"), 400
    if not pin or len(pin) > 128:
        return jsonify(error="Invalid pairing credential"), 400
    now = time.time()
    with LOCK:
        clean_expired(now)
        DEVICES[code] = {"url": url, "pin": pin, "seen": now}
    return {"ok": True, "expires_in": TTL}

@app.post("/api/lookup")
def lookup():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).upper()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    now = time.time()
    with LOCK:
        clean_expired(now)
        hits = LOOKUPS.setdefault(ip, [])
        if len(hits) >= LOOKUP_LIMIT:
            return jsonify(error="Слишком много попыток. Подожди минуту."), 429
        hits.append(now)
        item = DEVICES.get(code) if CODE_RE.fullmatch(code) else None
        if not item:
            return jsonify(error="Компьютер не найден или код устарел."), 404
        return jsonify(url=item["url"], pin=item["pin"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
