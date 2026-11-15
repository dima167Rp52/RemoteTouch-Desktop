# RemoteTouch Internet Directory

This Render service temporarily maps a four-character pairing code to a
computer's public Tailscale Funnel URL and the existing RemoteTouch pairing PIN.

## Deploy

1. Open Render and choose **New → Blueprint**.
2. Connect the GitHub repository `dima167Rp52/RemoteTouch-Desktop`.
3. Select branch `remotetouch-v2-desktop`.
4. Render reads the root `render.yaml` and creates `remotetouch-directory`.
5. Wait until the service is Live. Its health page is `/health`.

The desktop and Android apps are currently configured to use:
`https://remotetouch-directory.onrender.com`.
If Render assigns a different hostname, update that address in
`app.py` and `MainActivity.java`, then rebuild both apps.

## Behaviour and safety

- Codes use four characters from A-Z and 0-9.
- A computer refreshes its registration every 30 seconds.
- Registrations expire after 3 minutes without a heartbeat.
- Lookups are rate-limited per source IP.
- The directory stores active registrations in memory; expired entries and
  entries are lost when the service restarts.
- A four-character code is only a discovery shortcut, not strong
  authentication. The Windows approval prompt remains mandatory for a new
  device. Do not share the code publicly.
