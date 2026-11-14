# RemoteTouch Internet Directory

This small Render service temporarily maps a four-character pairing code to a
computer's public Tailscale Funnel URL and its existing one-time pairing PIN.

- Codes are case-insensitive, four characters from A-Z and 0-9.
- A computer must refresh its registration at least once every 3 minutes.
- Lookups are rate-limited per source IP.
- In-memory entries disappear when expired or when the service restarts.
- The four-character code is a discovery shortcut, not an authentication
  factor. The Windows approval prompt remains mandatory for a new device.

Deploy this folder using the repository's render.yaml Blueprint.
