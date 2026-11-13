import sys
import socket
import threading
import webbrowser
from urllib.parse import quote

import qrcode
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QFont, QClipboard
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QFrame, QGridLayout, QMessageBox, QSizePolicy, QGraphicsOpacityEffect
)

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
        self.setWindowTitle("RemoteTouch")
        self.setMinimumSize(820, 650)
        self.resize(980, 740)
        self.setStyleSheet("""
            QWidget { color: #edf4ff; font-family: 'Segoe UI'; }
            QMainWindow { background: #080d18; }
            QWidget#root { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0b1222, stop:0.55 #111b30, stop:1 #0b1222); }
            QFrame#topbar, QFrame#card { background: rgba(20,31,52,235); border: 1px solid #263957; border-radius: 18px; }
            QLabel#brand { color: #f5f9ff; font-size: 27px; font-weight: 800; letter-spacing: 1px; }
            QLabel#version { color: #7dd3fc; font-size: 11px; font-weight: 700; }
            QLabel#muted { color: #91a4c2; font-size: 13px; }
            QLabel#section { color: #e6f0ff; font-size: 17px; font-weight: 700; }
            QLabel#url { color: #7dd3fc; font-size: 18px; font-weight: 700; padding: 12px; background: #0b1527; border: 1px solid #29466b; border-radius: 10px; }
            QLabel#pin { color: #fbbf24; font-size: 15px; font-weight: 700; }
            QLabel#status { color: #fca5a5; font-size: 13px; font-weight: 700; }
            QPushButton { border: 0; border-radius: 11px; padding: 12px 16px; background: #263750; color: #f4f8ff; font-size: 13px; font-weight: 700; }
            QPushButton:hover { background: #345071; }
            QPushButton:pressed { background: #1d4ed8; }
            QPushButton#start { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2563eb, stop:1 #06b6d4); font-size: 16px; padding: 17px; }
            QPushButton#start:hover { background: #3b82f6; }
            QPushButton#stop { background: #7f1d1d; }
            QPushButton#stop:hover { background: #991b1b; }
            QLabel#qr { background: white; border-radius: 14px; padding: 10px; }
        """)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("topbar")
        h = QHBoxLayout(header)
        h.setContentsMargins(22, 16, 22, 16)
        brand_col = QVBoxLayout()
        brand = QLabel("RemoteTouch")
        brand.setObjectName("brand")
        version = QLabel("DESKTOP CONTROL CENTER  •  0.7.0")
        version.setObjectName("version")
        brand_col.addWidget(brand)
        brand_col.addWidget(version)
        h.addLayout(brand_col)
        h.addStretch()
        self.status = QLabel("●  Сервер остановлен")
        self.status.setObjectName("status")
        h.addWidget(self.status, alignment=Qt.AlignVCenter)
        layout.addWidget(header)

        intro = QLabel("Управляй компьютером с телефона — по одной Wi-Fi сети")
        intro.setObjectName("muted")
        layout.addWidget(intro)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        layout.addLayout(grid, 1)

        control = QFrame()
        control.setObjectName("card")
        cl = QVBoxLayout(control)
        cl.setContentsMargins(22, 22, 22, 22)
        cl.setSpacing(13)
        title = QLabel("Панель управления")
        title.setObjectName("section")
        cl.addWidget(title)
        desc = QLabel("Запусти сервер, чтобы подключить телефон к RemoteTouch.")
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        cl.addWidget(desc)
        self.start_btn = QPushButton("▶   ЗАПУСТИТЬ УПРАВЛЕНИЕ")
        self.start_btn.setObjectName("start")
        self.start_btn.clicked.connect(self.start_server)
        cl.addWidget(self.start_btn)
        self.stop_btn = QPushButton("■   ОСТАНОВИТЬ СЕРВЕР")
        self.stop_btn.setObjectName("stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_server)
        cl.addWidget(self.stop_btn)
        cl.addSpacing(6)
        cl.addWidget(self.make_info("●", "Мышь и удержание кнопок", "ЛКМ, ПКМ и прокрутка"))
        cl.addWidget(self.make_info("⌨", "Полноценная клавиатура", "RU / EN, Shift, Ctrl, Tab и другие"))
        cl.addWidget(self.make_info("🎮", "Игровой режим", "Поворот камеры и настройка чувствительности"))
        grid.addWidget(control, 0, 0)

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
        self.qr_label.setStyleSheet("QLabel#qr { color: #64748b; background: #111c2e; border: 1px dashed #456080; }")
        rl.addWidget(self.qr_label, alignment=Qt.AlignCenter)
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

        footer = QLabel("Важно: компьютер и телефон должны быть подключены к одной Wi-Fi сети. Не отправляй PIN посторонним.")
        footer.setObjectName("muted")
        footer.setWordWrap(True)
        layout.addWidget(footer)

        # Плавное появление верхней панели и двух основных карточек.
        self.animations = []
        for widget, delay in ((header, 0), (control, 130), (connect, 260)):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)
            effect.setOpacity(0.0)
            anim = QPropertyAnimation(effect, b"opacity", self)
            anim.setDuration(700)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self.animations.append(anim)
            QTimer.singleShot(delay, anim.start)

        # Мягкая пульсация индикатора состояния.
        self.status_effect = QGraphicsOpacityEffect(self.status)
        self.status.setGraphicsEffect(self.status_effect)
        self.status_effect.setOpacity(1.0)
        self.pulse = QPropertyAnimation(self.status_effect, b"opacity", self)
        self.pulse.setDuration(1100)
        self.pulse.setStartValue(1.0)
        self.pulse.setKeyValueAt(0.5, 0.55)
        self.pulse.setEndValue(1.0)
        self.pulse.setEasingCurve(QEasingCurve.InOutSine)
        self.pulse.setLoopCount(-1)
        self.pulse.start()

    def make_info(self, symbol, title, subtitle):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 5, 0, 5)
        icon = QLabel(symbol)
        icon.setStyleSheet("font-size: 20px; color: #67e8f9; min-width: 28px;")
        col = QVBoxLayout()
        t = QLabel(title)
        t.setStyleSheet("font-weight: 700; font-size: 13px;")
        s = QLabel(subtitle)
        s.setObjectName("muted")
        col.addWidget(t)
        col.addWidget(s)
        lay.addWidget(icon)
        lay.addLayout(col)
        lay.addStretch()
        return row

    def start_server(self):
        if self.httpd:
            return
        try:
            from http.server import ThreadingHTTPServer
            self.httpd = ThreadingHTTPServer(("0.0.0.0", remote_server.PORT), remote_server.Handler)
            self.httpd.daemon_threads = True
            self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.server_thread.start()
            ip = local_ip()
            self.address = f"http://{ip}:{remote_server.PORT}/?pin={quote(remote_server.PIN)}"
            self.url_label.setText(self.address)
            self.pin_label.setText(f"PIN: {remote_server.PIN}")
            self.set_qr(self.address)
            self.status.setText("●  Сервер работает")
            self.status.setStyleSheet("color: #86efac; font-size: 13px; font-weight: 700;")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.copy_btn.setEnabled(True)
            self.open_btn.setEnabled(True)
        except OSError as e:
            self.httpd = None
            QMessageBox.critical(self, "Не удалось запустить сервер",
                                 f"Порт {remote_server.PORT} может быть занят.\n\n{e}")

    def set_qr(self, text):
        qr = qrcode.QRCode(box_size=7, border=2)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qimage = ImageQt(img)
        pixmap = QPixmap.fromImage(qimage).scaled(190, 190, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.qr_label.setStyleSheet("QLabel#qr { background: white; border-radius: 14px; padding: 8px; }")
        self.qr_label.setPixmap(pixmap)

    def copy_link(self):
        QApplication.clipboard().setText(self.address)
        self.copy_btn.setText("✓  Ссылка скопирована")
        QTimer.singleShot(1800, lambda: self.copy_btn.setText("⧉  Копировать ссылку"))

    def open_link(self):
        if self.address:
            webbrowser.open(self.address)

    def stop_server(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        self.address = ""
        self.url_label.setText("http://—:8765")
        self.pin_label.setText("PIN: —")
        self.qr_label.clear()
        self.qr_label.setText("Сначала запусти сервер")
        self.qr_label.setStyleSheet("QLabel#qr { color: #64748b; background: #111c2e; border: 1px dashed #456080; }")
        self.status.setText("●  Сервер остановлен")
        self.status.setStyleSheet("color: #fca5a5; font-size: 13px; font-weight: 700;")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
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
