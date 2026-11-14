# RemoteTouch Desktop 1.0.0

RemoteTouch lets you view and control your own Windows computer from a phone over the local network or through Tailscale Funnel.

## What's included

- Windows desktop control center built with PySide6.
- Live screen streaming, touch mouse, click-and-hold for left/right mouse buttons, scrolling, keyboard, RU/EN layout switching, and game camera mode.
- Local Wi-Fi connection and optional Tailscale Funnel internet access.
- Device pairing: a new device requests access and the Windows app asks the computer owner to allow or deny it.
- Optional trusted devices with automatic approval.
- Per-session random access tokens. The pairing PIN is used only to request a new pairing; it is not used for mouse, keyboard, or screen endpoints.
- Trusted devices can be removed from the desktop app; their active sessions are revoked.

## Requirements

- Windows 10/11
- Python 3.13
- Tailscale installed and configured if internet access through Funnel is needed

## Run

Double-click `run.bat`. It creates a virtual environment, installs dependencies, and starts the desktop app.

## Pair a phone

1. Start the server in RemoteTouch Desktop.
2. Scan the QR code or open the shown pairing link on the phone.
3. Enter a device name and request access.
4. Approve or deny the request in the Windows app.
5. After approval, the phone opens the remote-control interface.

Devices must be on the same Wi-Fi network for a local connection. For access over the internet, enable Tailscale Funnel in the desktop app.

## Security notes

- Keep the pairing link and PIN private. Anyone who has the pairing PIN can request access, but a new device still requires approval unless it is already trusted and automatic approval is enabled.
- Session tokens are held in memory and expire after 12 hours. Restarting RemoteTouch ends all active sessions.
- Trusted device IDs and names, plus the auto-approval preference, are stored in the current Windows user's application data folder.
- Local Wi-Fi mode uses HTTP on the local network. Funnel provides the HTTPS internet endpoint. Do not expose the local HTTP port directly to the public internet.
- Only connect devices you recognize. The app grants control of the computer's mouse and keyboard.

## Tests

Run the pairing unit tests with:

```bat
python -m unittest discover -s tests -v
```

A GitHub Actions workflow also compiles the Python files and runs these tests on Windows.
