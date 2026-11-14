
import io
import socket
import secrets
import time
import json
import ctypes
import math
import threading

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from pairing import PairingManager
import mss
from PIL import Image

PORT = 8765
PIN = secrets.token_urlsafe(12)
PAIRING = PairingManager()

PROFILES = {
    "local": {
        "size": (1280, 720),
        "quality": 75,
        "fps": 24,
        "move_interval": 16
    },
    "network": {
        "size": (640, 360),
        "quality": 45,
        "fps": 12,
        "move_interval": 55
    }
}

settings_lock = threading.Lock()
current_mode = "auto"
funnel_active = False
remote_enabled = False

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


def set_mode(mode, funnel=False):
    global current_mode, funnel_active

    if mode not in ("auto", "local", "network"):
        return

    with settings_lock:
        current_mode = mode
        funnel_active = bool(funnel)


def set_remote_enabled(enabled):
    global remote_enabled
    with settings_lock:
        remote_enabled = bool(enabled)


def is_remote_enabled():
    with settings_lock:
        return remote_enabled


def get_profile():
    with settings_lock:
        mode = current_mode
        funnel = funnel_active

    if mode == "auto":
        effective = "network" if funnel else "local"
    else:
        effective = mode

    profile = PROFILES[effective].copy()
    profile["mode"] = mode
    profile["effective"] = effective
    return profile


HTML = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>RemoteTouch</title>

<style>
* { box-sizing:border-box; }

body {
    margin:0;
    padding:10px;
    background:#111827;
    color:white;
    font-family:Arial,sans-serif;
    text-align:center;
    user-select:none;
}

h1 {
    color:#60a5fa;
    margin:6px;
}

.subtitle {
    color:#94a3b8;
    font-size:12px;
}

.screen {
    position:relative;
    width:100%;
    margin-top:12px;
    overflow:hidden;
    border-radius:12px;
    background:black;
    touch-action:none;
}

#screenImage {
    width:100%;
    height:auto;
    display:block;
    pointer-events:none;
}

#gameControls {
    display:none;
    position:absolute;
    inset:0;
    z-index:10;
    pointer-events:none;
}

#gameControls.visible { display:block; }

#joystickBase {
    position:absolute;
    left:18px;
    bottom:18px;
    width:132px;
    height:132px;
    border:2px solid rgba(255,255,255,.55);
    border-radius:50%;
    background:rgba(15,23,42,.42);
    pointer-events:auto;
    touch-action:none;
}

#joystickStick {
    position:absolute;
    left:50%;
    top:50%;
    width:58px;
    height:58px;
    margin:-29px 0 0 -29px;
    border:2px solid rgba(255,255,255,.9);
    border-radius:50%;
    background:rgba(59,130,246,.88);
    box-shadow:0 3px 12px #0008;
    pointer-events:none;
}

#gameActionButtons {
    position:absolute;
    right:16px;
    bottom:20px;
    display:flex;
    flex-direction:column;
    gap:14px;
    pointer-events:auto;
}

.gameAction {
    width:58px;
    height:58px;
    min-width:58px;
    padding:0;
    border:2px solid rgba(255,255,255,.75);
    border-radius:50%;
    background:rgba(30,41,59,.82);
    font-size:28px;
    box-shadow:0 3px 12px #0008;
}

.gameAction.active { background:#15803d; }

#cursor {
    position:absolute;
    width:25px;
    height:33px;
    left:0;
    top:0;
    display:none;
    pointer-events:none;
    z-index:5;
}

.buttons,.scroll-buttons {
    display:flex;
    gap:8px;
    margin-top:10px;
}

button {
    border:0;
    border-radius:8px;
    padding:12px 5px;
    background:#374151;
    color:white;
    font-size:14px;
    font-weight:bold;
    touch-action:none;
    min-width:0;
}

.buttons button,.scroll-buttons button {
    flex:1;
}

button:active,button.active {
    background:#2563eb;
}

#keyboardToggle {
    width:100%;
    margin-top:12px;
    background:#2563eb;
    padding:13px;
}

#keyboard {
    display:none;
    margin-top:10px;
    padding:8px;
    background:#1f2937;
    border-radius:12px;
}

#keyboard.visible {
    display:block;
}

.keyrow {
    display:flex;
    gap:4px;
    margin-bottom:5px;
    justify-content:center;
}

.key {
    flex:1;
    min-width:0;
    padding:12px 2px;
    font-size:13px;
}

.key.wide {
    flex:1.7;
    font-size:11px;
}

.key.space {
    flex:5;
}

#languageToggle {
    flex:1.5;
    background:#0f766e;
}

.status {
    color:#86efac;
    font-size:12px;
    margin:12px 0;
}

#sensitivityOverlay {
    display:none;
    position:fixed;
    inset:0;
    z-index:1000;
    background:rgba(0,0,0,.75);
    align-items:center;
    justify-content:center;
    padding:20px;
}

#sensitivityOverlay.visible {
    display:flex;
}

.sensitivityPanel {
    position:relative;
    width:min(100%,340px);
    padding:22px 18px 18px;
    border-radius:16px;
    background:#1f2937;
}

#sensitivityClose {
    position:absolute;
    top:8px;
    right:8px;
    width:36px;
    min-width:36px;
    height:36px;
    padding:0;
    font-size:22px;
}

.sensitivityTitle {
    margin:4px 36px 16px;
    font-size:18px;
}

.sensitivityValue {
    color:#60a5fa;
    font-size:28px;
    font-weight:bold;
    margin:10px;
}

.sensitivityControls {
    display:flex;
    align-items:center;
    gap:10px;
}

.sensitivityControls button {
    width:48px;
    min-width:48px;
    font-size:20px;
}

#sensitivityRange {
    flex:1;
    min-width:0;
}

.sensitivityPresets {
    display:flex;
    gap:6px;
    margin-top:14px;
}

.sensitivityPresets button {
    flex:1;
    padding:10px 3px;
    font-size:12px;
}
</style>
</head>

<body>

<h1>RemoteTouch</h1>
<div class="subtitle">Version 1.0.0 • DEVICE PAIRING</div>

<div class="screen" id="screen">
    <img id="screenImage" src="/stream?token=TOKEN">

    <svg id="cursor" viewBox="0 0 25 33">
        <path d="M2 1 L2 25 L8 19 L13 31 L17 29 L12 17 L22 17 Z"
              fill="white" stroke="black" stroke-width="1.5"/>
    </svg>

    <div id="gameControls">
        <div id="joystickBase"><div id="joystickStick"></div></div>
        <div id="gameActionButtons">
            <button class="gameAction" id="jumpButton" aria-label="Прыжок">↑</button>
            <button class="gameAction" id="sneakButton" aria-label="Приседание">↓</button>
        </div>
    </div>
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

            <input id="sensitivityRange" type="range"
                   min="0.4" max="5" step="0.1"
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

<button id="keyboardToggle" onclick="toggleKeyboard()">⌨ ПОКАЗАТЬ КЛАВИАТУРУ</button>

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
let pointerStart = null;
let pointerMoved = false;
let longPressTimer = null;
let longPressTriggered = false;
let sneakToggled = false;
let joystickPointerId = null;
let joystickKeys = new Set();

let moveInterval = 16;
let pendingMove = null;
let pendingLook = {dx:0,dy:0};
let moveTimer = null;

const pressedKeys = new Set();
const heldMouseButtons = new Set();

const russianLabels = {
    Q:"Й",W:"Ц",E:"У",R:"К",T:"Е",Y:"Н",U:"Г",I:"Ш",O:"Щ",P:"З",
    A:"Ф",S:"Ы",D:"В",F:"А",G:"П",H:"Р",J:"О",K:"Л",L:"Д",
    Z:"Я",X:"Ч",C:"С",V:"М",B:"И",N:"Т",M:"Ь"
};

function send(command) {
    fetch("/control?token=" + encodeURIComponent(PIN), {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(command),
        keepalive:true
    }).catch(() => {
        statusText.textContent = "Нет соединения";
    });
}

function flushMovement() {
    moveTimer = null;

    if (pendingMove) {
        send({
            action:"move",
            x:pendingMove.x,
            y:pendingMove.y
        });

        pendingMove = null;
    }

    if (pendingLook.dx || pendingLook.dy) {
        send({
            action:"look",
            dx:pendingLook.dx,
            dy:pendingLook.dy
        });

        pendingLook = {dx:0,dy:0};
    }
}

function scheduleMovement() {
    if (moveTimer !== null) return;

    moveTimer = setTimeout(
        flushMovement,
        moveInterval
    );
}

function flushNow() {
    if (moveTimer !== null) {
        clearTimeout(moveTimer);
        moveTimer = null;
    }

    flushMovement();
}

async function updateRemoteSettings() {
    try {
        const response = await fetch(
            "/settings?token=" + encodeURIComponent(PIN),
            {cache:"no-store"}
        );

        if (!response.ok) return;

        const data = await response.json();
        moveInterval = data.move_interval || 16;
    } catch (_) {}
}

updateRemoteSettings();
setInterval(updateRemoteSettings, 2000);

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
    send({action:"layout"});

    currentLanguage = currentLanguage === "EN" ? "RU" : "EN";
    updateKeyboardLabels();

    statusText.textContent = "Раскладка: " + currentLanguage;
}

function toggleGameMode() {
    gameMode = !gameMode;
    lastTouch = null;
    pointerStart = null;

    const button = document.getElementById("gameModeToggle");

    button.textContent = gameMode
        ? "🎮 РЕЖИМ ИГРЫ: ВКЛ"
        : "🎮 РЕЖИМ ИГРЫ: ВЫКЛ";

    button.style.background = gameMode ? "#15803d" : "#374151";
    cursor.style.display = gameMode ? "none" : "block";
    document.getElementById("gameControls").classList.toggle("visible", gameMode);

    if (!gameMode) {
        releaseJoystickKeys();
        if (sneakToggled) {
            sendKey("SHIFT", false);
            sneakToggled = false;
            document.getElementById("sneakButton").classList.remove("active");
        }
    }

    statusText.textContent = gameMode
        ? "Джойстик — ходьба • ↑ прыжок • ↓ приседание"
        : "Обычный режим курсора";
}

function sendMove(x,y) {
    const rect = image.getBoundingClientRect();

    if (!rect.width || !rect.height) return;

    const nx = Math.max(0,Math.min(1,x/rect.width));
    const ny = Math.max(0,Math.min(1,y/rect.height));

    cursor.style.display = "block";
    cursor.style.left = (nx*rect.width)+"px";
    cursor.style.top = (ny*rect.height)+"px";

    pendingMove = {x:nx,y:ny};
    scheduleMovement();
}

function sendLook(dx,dy) {
    pendingLook.dx += Math.round(dx*cameraSensitivity);
    pendingLook.dy += Math.round(dy*cameraSensitivity);

    pendingLook.dx = Math.max(-500,Math.min(500,pendingLook.dx));
    pendingLook.dy = Math.max(-500,Math.min(500,pendingLook.dy));

    scheduleMovement();
}

function clickMouse(button) {
    send({action:"click",button});
}

function scrollMouse(delta) {
    send({action:"scroll",delta});
}

function openSensitivity() {
    document.getElementById("sensitivityOverlay").classList.add("visible");
}

function closeSensitivity() {
    document.getElementById("sensitivityOverlay").classList.remove("visible");
}

function overlayBackgroundClick(event) {
    if(event.target.id==="sensitivityOverlay") closeSensitivity();
}

function setSensitivity(value) {
    cameraSensitivity = Math.max(0.4,Math.min(5,Number(value)||1.6));
    cameraSensitivity = Math.round(cameraSensitivity*10)/10;

    document.getElementById("sensitivityRange").value=cameraSensitivity;

    document.getElementById("sensitivityValue").textContent =
        cameraSensitivity.toFixed(1)+"×";
}

function changeSensitivity(delta) {
    setSensitivity(cameraSensitivity+delta);
}

function sendKey(name,pressed) {
    let key=name;

    if(name==="SLASH") {
        key=currentLanguage==="RU" ? "SLASH_RU" : "SLASH_EN";
    }

    send({action:"key",key,pressed});
}

document.querySelectorAll(".mouseHold").forEach(button=>{
    const name=button.dataset.mouse;

    function release() {
        if(!heldMouseButtons.has(name)) return;

        heldMouseButtons.delete(name);
        button.classList.remove("active");

        send({
            action:"click",
            button:name,
            pressed:false
        });
    }

    button.addEventListener("pointerdown",event=>{
        event.preventDefault();

        if(heldMouseButtons.has(name)) return;

        heldMouseButtons.add(name);
        button.classList.add("active");

        try {
            button.setPointerCapture(event.pointerId);
        } catch(_) {}

        send({
            action:"click",
            button:name,
            pressed:true
        });
    });

    button.addEventListener("pointerup",release);
    button.addEventListener("pointercancel",release);
    button.addEventListener("lostpointercapture",release);
});

document.querySelectorAll(".key[data-key]").forEach(button=>{
    const key=button.dataset.key;
    let isPressed=false;

    function release() {
        if(!isPressed) return;

        isPressed=false;
        button.classList.remove("active");

        if(key!=="SLASH") {
            sendKey(key,false);
            pressedKeys.delete(key);
        }
    }

    button.addEventListener("pointerdown",event=>{
        event.preventDefault();

        if(isPressed) return;

        isPressed=true;
        button.classList.add("active");

        try {
            button.setPointerCapture(event.pointerId);
        } catch(_) {}

        if(key==="SLASH") {
            sendKey(key,true);
            sendKey(key,false);

            isPressed=false;
            button.classList.remove("active");
        } else {
            sendKey(key,true);
            pressedKeys.add(key);
        }
    });

    button.addEventListener("pointerup",release);
    button.addEventListener("pointercancel",release);
    button.addEventListener("lostpointercapture",release);
});

function toggleKeyboard() {
    const keyboard=document.getElementById("keyboard");

    keyboard.classList.toggle("visible");

    document.getElementById("keyboardToggle").textContent =
        keyboard.classList.contains("visible")
        ? "⌨ СКРЫТЬ КЛАВИАТУРУ"
        : "⌨ ПОКАЗАТЬ КЛАВИАТУРУ";
}

screen.addEventListener("pointerdown",event=>{
    if (event.target.closest("#gameControls")) return;
    event.preventDefault();

    try {
        screen.setPointerCapture(event.pointerId);
    } catch(_) {}

    pointerStart={x:event.clientX,y:event.clientY};
    lastTouch={x:event.clientX,y:event.clientY};
    pointerMoved=false;
    longPressTriggered=false;

    if(!gameMode) {
        const rect=image.getBoundingClientRect();
        sendMove(event.clientX-rect.left,event.clientY-rect.top);
    }

    longPressTimer=setTimeout(()=>{
        if(pointerStart && !pointerMoved) {
            longPressTriggered=true;
            clickMouse("right");
        }
    },1000);
});

screen.addEventListener("pointermove",event=>{
    if (event.target.closest("#gameControls")) return;
    event.preventDefault();
    if(!pointerStart || !lastTouch) return;

    const dx=event.clientX-lastTouch.x;
    const dy=event.clientY-lastTouch.y;

    if(Math.abs(dx)+Math.abs(dy)>5) {
        pointerMoved=true;
        if(longPressTimer!==null) {
            clearTimeout(longPressTimer);
            longPressTimer=null;
        }
    }

    if(gameMode) {
        sendLook(dx,dy);
    } else {
        const rect=image.getBoundingClientRect();
        sendMove(event.clientX-rect.left,event.clientY-rect.top);
    }

    lastTouch={x:event.clientX,y:event.clientY};
});

function finishScreenTouch() {
    flushNow();
    if(longPressTimer!==null) {
        clearTimeout(longPressTimer);
        longPressTimer=null;
    }

    if(pointerStart && !pointerMoved && !longPressTriggered) {
        clickMouse("left");
    }

    pointerStart=null;
    lastTouch=null;
    longPressTriggered=false;
}

screen.addEventListener("pointerup",finishScreenTouch);
screen.addEventListener("pointercancel",finishScreenTouch);

function setJoystickKeys(nextKeys) {
    for (const key of joystickKeys) {
        if (!nextKeys.has(key)) sendKey(key,false);
    }
    for (const key of nextKeys) {
        if (!joystickKeys.has(key)) sendKey(key,true);
    }
    joystickKeys=nextKeys;
}

function releaseJoystickKeys() {
    setJoystickKeys(new Set());
    joystickPointerId=null;
    const stick=document.getElementById("joystickStick");
    if(stick) stick.style.transform="translate(0px,0px)";
}

function updateJoystick(event) {
    const base=document.getElementById("joystickBase");
    const stick=document.getElementById("joystickStick");
    const rect=base.getBoundingClientRect();
    const cx=rect.left+rect.width/2;
    const cy=rect.top+rect.height/2;
    let dx=event.clientX-cx;
    let dy=event.clientY-cy;
    const maxRadius=47;
    const distance=Math.hypot(dx,dy);
    if(distance>maxRadius) {
        dx=dx/distance*maxRadius;
        dy=dy/distance*maxRadius;
    }
    stick.style.transform="translate("+dx+"px,"+dy+"px)";

    const threshold=13;
    const next=new Set();
    if(Math.abs(dx)>threshold) next.add(dx<0?"A":"D");
    if(Math.abs(dy)>threshold) next.add(dy<0?"W":"S");
    setJoystickKeys(next);
}

const joystickBase=document.getElementById("joystickBase");
joystickBase.addEventListener("pointerdown",event=>{
    if(!gameMode) return;
    event.preventDefault();
    event.stopPropagation();
    joystickPointerId=event.pointerId;
    joystickBase.setPointerCapture(event.pointerId);
    updateJoystick(event);
});
joystickBase.addEventListener("pointermove",event=>{
    if(event.pointerId!==joystickPointerId) return;
    event.preventDefault();
    event.stopPropagation();
    updateJoystick(event);
});
function endJoystick(event) {
    if(event.pointerId!==joystickPointerId) return;
    event.preventDefault();
    event.stopPropagation();
    releaseJoystickKeys();
}
joystickBase.addEventListener("pointerup",endJoystick);
joystickBase.addEventListener("pointercancel",endJoystick);
joystickBase.addEventListener("lostpointercapture",endJoystick);

const jumpButton=document.getElementById("jumpButton");
jumpButton.addEventListener("pointerdown",event=>{
    event.preventDefault();
    event.stopPropagation();
    jumpButton.classList.add("active");
    sendKey("SPACE",true);
    setTimeout(()=>{
        sendKey("SPACE",false);
        jumpButton.classList.remove("active");
    },140);
});
["pointerup","pointercancel","lostpointercapture"].forEach(name=>{
    jumpButton.addEventListener(name,event=>event.stopPropagation());
});

const sneakButton=document.getElementById("sneakButton");
sneakButton.addEventListener("pointerdown",event=>{
    event.preventDefault();
    event.stopPropagation();
    sneakToggled=!sneakToggled;
    sendKey("SHIFT",sneakToggled);
    sneakButton.classList.toggle("active",sneakToggled);
});
["pointerup","pointercancel","lostpointercapture"].forEach(name=>{
    sneakButton.addEventListener(name,event=>event.stopPropagation());
});

screen.addEventListener("wheel",event=>{
    event.preventDefault();
    scrollMouse(event.deltaY>0 ? -120 : 120);
},{passive:false});

image.addEventListener("load",()=>{
    statusText.textContent="Экран подключён";
});

window.addEventListener("pagehide",()=>{
    releaseJoystickKeys();
    if(sneakToggled) sendKey("SHIFT",false);
    if(longPressTimer!==null) clearTimeout(longPressTimer);

    for(const key of pressedKeys) {
        sendKey(key,false);
    }

    pressedKeys.clear();

    for(const button of heldMouseButtons) {
        send({
            action:"click",
            button,
            pressed:false
        });
    }

    heldMouseButtons.clear();
});

updateKeyboardLabels();
</script>
</body>
</html>
"""


PAIR_HTML = r"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Подключение RemoteTouch</title>
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:22px;background:#0b1220;color:#edf4ff;font-family:Segoe UI,Arial,sans-serif}
main{width:min(100%,420px);padding:28px;border:1px solid #29405f;border-radius:20px;background:#142039;box-shadow:0 20px 70px #0006}
h1{margin:0 0 8px;color:#7dd3fc}p{color:#a8b8d0;line-height:1.5}
input,button{width:100%;padding:14px;border:0;border-radius:10px;font-size:15px}
input{margin:12px 0;background:#0b1527;color:white;border:1px solid #355071}
button{background:#2563eb;color:white;font-weight:700}
#status{min-height:24px;margin-top:14px;color:#7dd3fc;font-size:14px}
</style></head><body><main>
<h1>RemoteTouch</h1><p>Запроси разрешение на подключение к компьютеру. На компьютере появится окно подтверждения.</p>
<input id="deviceName" maxlength="48" placeholder="Название устройства" autocomplete="off">
<button id="connect">Запросить подключение</button><div id="status"></div>
</main><script>
const pin = new URLSearchParams(location.search).get("pin") || "";
const statusEl = document.getElementById("status");
const button = document.getElementById("connect");
let requestId = "";
function deviceId(){
 let id=localStorage.getItem("remotetouch_device_id");
 if(!id){
  id=(window.crypto&&crypto.randomUUID)
   ? crypto.randomUUID()
   : "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g,c=>{
      const r=Math.random()*16|0;
      return (c==="x"?r:(r&3|8)).toString(16);
     });
  localStorage.setItem("remotetouch_device_id",id);
 }
 return id;
}
async function poll(){
 try{
  const r=await fetch("/pair/status?request_id="+encodeURIComponent(requestId),{cache:"no-store"});
  const d=await r.json();
  if(d.status==="approved"&&d.session_token){
   statusEl.textContent="Подключено. Открываем управление…";
   location.replace("/remote?token="+encodeURIComponent(d.session_token));
   return;
  }
  if(d.status==="denied"){statusEl.textContent="Запрос отклонён на компьютере.";button.disabled=false;return}
  if(d.status==="expired"){statusEl.textContent="Время запроса истекло. Попробуй ещё раз.";button.disabled=false;return}
  setTimeout(poll,1200);
 }catch(e){statusEl.textContent="Нет связи с компьютером.";setTimeout(poll,2500)}
}
button.addEventListener("click",async()=>{
 const name=document.getElementById("deviceName").value.trim()||"Телефон";
 button.disabled=true;statusEl.textContent="Отправляем запрос…";
 try{
  const r=await fetch("/pair/request",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({pin,device_id:deviceId(),device_name:name})});
  const d=await r.json();
  if(!r.ok)throw new Error(d.error||"Не удалось отправить запрос");
  if(d.status==="approved"&&d.session_token){location.replace("/remote?token="+encodeURIComponent(d.session_token));return}
  requestId=d.request_id;statusEl.textContent="Ожидаем подтверждения на компьютере…";poll();
 }catch(e){statusEl.textContent=e.message;button.disabled=false}
});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def authorized(self):
        query = parse_qs(urlparse(self.path).query)
        supplied = query.get("token", [""])[0]
        return PAIRING.authenticate(supplied)

    def send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_bytes(status, "application/json; charset=utf-8", data)

    def send_bytes(self, status, content_type, data):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            supplied = query.get("pin", [""])[0]
            if not secrets.compare_digest(supplied, PIN):
                self.send_error(403)
                return
            self.send_bytes(200, "text/html; charset=utf-8", PAIR_HTML.encode("utf-8"))
            return

        if path == "/pair/status":
            request_id = query.get("request_id", [""])[0]
            self.send_json(200, PAIRING.pairing_status(request_id))
            return

        if path == "/remote":
            if not self.authorized():
                self.send_error(403)
                return
            token = query.get("token", [""])[0]
            page = HTML.replace("TOKEN", token).encode("utf-8")
            self.send_bytes(200, "text/html; charset=utf-8", page)
            return

        if not self.authorized():
            self.send_error(403)
            return

        if path == "/app/status":
            self.send_json(200, {"remote_enabled": is_remote_enabled()})
            return

        if path == "/settings":
            profile = get_profile()
            data = json.dumps(profile).encode("utf-8")

            self.send_bytes(
                200,
                "application/json; charset=utf-8",
                data
            )
            return

        if path == "/stream":
            if not is_remote_enabled():
                self.send_error(409, "Remote streaming is stopped")
                return
            self.send_response(200)

            self.send_header(
                "Content-Type",
                "multipart/x-mixed-replace; boundary=frame"
            )

            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()

            self.close_connection = True

            try:
                with mss.mss() as capture:
                    monitor = capture.monitors[1]

                    while is_remote_enabled():
                        start = time.perf_counter()

                        shot = capture.grab(monitor)

                        frame = Image.frombytes(
                            "RGB",
                            shot.size,
                            shot.rgb
                        )

                        profile = get_profile()

                        frame.thumbnail(
                            profile["size"],
                            Image.Resampling.BILINEAR
                        )

                        buffer = io.BytesIO()

                        frame.save(
                            buffer,
                            format="JPEG",
                            quality=profile["quality"],
                            optimize=False
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

                        delay = (
                            1 / profile["fps"]
                            - (time.perf_counter() - start)
                        )

                        if delay > 0:
                            time.sleep(delay)

            except (
                BrokenPipeError,
                ConnectionResetError,
                ConnectionAbortedError,
                OSError
            ):
                pass

            return

        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/pair/request":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 4096:
                    self.send_error(400)
                    return
                payload = json.loads(self.rfile.read(length))
                supplied_pin = str(payload.get("pin", ""))
                if not secrets.compare_digest(supplied_pin, PIN):
                    self.send_json(403, {"error": "Неверный PIN"})
                    return
                result = PAIRING.request_pairing(
                    payload.get("device_id"),
                    payload.get("device_name"),
                )
                self.send_json(200, result)
            except (ValueError, TypeError, json.JSONDecodeError, RuntimeError) as exc:
                self.send_json(400, {"error": str(exc)})
            return

        if path in ("/app/remote/start", "/app/remote/stop"):
            if not self.authorized():
                self.send_error(403)
                return
            set_remote_enabled(path.endswith("/start"))
            self.send_json(200, {"remote_enabled": is_remote_enabled()})
            return

        if path != "/control":
            self.send_error(404)
            return

        if not self.authorized():
            self.send_error(403)
            return

        if not is_remote_enabled():
            self.send_error(409, "Remote control is stopped")
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

                x = max(0, min(1, x))
                y = max(0, min(1, y))

                width = user32.GetSystemMetrics(0)
                height = user32.GetSystemMetrics(1)

                user32.SetCursorPos(
                    round(x * (width - 1)),
                    round(y * (height - 1))
                )

            elif action == "look":
                dx = max(-500, min(500, int(command.get("dx", 0))))
                dy = max(-500, min(500, int(command.get("dy", 0))))

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
                    pressed = command["pressed"]

                    if not isinstance(pressed, bool):
                        self.send_error(400)
                        return

                    user32.mouse_event(
                        down if pressed else up,
                        0, 0, 0, 0
                    )
                else:
                    user32.mouse_event(down, 0, 0, 0, 0)
                    user32.mouse_event(up, 0, 0, 0, 0)

            elif action == "scroll":
                delta = int(command["delta"])

                if delta not in (-120, 120):
                    self.send_error(400)
                    return

                user32.mouse_event(0x0800, 0, 0, delta, 0)

            elif action == "layout":
                user32.keybd_event(0x5B, 0, 0, 0)
                user32.keybd_event(0x20, 0, 0, 0)
                user32.keybd_event(0x20, 0, 0x0002, 0)
                user32.keybd_event(0x5B, 0, 0x0002, 0)

            elif action == "key":
                name = str(command["key"]).upper()
                pressed = command["pressed"]

                if not isinstance(pressed, bool):
                    self.send_error(400)
                    return

                if name == "SLASH_RU":
                    if pressed:
                        user32.keybd_event(0x10, 0, 0, 0)
                        user32.keybd_event(0x37, 0, 0, 0)
                        user32.keybd_event(0x37, 0, 0x0002, 0)
                        user32.keybd_event(0x10, 0, 0x0002, 0)

                elif name == "SLASH_EN":
                    user32.keybd_event(
                        0xBF,
                        0,
                        0 if pressed else 0x0002,
                        0
                    )

                elif name in KEYS:
                    user32.keybd_event(
                        KEYS[name],
                        0,
                        0 if pressed else 0x0002,
                        0
                    )

                elif len(name) == 1 and name.isascii() and name.isalnum():
                    user32.keybd_event(
                        ord(name),
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
            self.send_header("Connection", "close")
            self.end_headers()

            self.close_connection = True

        except (
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
            OSError
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

    print("RemoteTouch 1.0.0")
    print(f"Pairing address: http://{get_local_ip()}:{PORT}/?pin={PIN}")
    print("PIN is only used to request a new device pairing.")

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("RemoteTouch stopped.")

    finally:
        server.server_close()
