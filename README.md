# KillSwitch

A Windows system tray tool that instantly kills messaging, video conferencing, screen-sharing, VPN, and social apps with a single double-click.

## Features

- **One-click kill** — double-click the tray icon (or choose "Kill All Now") to terminate all enabled apps at once
- **Kill by group** — right-click to kill only apps in a specific category (Messaging, Video Conferencing, Screen Sharing, VPN, etc.)
- **Configurable app list** — enable/disable individual apps, edit process names, add custom apps, or scan for running processes not yet in the list
- **Start with Windows** — optional autostart via registry
- **Notifications** — optional toast notification showing which apps were killed
- **Safe process guard** — never touches system processes (explorer, svchost, lsass, etc.)

## Supported App Categories

| Category | Examples |
|---|---|
| Messaging | Slack, Discord, Teams, WhatsApp, Telegram, Signal, Skype |
| Video Conferencing | Zoom, Webex, GoToMeeting, BlueJeans, RingCentral |
| Screen Sharing | TeamViewer, AnyDesk, VNC, Parsec, Chrome Remote Desktop |
| VPN | NordVPN, ExpressVPN, WireGuard, OpenVPN, ProtonVPN, and 20+ more |
| Social | Facebook, Instagram |
| Phone Link | Windows Phone Link / Your Phone |

## Installation

### From source

```bash
pip install -r requirements.txt
python killswitch.py
```

### Build standalone EXE

```bat
build.bat
```

The compiled executable will be in `dist/`.

### Install shortcut

```bat
install.bat
```

## Usage

- **Double-click** the tray icon to kill all enabled apps immediately
- **Right-click** the tray icon for the full menu:
  - Kill All Now
  - Kill by Group (kill only one category)
  - Settings (manage the app list and options)
  - Exit

## Requirements

- Windows 10/11
- Python 3.9+ (if running from source)
- Dependencies: `psutil`, `pystray`, `Pillow`

## Configuration

Settings are stored in `%APPDATA%\KillSwitch\config.json`. Use the Settings UI to manage the list — no manual editing needed.
