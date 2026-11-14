
import sys
import socket
import threading
import webbrowser
import shutil
import os
import re
import json
import time

import qrcode
from PIL.ImageQt import ImageQt

from PySide6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QProcess
)

from PySide6.QtGui import QPixmap

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QGridLayout,
    QMessageBox,
    QGraphicsOpacityEffect,
    QComboBox,
    QCheckBox,
    QInputDialog
)

from urllib.parse import quote

import main as remote_server


def local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.connect(("192.0.2.1", 80))
        return sock.getsockname()[0]

    except OSError:
        return "127.0.0.1"

    finally:
        sock.close()


class RemoteTouchApp(QMainWindow):

    def __init__(self):
        super().__init__()

        self.httpd = None
        self.server_thread = None
        self.address = ""

        self.funnel_process = None
        self.internet_address = ""
        self.discovery_stop = threading.Event()
        self.discovery_thread = None

        self.setWindowTitle("RemoteTouch")
        self.setMinimumSize(820, 740)
        self.resize(980, 850)

        self.setStyleSheet("""
            QWidget {
                color: #edf4ff;
                font-family: 'Segoe UI';
            }

            QMainWindow {
                background: #080d18;
            }

            QWidget#root {
                background: qlineargradient(
                    x1:0,y1:0,x2:1,y2:1,
                    stop:0 #0b1222,
                    stop:0.55 #111b30,
                    stop:1 #0b1222
                );
            }

            QFrame#topbar, QFrame#card {
                background: rgba(20,31,52,235);
                border: 1px solid #263957;
                border-radius: 18px;
            }

            QLabel#brand {
                color: #f5f9ff;
                font-size: 27px;
                font-weight: 800;
                letter-spacing: 1px;
            }

            QLabel#version {
                color: #7dd3fc;
                font-size: 11px;
                font-weight: 700;
            }

            QLabel#muted {
                color: #91a4c2;
                font-size: 13px;
            }

            QLabel#section {
                color: #e6f0ff;
                font-size: 17px;
                font-weight: 700;
            }

            QLabel#url {
                color: #7dd3fc;
                font-size: 15px;
                font-weight: 700;
                padding: 12px;
                background: #0b1527;
                border: 1px solid #29466b;
                border-radius: 10px;
            }

            QLabel#pin {
                color: #fbbf24;
                font-size: 15px;
                font-weight: 700;
            }

            QLabel#status {
                color: #fca5a5;
                font-size: 13px;
                font-weight: 700;
            }

            QPushButton {
                border: 0;
                border-radius: 11px;
                padding: 12px 16px;
                background: #263750;
                color: #f4f8ff;
                font-size: 13px;
                font-weight: 700;
            }

            QPushButton:hover {
                background: #345071;
            }

            QPushButton:pressed {
                background: #1d4ed8;
            }

            QPushButton:disabled {
                background: #1c293c;
                color: #718096;
            }

            QPushButton#start {
                background: qlineargradient(
                    x1:0,y1:0,x2:1,y2:0,
                    stop:0 #2563eb,
                    stop:1 #06b6d4
                );
                font-size: 15px;
                padding: 16px;
            }

            QPushButton#start:hover {
                background: #3b82f6;
            }

            QPushButton#stop {
                background: #7f1d1d;
            }

            QPushButton#stop:hover {
                background: #991b1b;
            }

            QPushButton#internet {
                background: #075985;
            }

            QPushButton#internet:hover {
                background: #0369a1;
            }

            QPushButton#internet_stop {
                background: #7f1d1d;
            }

            QLabel#qr {
                background: white;
                border-radius: 14px;
                padding: 10px;
            }

            QComboBox {
                background: #0b1527;
                color: white;
                border: 1px solid #29466b;
                border-radius: 9px;
                padding: 11px;
                font-size: 13px;
                font-weight: 700;
            }

            QComboBox:hover {
                border: 1px solid #3b82f6;
            }

            QComboBox QAbstractItemView {
                background: #17243a;
                color: white;
                selection-background-color: #2563eb;
                border: 1px solid #29466b;
                padding: 5px;
            }
        """)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(16)

        # Верхняя панель
        header = QFrame()
        header.setObjectName("topbar")

        h = QHBoxLayout(header)
        h.setContentsMargins(22, 16, 22, 16)

        brand_col = QVBoxLayout()

        brand = QLabel("RemoteTouch")
        brand.setObjectName("brand")

        version = QLabel("DESKTOP CONTROL CENTER  •  1.0.0")
        version.setObjectName("version")

        brand_col.addWidget(brand)
        brand_col.addWidget(version)

        h.addLayout(brand_col)
        h.addStretch()

        self.status = QLabel("●  Сервер остановлен")
        self.status.setObjectName("status")

        h.addWidget(self.status, alignment=Qt.AlignVCenter)

        layout.addWidget(header)

        intro = QLabel(
            "Управляй компьютером с телефона — локально или через интернет"
        )
        intro.setObjectName("muted")

        layout.addWidget(intro)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        layout.addLayout(grid, 1)

        # Левая карточка
        control = QFrame()
        control.setObjectName("card")

        cl = QVBoxLayout(control)
        cl.setContentsMargins(22, 22, 22, 22)
        cl.setSpacing(12)

        title = QLabel("Панель управления")
        title.setObjectName("section")

        cl.addWidget(title)

        desc = QLabel(
            "Запусти сервер, чтобы подключить телефон к RemoteTouch."
        )
        desc.setObjectName("muted")
        desc.setWordWrap(True)

        cl.addWidget(desc)

        self.start_btn = QPushButton(
            "▶   ЗАПУСТИТЬ УПРАВЛЕНИЕ"
        )
        self.start_btn.setObjectName("start")
        self.start_btn.clicked.connect(self.start_server)

        cl.addWidget(self.start_btn)

        self.stop_btn = QPushButton(
            "■   ОСТАНОВИТЬ СЕРВЕР"
        )
        self.stop_btn.setObjectName("stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_server)

        cl.addWidget(self.stop_btn)

        # Выбор режима
        mode_title = QLabel("⚙  РЕЖИМ ПРОИЗВОДИТЕЛЬНОСТИ")
        mode_title.setStyleSheet(
            "font-size: 13px; font-weight: 700; color: #7dd3fc;"
        )

        cl.addWidget(mode_title)

        self.mode_combo = QComboBox()

        self.mode_combo.addItem(
            "Авто — локально / интернет",
            "auto"
        )

        self.mode_combo.addItem(
            "Локальный — максимум качества",
            "local"
        )

        self.mode_combo.addItem(
            "Сетевой — минимум задержки",
            "network"
        )

        self.mode_combo.currentIndexChanged.connect(
            self.change_mode
        )

        cl.addWidget(self.mode_combo)

        self.mode_description = QLabel(
            "Авто: при включённом Funnel используется сетевой режим."
        )
        self.mode_description.setObjectName("muted")
        self.mode_description.setWordWrap(True)

        cl.addWidget(self.mode_description)

        self.internet_btn = QPushButton(
            "🌐   ОТКРЫТЬ ДОСТУП ИЗ ИНТЕРНЕТА"
        )
        self.internet_btn.setObjectName("internet")
        self.internet_btn.setEnabled(False)
        self.internet_btn.clicked.connect(self.start_funnel)

        cl.addWidget(self.internet_btn)

        self.stop_internet_btn = QPushButton(
            "✕   ОТКЛЮЧИТЬ ИНТЕРНЕТ"
        )
        self.stop_internet_btn.setObjectName("internet_stop")
        self.stop_internet_btn.setEnabled(False)
        self.stop_internet_btn.clicked.connect(self.stop_funnel)

        cl.addWidget(self.stop_internet_btn)

        self.auto_trust_check = QCheckBox(
            "Автоматически разрешать доверенным устройствам"
        )
        self.auto_trust_check.setStyleSheet(
            "color: #c5d5eb; font-size: 12px; padding: 5px;"
        )
        self.auto_trust_check.setChecked(
            remote_server.PAIRING.auto_allow_trusted()
        )
        self.auto_trust_check.toggled.connect(
            remote_server.PAIRING.set_auto_allow_trusted
        )
        cl.addWidget(self.auto_trust_check)

        self.trusted_devices_btn = QPushButton(
            "УПРАВЛЕНИЕ ДОВЕРЕННЫМИ УСТРОЙСТВАМИ"
        )
        self.trusted_devices_btn.clicked.connect(
            self.manage_trusted_devices
        )
        cl.addWidget(self.trusted_devices_btn)

        cl.addSpacing(6)

        cl.addWidget(
            self.make_info(
                "●",
                "Мышь и удержание кнопок",
                "ЛКМ, ПКМ и прокрутка"
            )
        )

        cl.addWidget(
            self.make_info(
                "⌨",
                "Полноценная клавиатура",
                "RU / EN, Shift, Ctrl, Tab и другие"
            )
        )

        cl.addWidget(
            self.make_info(
                "🎮",
                "Игровой режим",
                "Поворот камеры и настройка чувствительности"
            )
        )

        grid.addWidget(control, 0, 0)

        # Правая карточка
        connect = QFrame()
        connect.setObjectName("card")

        rl = QVBoxLayout(connect)
        rl.setContentsMargins(22, 22, 22, 22)
        rl.setSpacing(12)

        rtitle = QLabel("Подключение телефона")
        rtitle.setObjectName("section")

        rl.addWidget(rtitle)

        self.qr_label = QLabel("Сначала запусти сервер")
        self.qr_label.setObjectName("qr")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setFixedSize(210, 210)

        self.qr_label.setStyleSheet("""
            QLabel#qr {
                color: #64748b;
                background: #111c2e;
                border: 1px dashed #456080;
            }
        """)

        rl.addWidget(
            self.qr_label,
            alignment=Qt.AlignCenter
        )

        hint = QLabel("Отсканируй QR-код камерой телефона")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignCenter)

        rl.addWidget(hint)

        self.url_label = QLabel("http://—:8765")
        self.url_label.setObjectName("url")
        self.url_label.setAlignment(Qt.AlignCenter)
        self.url_label.setWordWrap(True)

        rl.addWidget(self.url_label)

        self.pin_label = QLabel("PIN: —")
        self.pin_label.setObjectName("pin")
        self.pin_label.setAlignment(Qt.AlignCenter)

        rl.addWidget(self.pin_label)

        buttons = QHBoxLayout()

        self.copy_btn = QPushButton("⧉  Копировать ссылку")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self.copy_link)

        self.open_btn = QPushButton("↗  Открыть на ПК")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self.open_link)

        buttons.addWidget(self.copy_btn)
        buttons.addWidget(self.open_btn)

        rl.addLayout(buttons)

        grid.addWidget(connect, 0, 1)

        footer = QLabel(
            "Важно: для локального подключения устройства должны быть "
            "в одной Wi-Fi сети. Для доступа из интернета используется "
            "Tailscale Funnel. Не отправляй PIN посторонним."
        )

        footer.setObjectName("muted")
        footer.setWordWrap(True)

        layout.addWidget(footer)

        # Анимация появления
        self.animations = []

        for widget, delay in (
            (header, 0),
            (control, 130),
            (connect, 260)
        ):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            effect.setOpacity(0.0)

            anim = QPropertyAnimation(
                effect,
                b"opacity",
                self
            )

            anim.setDuration(700)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)

            self.animations.append(anim)

            QTimer.singleShot(delay, anim.start)

        # Пульсация статуса
        self.status_effect = QGraphicsOpacityEffect(self.status)
        self.status.setGraphicsEffect(self.status_effect)
        self.status_effect.setOpacity(1.0)

        self.pulse = QPropertyAnimation(
            self.status_effect,
            b"opacity",
            self
        )

        self.pulse.setDuration(1100)
        self.pulse.setStartValue(1.0)
        self.pulse.setKeyValueAt(0.5, 0.55)
        self.pulse.setEndValue(1.0)
        self.pulse.setEasingCurve(QEasingCurve.InOutSine)
        self.pulse.setLoopCount(-1)
        self.pulse.start()

        self.pairing_prompt_active = False
        self.pairing_timer = QTimer(self)
        self.pairing_timer.timeout.connect(self.check_pairing_requests)
        self.pairing_timer.start(900)

    def manage_trusted_devices(self):
        devices = remote_server.PAIRING.trusted_devices()
        if not devices:
            QMessageBox.information(
                self,
                "Доверенные устройства",
                "Пока нет сохранённых доверенных устройств."
            )
            return

        labels = [
            f'{item["name"]} • {item["device_id"][:8]}'
            for item in devices
        ]
        selected, accepted = QInputDialog.getItem(
            self,
            "Доверенные устройства",
            "Выбери устройство для отзыва доступа:",
            labels,
            0,
            False
        )
        if not accepted:
            return

        index = labels.index(selected)
        device = devices[index]
        answer = QMessageBox.question(
            self,
            "Отозвать доступ",
            f'Удалить доверие для устройства «{device["name"]}»?'
        )
        if answer == QMessageBox.Yes:
            remote_server.PAIRING.revoke_device(device["device_id"])
            QMessageBox.information(
                self,
                "Готово",
                "Доверие удалено. Активные сессии этого устройства закрыты."
            )

    def check_pairing_requests(self):
        """Ask the computer owner before granting a new device access."""
        if not self.httpd or self.pairing_prompt_active:
            return

        requests = remote_server.PAIRING.pending_requests()
        if not requests:
            return

        self.pairing_prompt_active = True
        try:
            for request in requests:
                box = QMessageBox(self)
                box.setWindowTitle("Запрос RemoteTouch")
                box.setIcon(QMessageBox.Question)
                box.setText(
                    "Устройство просит доступ к компьютеру:\n\n"
                    + request["device_name"]
                    + "\n\nРазрешить управление экраном и мышью?"
                )
                box.setInformativeText(
                    "Если устройство ваше, можно добавить его в доверенные."
                )
                box.setStandardButtons(
                    QMessageBox.Yes | QMessageBox.No
                )
                box.button(QMessageBox.Yes).setText("Разрешить")
                box.button(QMessageBox.No).setText("Отклонить")

                trust = QCheckBox("Запомнить устройство и доверять ему")
                box.setCheckBox(trust)

                answer = box.exec()
                if answer == QMessageBox.Yes:
                    remote_server.PAIRING.approve(
                        request["request_id"],
                        trust_device=trust.isChecked()
                    )
                else:
                    remote_server.PAIRING.deny(request["request_id"])
        finally:
            self.pairing_prompt_active = False

    def make_info(self, symbol, title, subtitle):
        row = QWidget()

        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 5, 0, 5)

        icon = QLabel(symbol)

        icon.setStyleSheet(
            "font-size: 20px; color: #67e8f9; min-width: 28px;"
        )

        col = QVBoxLayout()

        t = QLabel(title)
        t.setStyleSheet(
            "font-weight: 700; font-size: 13px;"
        )

        s = QLabel(subtitle)
        s.setObjectName("muted")

        col.addWidget(t)
        col.addWidget(s)

        lay.addWidget(icon)
        lay.addLayout(col)
        lay.addStretch()

        return row

    # Переключение режима
    def change_mode(self):
        mode = self.mode_combo.currentData()

        remote_server.set_mode(
            mode,
            funnel=bool(self.internet_address)
        )

        descriptions = {
            "auto": (
                "Авто: при включённом Funnel используется сетевой режим."
            ),
            "local": (
                "Локальный: 1280×720, качество 75, до 24 FPS."
            ),
            "network": (
                "Сетевой: 640×360, качество 45, до 12 FPS."
            )
        }

        self.mode_description.setText(
            descriptions.get(mode, "")
        )

    # Запуск локального сервера
    def start_server(self):
        if self.httpd:
            return

        try:
            self.httpd = remote_server.ThreadingHTTPServer(
                ("0.0.0.0", remote_server.PORT),
                remote_server.Handler
            )

            self.httpd.daemon_threads = True

            self.server_thread = threading.Thread(
                target=self.httpd.serve_forever,
                daemon=True
            )

            self.server_thread.start()

            # Обнаружение компьютера приложением RemoteTouch в той же Wi-Fi сети.
            self.discovery_stop.clear()
            self.discovery_thread = threading.Thread(
                target=self.broadcast_discovery,
                daemon=True
            )
            self.discovery_thread.start()

            remote_server.set_mode(
                self.mode_combo.currentData(),
                funnel=False
            )

            ip = local_ip()

            self.address = (
                f"http://{ip}:{remote_server.PORT}/"
                f"?pin={quote(remote_server.PIN)}"
            )

            self.url_label.setText(self.address)
            self.pin_label.setText(
                f"PIN: {remote_server.PIN}"
            )

            self.set_qr(self.address)

            self.status.setText("●  Сервер работает")
            self.status.setStyleSheet(
                "color: #86efac; font-size: 13px; font-weight: 700;"
            )

            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.internet_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
            self.open_btn.setEnabled(True)

        except OSError as e:
            if self.httpd:
                self.httpd.server_close()

            self.httpd = None

            QMessageBox.critical(
                self,
                "Не удалось запустить сервер",
                f"Порт {remote_server.PORT} может быть занят.\n\n{e}"
            )

    # Запуск Tailscale Funnel
    def start_funnel(self):
        if not self.httpd:
            QMessageBox.warning(
                self,
                "RemoteTouch",
                "Сначала запусти локальный сервер!"
            )
            return

        if (
            self.funnel_process
            and self.funnel_process.state() != QProcess.NotRunning
        ):
            return

        tailscale = shutil.which("tailscale")

        if not tailscale:
            candidates = [
                r"C:\Program Files\Tailscale\tailscale.exe",
                r"C:\Program Files (x86)\Tailscale\tailscale.exe"
            ]

            tailscale = next(
                (p for p in candidates if os.path.isfile(p)),
                None
            )

        if not tailscale:
            QMessageBox.critical(
                self,
                "Tailscale не найден",
                "Не удалось найти tailscale.exe.\n"
                "Проверь, установлен ли Tailscale."
            )
            return

        self.funnel_process = QProcess(self)

        self.funnel_process.setProgram(tailscale)

        self.funnel_process.setArguments(
            ["funnel", str(remote_server.PORT)]
        )

        self.funnel_process.setProcessChannelMode(
            QProcess.MergedChannels
        )

        self.funnel_process.readyReadStandardOutput.connect(
            self.on_funnel_output
        )

        self.funnel_process.finished.connect(
            self.on_funnel_finished
        )

        self.internet_btn.setEnabled(False)
        self.internet_btn.setText("⏳   ПОДКЛЮЧЕНИЕ...")

        self.status.setText(
            "●  Подключение к Tailscale..."
        )

        self.status.setStyleSheet(
            "color: #fbbf24; font-size: 13px; font-weight: 700;"
        )

        self.funnel_process.start()

        QTimer.singleShot(
            10000,
            self.check_funnel_start
        )

    def check_funnel_start(self):
        if (
            self.funnel_process
            and self.funnel_process.state() == QProcess.NotRunning
            and not self.internet_address
            and self.httpd
        ):
            self.internet_btn.setEnabled(True)

            self.internet_btn.setText(
                "🌐   ОТКРЫТЬ ДОСТУП ИЗ ИНТЕРНЕТА"
            )

            QMessageBox.warning(
                self,
                "Tailscale",
                "Не удалось запустить Funnel. "
                "Проверь Tailscale и его настройки."
            )

    # Получение публичной ссылки
    def on_funnel_output(self):
        if not self.funnel_process:
            return

        output = bytes(
            self.funnel_process.readAllStandardOutput()
        ).decode("utf-8", errors="replace")

        match = re.search(
            r"https://[a-zA-Z0-9.-]+\.ts\.net/?",
            output
        )

        if match and not self.internet_address:
            base_url = match.group(0).rstrip("/")

            self.internet_address = (
                base_url
                + "/?pin="
                + quote(remote_server.PIN)
            )

            remote_server.set_mode(
                self.mode_combo.currentData(),
                funnel=True
            )

            self.url_label.setText(
                self.internet_address
            )

            self.set_qr(self.internet_address)

            self.internet_btn.setText(
                "✓   ИНТЕРНЕТ ДОСТУПЕН"
            )

            self.internet_btn.setEnabled(False)
            self.stop_internet_btn.setEnabled(True)

            self.copy_btn.setText(
                "⧉  Копировать ссылку"
            )

            self.copy_btn.setEnabled(True)
            self.open_btn.setEnabled(True)

            self.status.setText(
                "●  Сервер доступен из интернета"
            )

            self.status.setStyleSheet(
                "color: #86efac; font-size: 13px; font-weight: 700;"
            )

    # Завершение Funnel
    def on_funnel_finished(self, exit_code, exit_status):
        self.internet_address = ""

        remote_server.set_mode(
            self.mode_combo.currentData(),
            funnel=False
        )

        self.stop_internet_btn.setEnabled(False)
        self.internet_btn.setEnabled(bool(self.httpd))

        self.internet_btn.setText(
            "🌐   ОТКРЫТЬ ДОСТУП ИЗ ИНТЕРНЕТА"
        )

        if self.httpd:
            self.url_label.setText(self.address)
            self.set_qr(self.address)

            self.status.setText(
                "●  Сервер работает (локально)"
            )

            self.status.setStyleSheet(
                "color: #86efac; font-size: 13px; font-weight: 700;"
            )

    # Отключение Funnel
    def stop_funnel(self):
        process = self.funnel_process

        if process:
            self.funnel_process = None

            if process.state() != QProcess.NotRunning:
                process.terminate()

                if not process.waitForFinished(2500):
                    process.kill()
                    process.waitForFinished(1500)

        self.internet_address = ""

        remote_server.set_mode(
            self.mode_combo.currentData(),
            funnel=False
        )

        self.stop_internet_btn.setEnabled(False)
        self.internet_btn.setEnabled(bool(self.httpd))

        self.internet_btn.setText(
            "🌐   ОТКРЫТЬ ДОСТУП ИЗ ИНТЕРНЕТА"
        )

        if self.httpd:
            self.url_label.setText(self.address)
            self.set_qr(self.address)

            self.status.setText(
                "●  Сервер работает"
            )

            self.status.setStyleSheet(
                "color: #86efac; font-size: 13px; font-weight: 700;"
            )

    # Создание QR-кода
    def set_qr(self, text):
        qr = qrcode.QRCode(
            box_size=7,
            border=2
        )

        qr.add_data(text)
        qr.make(fit=True)

        img = qr.make_image(
            fill_color="black",
            back_color="white"
        ).convert("RGB")

        qimage = ImageQt(img)

        pixmap = QPixmap.fromImage(qimage).scaled(
            190,
            190,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.qr_label.setStyleSheet("""
            QLabel#qr {
                background: white;
                border-radius: 14px;
                padding: 8px;
            }
        """)

        self.qr_label.setPixmap(pixmap)

    # Копирование ссылки
    def copy_link(self):
        link = self.internet_address or self.address

        if not link:
            return

        QApplication.clipboard().setText(link)

        self.copy_btn.setText(
            "✓  Ссылка скопирована"
        )

        QTimer.singleShot(
            1800,
            lambda: self.copy_btn.setText(
                "⧉  Копировать ссылку"
            )
        )

    # Открытие ссылки
    def open_link(self):
        link = self.internet_address or self.address

        if link:
            webbrowser.open(link)

    # Объявление компьютера в локальной сети для мобильного приложения.
    def broadcast_discovery(self):
        packet = json.dumps({
            "type": "remotetouch_discovery",
            "name": socket.gethostname(),
            "url": self.address,
            "version": 1
        }).encode("utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while not self.discovery_stop.is_set():
                try:
                    sock.sendto(packet, ("255.255.255.255", 8766))
                except OSError:
                    pass
                self.discovery_stop.wait(2.0)
        finally:
            sock.close()

    # Остановка сервера
    def stop_server(self):
        self.discovery_stop.set()
        self.discovery_thread = None
        self.stop_funnel()

        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

        self.server_thread = None
        self.address = ""

        self.url_label.setText("http://—:8765")
        self.pin_label.setText("PIN: —")

        self.qr_label.clear()
        self.qr_label.setText("Сначала запусти сервер")

        self.qr_label.setStyleSheet("""
            QLabel#qr {
                color: #64748b;
                background: #111c2e;
                border: 1px dashed #456080;
            }
        """)

        self.status.setText(
            "●  Сервер остановлен"
        )

        self.status.setStyleSheet(
            "color: #fca5a5; font-size: 13px; font-weight: 700;"
        )

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.internet_btn.setEnabled(False)
        self.stop_internet_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.open_btn.setEnabled(False)

    def closeEvent(self, event):
        self.stop_server()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("RemoteTouch")

    window = RemoteTouchApp()
    window.show()

    sys.exit(app.exec())
