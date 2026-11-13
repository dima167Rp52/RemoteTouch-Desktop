
import io
import socket
import secrets
import time
import json
import ctypes
import math

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import mss
from PIL import Image

PORT = 8765
PIN = secrets.token_urlsafe(12)

MAX_SIZE = (960, 540)
JPEG_QUALITY = 55
TARGET_FPS = 20

user32 = ctypes.windll.user32

KEYS = {
    "ESC": 0x1B,
    "TAB": 0x09,
    "SHIFT": 0x10,
    "CTRL": 0x11,
    "ALT": 0x12,
    "WIN": 0x5B,
    "BACKSPACE": 0x08,
    "ENTER": 0x0D,
    "SPACE": 0x20,
    "CAPS": 0x14,
    "UP": 0x26,
    "DOWN": 0x28,
    "LEFT": 0x25,
    "RIGHT": 0x27,
    "DELETE": 0x2E,
}

HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>RemoteTouch</title>

<style>
* { box-sizing: border-box; }

body {
    margin: 0;
    padding: 10px;
    background: #111827;
    color: white;
    font-family: Arial, sans-serif;
    text-align: center;
    user-select: none;
}

h1 { color: #60a5fa; margin: 6px; }

.subtitle {
    color: #94a3b8;
    font-size: 12px;
}

.screen {
    position: relative;
    width: 100%;
    margin-top: 12px;
    overflow: hidden;
    border-radius: 12px;
    background: black;
    touch-action: none;
}

#screenImage {
    width: 100%;
    height: auto;
    display: block;
    pointer-events: none;
}

#cursor {
    position: absolute;
    width: 25px;
    height: 33px;
    left: 0;
    top: 0;
    display: none;
    pointer-events: none;
    z-index: 5;
}

.buttons, .scroll-buttons {
    display: flex;
    gap: 8px;
    margin-top: 10px;
}

button {
    border: 0;
    border-radius: 8px;
    padding: 12px 5px;
    background: #374151;
    color: white;
    font-size: 14px;
    font-weight: bold;
    touch-action: none;
    min-width: 0;
}

.buttons button, .scroll-buttons button {
    flex: 1;
}

button:active, button.active {
    background: #2563eb;
}

#keyboardToggle {
    width: 100%;
    margin-top: 12px;
    background: #2563eb;
    padding: 13px;
}

#keyboard {
    display: none;
    margin-top: 10px;
    padding: 8px;
    background: #1f2937;
    border-radius: 12px;
}

#keyboard.visible {
    display: block;
}

.keyrow {
    display: flex;
    gap: 4px;
    margin-bottom: 5px;
    justify-content: center;
}

.key {
    flex: 1;
    min-width: 0;
    padding: 12px 2px;
    font-size: 13px;
    background: #374151;
}

.key.wide {
    flex: 1.7;
    font-size: 11px;
}

.key.space {
    flex: 5;
}

#languageToggle {
    flex: 1.5;
    background: #0f766e;
}

.status {
    color: #86efac;
    font-size: 12px;
    margin: 12px 0;
}

#sensitivityOverlay {
    display: none;
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.75);
    align-items: center;
    justify-content: center;
    padding: 20px;
}
#sensitivityOverlay.visible { display: flex; }
.sensitivityPanel {
    position: relative;
    width: min(100%, 340px);
    padding: 22px 18px 18px;
    border-radius: 16px;
    background: #1f2937;
    box-shadow: 0 12px 40px rgba(0,0,0,.45);
}
#sensitivityClose {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 36px;
    min-width: 36px;
    height: 36px;
    padding: 0;
    background: #4b5563;
    font-size: 22px;
}
.sensitivityTitle { margin: 4px 36px 16px; font-size: 18px; }
.sensitivityValue { color: #60a5fa; font-size: 28px; font-weight: bold; margin: 10px; }
.sensitivityControls { display: flex; align-items: center; gap: 10px; }
.sensitivityControls button { width: 48px; min-width: 48px; font-size: 20px; }
#sensitivityRange { flex: 1; min-width: 0; accent-color: #3b82f6; }
.sensitivityPresets { display: flex; gap: 6px; margin-top: 14px; }
.sensitivityPresets button { flex: 1; padding: 10px 3px; font-size: 12px; }

</style>
</head>

<body>

<h1>RemoteTouch</h1>
<div class="subtitle">Version 0.6.4 • Sensitivity Control + Minecraft Camera</div>

<div class="screen" id="screen">
    <img id="screenImage" src="/stream?pin=TOKEN">

    <svg id="cursor" viewBox="0 0 25 33">
        <path d="M2 1 L2 25 L8 19 L13 31 L17 29 L12 17 L22 17 Z"
              fill="white" stroke="black" stroke-width="1.5"/>
    </svg>
</div>

<div class="buttons">
    <button class="mouseHold" data-mouse="left">ЛКМ</button>
    <button class="mouseHold" data-mouse="right">ПКМ</button>
</div>

<div class="buttons">
    <button id="gameModeToggle" onclick="toggleGameMode()">🎮 РЕЖИМ ИГРЫ: ВЫКЛ</button>
</div>

<div class="buttons">
    <button id="languageToggle" onclick="switchLanguage()">🌐 RU / EN</button>
</div>

<div class="scroll-buttons">
    <button onclick="scrollMouse(120)">▲ Вверх</button>
    <button onclick="openSensitivity()">🎯 ЧУВСТВИТЕЛЬНОСТЬ</button>
    <button onclick="scrollMouse(-120)">▼ Вниз</button>
</div>

<div id="sensitivityOverlay" onclick="overlayBackgroundClick(event)">
    <div class="sensitivityPanel">
        <button id="sensitivityClose" onclick="closeSensitivity()">×</button>
        <div class="sensitivityTitle">Чувствительность камеры</div>
        <div class="sensitivityValue" id="sensitivityValue">1.6×</div>
        <div class="sensitivityControls">
            <button onclick="changeSensitivity(-0.1)">−</button>
            <input id="sensitivityRange" type="range" min="0.4" max="5" step="0.1"
                   value="1.6" oninput="setSensitivity(this.value)">
            <button onclick="changeSensitivity(0.1)">+</button>
        </div>
        <div class="sensitivityPresets">
            <button onclick="setSensitivity(0.8)">0.8×</button>
            <button onclick="setSensitivity(1.6)">1.6×</button>
            <button onclick="setSensitivity(2.5)">2.5×</button>
            <button onclick="setSensitivity(4)">4×</button>
        </div>
    </div>
</div>

<button id="keyboardToggle" onclick="toggleKeyboard()">
    ⌨ ПОКАЗАТЬ КЛАВИАТУРУ
</button>

<div id="keyboard">

    <div class="keyrow">
        <button class="key" data-key="ESC">ESC</button>
        <button class="key" data-key="TAB">TAB</button>
        <button class="key" data-key="CAPS">CAPS</button>
        <button class="key" data-key="DELETE">DEL</button>
    </div>

    <div class="keyrow">
        <button class="key" data-key="1">1</button>
        <button class="key" data-key="2">2</button>
        <button class="key" data-key="3">3</button>
        <button class="key" data-key="4">4</button>
        <button class="key" data-key="5">5</button>
        <button class="key" data-key="6">6</button>
        <button class="key" data-key="7">7</button>
        <button class="key" data-key="8">8</button>
        <button class="key" data-key="9">9</button>
        <button class="key" data-key="0">0</button>
    </div>

    <div class="keyrow">
        <button class="key" data-key="Q">Q</button>
        <button class="key" data-key="W">W</button>
        <button class="key" data-key="E">E</button>
        <button class="key" data-key="R">R</button>
        <button class="key" data-key="T">T</button>
        <button class="key" data-key="Y">Y</button>
        <button class="key" data-key="U">U</button>
        <button class="key" data-key="I">I</button>
        <button class="key" data-key="O">O</button>
        <button class="key" data-key="P">P</button>
    </div>

    <div class="keyrow">
        <button class="key" data-key="A">A</button>
        <button class="key" data-key="S">S</button>
        <button class="key" data-key="D">D</button>
        <button class="key" data-key="F">F</button>
        <button class="key" data-key="G">G</button>
        <button class="key" data-key="H">H</button>
        <button class="key" data-key="J">J</button>
        <button class="key" data-key="K">K</button>
        <button class="key" data-key="L">L</button>
    </div>

    <div class="keyrow">
        <button class="key wide" data-key="SHIFT">SHIFT</button>
        <button class="key" data-key="Z">Z</button>
        <button class="key" data-key="X">X</button>
        <button class="key" data-key="C">C</button>
        <button class="key" data-key="V">V</button>
        <button class="key" data-key="B">B</button>
        <button class="key" data-key="N">N</button>
        <button class="key" data-key="M">M</button>
        <button class="key wide" data-key="BACKSPACE">⌫</button>
    </div>

    <div class="keyrow">
        <button class="key wide" data-key="CTRL">CTRL</button>
        <button class="key wide" data-key="WIN">WIN</button>
        <button class="key wide" data-key="ALT">ALT</button>
        <button class="key space" data-key="SPACE">ПРОБЕЛ</button>
        <button class="key wide" data-key="ENTER">ENTER</button>
    </div>

    <div class="keyrow">
        <button class="key" data-key="LEFT">←</button>
        <button class="key" data-key="UP">↑</button>
        <button class="key" data-key="DOWN">↓</button>
        <button class="key" data-key="RIGHT">→</button>
        <button class="key" data-key="SLASH">/</button>
    </div>

</div>

<div class="status" id="status">Управление готово</div>

<script>
const PIN = "TOKEN";

const screen = document.getElementById("screen");
const image = document.getElementById("screenImage");
const cursor = document.getElementById("cursor");
const statusText = document.getElementById("status");
let currentLanguage = "EN";
let gameMode = false;
let cameraSensitivity = 1.6;
let lastTouch = null;
const pressedKeys = new Set();

const russianLabels = {
    Q: "Й", W: "Ц", E: "У", R: "К", T: "Е",
    Y: "Н", U: "Г", I: "Ш", O: "Щ", P: "З",
    A: "Ф", S: "Ы", D: "В", F: "А", G: "П",
    H: "Р", J: "О", K: "Л", L: "Д",
    Z: "Я", X: "Ч", C: "С", V: "М", B: "И",
    N: "Т", M: "Ь"
};

function updateKeyboardLabels() {
    document.querySelectorAll(".key[data-key]").forEach(button => {
        const key = button.dataset.key;
        if (/^[A-Z]$/.test(key)) {
            button.textContent = currentLanguage === "RU"
                ? (russianLabels[key] || key)
                : key;
        }
    });
    document.getElementById("languageToggle").textContent =
        currentLanguage === "RU" ? "🌐 RU → EN" : "🌐 EN → RU";
}

function switchLanguage() {
    enqueue({action: "layout"});
    currentLanguage = currentLanguage === "EN" ? "RU" : "EN";
    updateKeyboardLabels();
    statusText.textContent = "Раскладка переключена: " + currentLanguage;
}

let queue = [];
let processing = false;
let pointerStart = null;
let pointerMoved = false;

function enqueue(command) {
    if (command.action === "move") {
        if (queue.length && queue[queue.length - 1].action === "move") {
            queue[queue.length - 1] = command;
        } else {
            queue.push(command);
        }
    } else if (command.action === "look") {
        if (queue.length && queue[queue.length - 1].action === "look") {
            queue[queue.length - 1].dx += command.dx;
            queue[queue.length - 1].dy += command.dy;
        } else {
            queue.push(command);
        }
    } else {
        queue.push(command);
    }

    processQueue();
}

async function processQueue() {
    if (processing) return;
    processing = true;

    while (queue.length) {
        const command = queue.shift();

        try {
            const response = await fetch(
                "/control?pin=" + encodeURIComponent(PIN),
                {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify(command)
                }
            );

            if (!response.ok) {
                statusText.textContent = "Ошибка управления";
            }
        } catch (error) {
            statusText.textContent = "Нет соединения";
        }
    }

    processing = false;
}

function sendMove(x, y) {
    const rect = image.getBoundingClientRect();
    if (!rect.width || !rect.height) return;

    const nx = Math.max(0, Math.min(1, x / rect.width));
    const ny = Math.max(0, Math.min(1, y / rect.height));

    cursor.style.display = "block";
    cursor.style.left = (nx * rect.width) + "px";
    cursor.style.top = (ny * rect.height) + "px";

    enqueue({action: "move", x: nx, y: ny});
}

function sendLook(dx, dy) {
    // Relative mouse movement is what games use to rotate the camera.
    const mx = Math.round(dx * cameraSensitivity);
    const my = Math.round(dy * cameraSensitivity);
    if (mx || my) enqueue({action: "look", dx: mx, dy: my});
}

function toggleGameMode() {
    gameMode = !gameMode;
    lastTouch = null;
    const button = document.getElementById("gameModeToggle");
    button.textContent = gameMode
        ? "🎮 РЕЖИМ ИГРЫ: ВКЛ"
        : "🎮 РЕЖИМ ИГРЫ: ВЫКЛ";
    button.style.background = gameMode ? "#15803d" : "#374151";
    cursor.style.display = gameMode ? "none" : cursor.style.display;
    statusText.textContent = gameMode
        ? "Игровой режим: веди пальцем по экрану для поворота камеры"
        : "Обычный режим управления курсором";
}

function clickMouse(button) {
    // Короткое нажатие (например, тап по экрану).
    enqueue({action: "click", button: button});
}

function sendMouseButton(button, pressed) {
    enqueue({action: "click", button: button, pressed: pressed});
}

const heldMouseButtons = new Set();
document.querySelectorAll(".mouseHold").forEach(button => {
    const name = button.dataset.mouse;
    function releaseMouse() {
        if (!heldMouseButtons.has(name)) return;
        heldMouseButtons.delete(name);
        button.classList.remove("active");
        sendMouseButton(name, false);
    }
    button.addEventListener("pointerdown", event => {
        event.preventDefault();
        if (heldMouseButtons.has(name)) return;
        heldMouseButtons.add(name);
        button.classList.add("active");
        try { button.setPointerCapture(event.pointerId); } catch (_) {}
        sendMouseButton(name, true);
    });
    button.addEventListener("pointerup", releaseMouse);
    button.addEventListener("pointercancel", releaseMouse);
    button.addEventListener("lostpointercapture", releaseMouse);
});

function scrollMouse(delta) {
    enqueue({action: "scroll", delta: delta});
}

function openSensitivity() {
    document.getElementById("sensitivityOverlay").classList.add("visible");
}

function closeSensitivity() {
    document.getElementById("sensitivityOverlay").classList.remove("visible");
}

function overlayBackgroundClick(event) {
    if (event.target.id === "sensitivityOverlay") closeSensitivity();
}

function setSensitivity(value) {
    cameraSensitivity = Math.max(0.4, Math.min(5, Number(value) || 1.6));
    cameraSensitivity = Math.round(cameraSensitivity * 10) / 10;
    document.getElementById("sensitivityRange").value = cameraSensitivity;
    document.getElementById("sensitivityValue").textContent =
        cameraSensitivity.toFixed(1) + "×";
}

function changeSensitivity(delta) {
    setSensitivity(cameraSensitivity + delta);
}

function sendKey(name, pressed) {
    let keyName = name;
    if (name === "SLASH") {
        keyName = currentLanguage === "RU" ? "SLASH_RU" : "SLASH_EN";
    }
    enqueue({
        action: "key",
        key: keyName,
        pressed: pressed
    });
}

function toggleKeyboard() {
    const keyboard = document.getElementById("keyboard");
    keyboard.classList.toggle("visible");

    document.getElementById("keyboardToggle").textContent =
        keyboard.classList.contains("visible")
        ? "⌨ СКРЫТЬ КЛАВИАТУРУ"
        : "⌨ ПОКАЗАТЬ КЛАВИАТУРУ";
}

document.querySelectorAll(".key[data-key]").forEach(button => {
    const key = button.dataset.key;
    let isPressed = false;

    function releaseKey() {
        if (!isPressed) return;
        isPressed = false;
        button.classList.remove("active");
        if (key !== "SLASH") {
            sendKey(key, false);
            pressedKeys.delete(key);
        }
    }

    button.addEventListener("pointerdown", event => {
        event.preventDefault();
        if (isPressed) return;
        isPressed = true;
        button.classList.add("active");
        try { button.setPointerCapture(event.pointerId); } catch (_) {}

        if (key === "SLASH") {
            // Slash is a one-shot character, not a held key.
            sendKey(key, true);
            sendKey(key, false);
            isPressed = false;
            button.classList.remove("active");
        } else {
            sendKey(key, true);
            pressedKeys.add(key);
        }
    });

    button.addEventListener("pointerup", releaseKey);
    button.addEventListener("pointercancel", releaseKey);
    button.addEventListener("lostpointercapture", releaseKey);
});

screen.addEventListener("pointerdown", event => {
    event.preventDefault();
    try { screen.setPointerCapture(event.pointerId); } catch (_) {}

    pointerStart = {x: event.clientX, y: event.clientY};
    lastTouch = {x: event.clientX, y: event.clientY};
    pointerMoved = false;

    if (!gameMode) {
        const rect = image.getBoundingClientRect();
        sendMove(event.clientX - rect.left, event.clientY - rect.top);
    }
});

screen.addEventListener("pointermove", event => {
    event.preventDefault();
    if (!pointerStart || !lastTouch) return;

    const dx = event.clientX - lastTouch.x;
    const dy = event.clientY - lastTouch.y;
    if (Math.abs(dx) + Math.abs(dy) > 2) pointerMoved = true;

    if (gameMode) {
        sendLook(dx, dy);
    } else {
        const rect = image.getBoundingClientRect();
        sendMove(event.clientX - rect.left, event.clientY - rect.top);
    }
    lastTouch = {x: event.clientX, y: event.clientY};
});

screen.addEventListener("pointerup", () => {
    if (pointerStart && !pointerMoved) clickMouse("left");
    pointerStart = null;
    lastTouch = null;
});

screen.addEventListener("pointercancel", () => {
    pointerStart = null;
    lastTouch = null;
});

screen.addEventListener("wheel", event => {
    event.preventDefault();
    scrollMouse(event.deltaY > 0 ? -120 : 120);
}, {passive: false});

image.addEventListener("load", () => {
    statusText.textContent = "Экран подключён";
});

window.addEventListener("pagehide", () => {
    for (const key of pressedKeys) sendKey(key, false);
    pressedKeys.clear();
    for (const button of heldMouseButtons) sendMouseButton(button, false);
    heldMouseButtons.clear();
});
</script>

</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):

    def authorized(self):
        query = parse_qs(urlparse(self.path).query)
        supplied = query.get("pin", [""])[0]
        return secrets.compare_digest(supplied, PIN)

    def do_GET(self):
        path = urlparse(self.path).path

        if not self.authorized():
            self.send_error(403, "Access denied")
            return

        if path == "/":
            page = HTML.replace("TOKEN", PIN).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return

        if path == "/stream":
            self.send_response(200)
            self.send_header(
                "Content-Type",
                "multipart/x-mixed-replace; boundary=frame"
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            try:
                with mss.mss() as screen:
                    monitor = screen.monitors[1]
                    buffer = io.BytesIO()

                    while True:
                        start = time.perf_counter()
                        shot = screen.grab(monitor)

                        image = Image.frombytes(
                            "RGB", shot.size, shot.rgb
                        )
                        image.thumbnail(
                            MAX_SIZE,
                            Image.Resampling.BILINEAR
                        )

                        buffer.seek(0)
                        buffer.truncate(0)
                        image.save(
                            buffer,
                            format="JPEG",
                            quality=JPEG_QUALITY
                        )

                        data = buffer.getvalue()

                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(
                            b"Content-Type: image/jpeg\r\n"
                        )
                        self.wfile.write(
                            f"Content-Length: {len(data)}\r\n\r\n".encode()
                        )
                        self.wfile.write(data)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()

                        remaining = (
                            1.0 / TARGET_FPS
                            - (time.perf_counter() - start)
                        )

                        if remaining > 0:
                            time.sleep(remaining)

            except (BrokenPipeError, ConnectionResetError,
                    ConnectionAbortedError, OSError):
                pass

            return

        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/control":
            self.send_error(404)
            return

        if not self.authorized():
            self.send_error(403, "Access denied")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))

            if length <= 0 or length > 4096:
                self.send_error(400)
                return

            command = json.loads(self.rfile.read(length))
            action = command.get("action")

            if action == "move":
                x = float(command["x"])
                y = float(command["y"])

                if not math.isfinite(x) or not math.isfinite(y):
                    self.send_error(400)
                    return

                x = max(0.0, min(1.0, x))
                y = max(0.0, min(1.0, y))

                width = user32.GetSystemMetrics(0)
                height = user32.GetSystemMetrics(1)

                user32.SetCursorPos(
                    round(x * (width - 1)),
                    round(y * (height - 1))
                )

            elif action == "look":
                # Relative mouse movement for first-person camera control.
                dx = int(command.get("dx", 0))
                dy = int(command.get("dy", 0))
                dx = max(-500, min(500, dx))
                dy = max(-500, min(500, dy))
                user32.mouse_event(0x0001, dx, dy, 0, 0)

            elif action == "click":
                button = command.get("button")

                flags = {
                    "left": (0x0002, 0x0004),
                    "right": (0x0008, 0x0010)
                }

                if button not in flags:
                    self.send_error(400)
                    return

                down, up = flags[button]
                if "pressed" in command:
                    if not isinstance(command["pressed"], bool):
                        self.send_error(400)
                        return
                    user32.mouse_event(down if command["pressed"] else up, 0, 0, 0, 0)
                else:
                    # Совместимость с короткими кликами по экрану.
                    user32.mouse_event(down, 0, 0, 0, 0)
                    user32.mouse_event(up, 0, 0, 0, 0)

            elif action == "scroll":
                delta = int(command["delta"])

                if delta not in (-120, 120):
                    self.send_error(400)
                    return

                user32.mouse_event(0x0800, 0, 0, delta, 0)

            elif action == "layout":
                # Windows: переключить раскладку ввода (Win + Space)
                user32.keybd_event(0x5B, 0, 0, 0)       # Win down
                user32.keybd_event(0x20, 0, 0, 0)       # Space down
                user32.keybd_event(0x20, 0, 0x0002, 0)  # Space up
                user32.keybd_event(0x5B, 0, 0x0002, 0)  # Win up

            elif action == "key":
                name = str(command["key"]).upper()
                pressed = command["pressed"]

                if name == "SLASH_RU":
                    # На русской раскладке / находится на Shift + 7.
                    # Выполняем сочетание одним нажатием.
                    if pressed:
                        user32.keybd_event(0x10, 0, 0, 0)       # Shift down
                        user32.keybd_event(0x37, 0, 0, 0)       # 7 down
                        user32.keybd_event(0x37, 0, 0x0002, 0)  # 7 up
                        user32.keybd_event(0x10, 0, 0x0002, 0)  # Shift up
                elif name == "SLASH_EN":
                    user32.keybd_event(
                        0xBF, 0, 0 if pressed else 0x0002, 0
                    )
                elif name in KEYS:
                    vk = KEYS[name]
                    user32.keybd_event(
                        vk,
                        0,
                        0 if pressed else 0x0002,
                        0
                    )
                elif len(name) == 1 and name.isascii() and name.isalnum():
                    vk = ord(name)
                    user32.keybd_event(
                        vk,
                        0,
                        0 if pressed else 0x0002,
                        0
                    )
                else:
                    self.send_error(400)
                    return

            else:
                self.send_error(400)
                return

            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()

        except (
            ValueError, TypeError, KeyError,
            json.JSONDecodeError, OSError
        ):
            self.send_error(400)

    def log_message(self, format, *args):
        pass


def get_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.connect(("192.0.2.1", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


if __name__ == "__main__":
    server = ThreadingHTTPServer(
        ("0.0.0.0", PORT),
        Handler
    )

    server.daemon_threads = True

    print("=" * 45)
    print("       REMOTETOUCH SERVER 0.6.4")
    print("          HOLD KEYS + MINECRAFT CAMERA")
    print("=" * 45)
    print("Server started!")
    print(f"Address: http://{get_local_ip()}:{PORT}")
    print(f"PIN: {PIN}")
    print("Mouse: ENABLED")
    print("Keyboard: ENABLED")
    print("Press CTRL+C to stop.")
    print("=" * 45)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nRemoteTouch stopped.")
    finally:
        server.server_close()
