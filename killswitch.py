#!/usr/bin/env python3
"""
KillSwitch - System tray tool to instantly close messaging and screen-sharing apps.
Double-click the tray icon (or choose "Kill All Now") to kill every enabled app.
Right-click for the full menu.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import winreg
from pathlib import Path

import psutil
import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import ttk, messagebox

# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME     = "KillSwitch"
APP_VERSION  = "1.1.0"
CONFIG_DIR   = Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME
CONFIG_FILE  = CONFIG_DIR / "config.json"
AUTOSTART_REG = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

APP_GROUPS: list[str] = [
    "Messaging",
    "Video Conferencing",
    "Screen Sharing",
    "VPN",
    "Phone Link",
    "Social",
    "Other",
]

# Processes we never touch regardless of config
_SAFE_PROCS: frozenset[str] = frozenset({
    "system", "idle", "registry", "smss.exe", "csrss.exe", "wininit.exe",
    "services.exe", "lsass.exe", "winlogon.exe", "explorer.exe", "dwm.exe",
    "taskhostw.exe", "runtimebroker.exe", "sihost.exe", "ctfmon.exe",
    "fontdrvhost.exe", "svchost.exe", "spoolsv.exe", "audiodg.exe",
    "wuauclt.exe", "msiexec.exe", "conhost.exe", "taskmgr.exe",
    "python.exe", "pythonw.exe",  # never kill ourselves
})

DEFAULT_APPS: list[dict] = [
    # ── Meta / Facebook ──────────────────────────────────────────────────────
    {"name": "Facebook Messenger",    "group": "Messaging",          "processes": ["Messenger", "MessengerDesktop", "FacebookMessenger"],          "enabled": True},
    {"name": "Facebook",              "group": "Social",             "processes": ["Facebook", "FacebookDesktop"],                                  "enabled": True},
    {"name": "WhatsApp",              "group": "Messaging",          "processes": ["WhatsApp", "WhatsAppDesktop"],                                  "enabled": True},
    {"name": "Instagram",             "group": "Social",             "processes": ["Instagram"],                                                    "enabled": True},
    # ── Microsoft ────────────────────────────────────────────────────────────
    {"name": "Microsoft Teams",       "group": "Video Conferencing", "processes": ["Teams", "ms-teams", "ms-teamsupdate"],                         "enabled": True},
    {"name": "Phone Link",            "group": "Phone Link",         "processes": ["PhoneExperienceHost", "YourPhone", "YourPhoneServer", "YourPhoneAppProxy"], "enabled": True},
    {"name": "Skype",                 "group": "Messaging",          "processes": ["Skype", "SkypeApp", "SkypeBackgroundHost"],                    "enabled": True},
    # ── Video conferencing ───────────────────────────────────────────────────
    {"name": "Zoom",                  "group": "Video Conferencing", "processes": ["Zoom", "CptHost", "Cpthost"],                                  "enabled": True},
    {"name": "Webex",                 "group": "Video Conferencing", "processes": ["CiscoWebexMeetings", "WebexHost", "ptoneclk", "atmgr"],        "enabled": True},
    {"name": "GoToMeeting",           "group": "Video Conferencing", "processes": ["g2mcomm", "g2mlauncher", "g2mstart", "GoTo"],                 "enabled": True},
    {"name": "BlueJeans",             "group": "Video Conferencing", "processes": ["BlueJeans", "BlueJeansHelper"],                                "enabled": True},
    {"name": "RingCentral",           "group": "Video Conferencing", "processes": ["RingCentral", "RingCentralMeetings"],                          "enabled": True},
    {"name": "Google Chat",           "group": "Messaging",          "processes": ["googlechat"],                                                   "enabled": True},
    {"name": "Google Meet (Chrome)",  "group": "Video Conferencing", "processes": [],                                                               "enabled": False},  # browser-based
    # ── Chat / Messaging ─────────────────────────────────────────────────────
    {"name": "Slack",                 "group": "Messaging",          "processes": ["slack"],                                                        "enabled": True},
    {"name": "Discord",               "group": "Messaging",          "processes": ["Discord", "DiscordPTB", "DiscordCanary"],                      "enabled": True},
    {"name": "Telegram",              "group": "Messaging",          "processes": ["Telegram", "Telegram Desktop"],                                 "enabled": True},
    {"name": "Signal",                "group": "Messaging",          "processes": ["Signal"],                                                       "enabled": True},
    {"name": "LINE",                  "group": "Messaging",          "processes": ["LINE"],                                                          "enabled": True},
    {"name": "WeChat",                "group": "Messaging",          "processes": ["WeChat", "WeChatApp"],                                          "enabled": True},
    {"name": "Viber",                 "group": "Messaging",          "processes": ["Viber"],                                                        "enabled": True},
    {"name": "Snapchat",              "group": "Messaging",          "processes": ["Snapchat"],                                                     "enabled": True},
    {"name": "Element / Matrix",      "group": "Messaging",          "processes": ["Element"],                                                      "enabled": True},
    {"name": "Mattermost",            "group": "Messaging",          "processes": ["Mattermost"],                                                   "enabled": True},
    {"name": "Rocket.Chat",           "group": "Messaging",          "processes": ["rocketchat"],                                                   "enabled": True},
    {"name": "Wire",                  "group": "Messaging",          "processes": ["Wire"],                                                          "enabled": True},
    {"name": "Flock",                 "group": "Messaging",          "processes": ["Flock"],                                                        "enabled": True},
    {"name": "Chanty",                "group": "Messaging",          "processes": ["Chanty"],                                                       "enabled": True},
    {"name": "Keybase",               "group": "Messaging",          "processes": ["Keybase"],                                                      "enabled": True},
    # ── Remote desktop / screen share ────────────────────────────────────────
    {"name": "TeamViewer",            "group": "Screen Sharing",     "processes": ["TeamViewer", "TeamViewer_Service", "tv_w32", "tv_x64"],        "enabled": True},
    {"name": "AnyDesk",               "group": "Screen Sharing",     "processes": ["AnyDesk"],                                                      "enabled": True},
    {"name": "Chrome Remote Desktop", "group": "Screen Sharing",     "processes": ["remoting_host", "remoting_desktop"],                           "enabled": True},
    {"name": "LogMeIn",               "group": "Screen Sharing",     "processes": ["LogMeIn", "LMIGuardianSvc", "LogMeInSystray"],                 "enabled": True},
    {"name": "Splashtop",             "group": "Screen Sharing",     "processes": ["SplashtopStreamer", "SRService", "SRFeature"],                  "enabled": True},
    {"name": "VNC",                   "group": "Screen Sharing",     "processes": ["vncviewer", "vncserver", "winvnc4", "tvnserver", "VNC-Server"], "enabled": True},
    {"name": "Parsec",                "group": "Screen Sharing",     "processes": ["parsecd", "Parsec"],                                            "enabled": True},
    {"name": "Rustdesk",              "group": "Screen Sharing",     "processes": ["rustdesk"],                                                      "enabled": True},
    {"name": "Ammyy Admin",           "group": "Screen Sharing",     "processes": ["AA_v3", "AMMYY"],                                               "enabled": True},
    {"name": "DameWare",              "group": "Screen Sharing",     "processes": ["DWRCS"],                                                        "enabled": True},
    {"name": "ConnectWise Control",   "group": "Screen Sharing",     "processes": ["ScreenConnect.WindowsClient", "ScreenConnect.Service", "screenconnect"], "enabled": True},
    {"name": "GoToMyPC",              "group": "Screen Sharing",     "processes": ["g2comm", "g2pre", "g2svc"],                                    "enabled": True},
    {"name": "NoMachine",             "group": "Screen Sharing",     "processes": ["nxservice", "nxnode", "nxserver", "NoMachine"],                "enabled": True},
    {"name": "Radmin",                "group": "Screen Sharing",     "processes": ["Radmin", "RServer3", "rfusclient"],                             "enabled": True},
    {"name": "DWService",             "group": "Screen Sharing",     "processes": ["dwservice", "DWAgent"],                                         "enabled": True},
    {"name": "Supremo",               "group": "Screen Sharing",     "processes": ["Supremo"],                                                      "enabled": True},
    {"name": "Bomgar / BeyondTrust",  "group": "Screen Sharing",     "processes": ["Bomgar", "bomgar-scc"],                                        "enabled": True},
    # ── VPN ──────────────────────────────────────────────────────────────────
    {"name": "OpenVPN",               "group": "VPN",                "processes": ["openvpn", "openvpn-gui", "openvpnserv"],                       "enabled": True},
    {"name": "WireGuard",             "group": "VPN",                "processes": ["wireguard", "wg", "wg-quick"],                                 "enabled": True},
    {"name": "NordVPN",               "group": "VPN",                "processes": ["nordvpn", "NordVPN", "nordvpnservice"],                        "enabled": True},
    {"name": "ExpressVPN",            "group": "VPN",                "processes": ["expressvpn", "ExpressVPN", "expressvpnservice"],               "enabled": True},
    {"name": "CyberGhost",            "group": "VPN",                "processes": ["cyberghost", "CyberGhost", "CyberGhost.Service"],              "enabled": True},
    {"name": "Surfshark",             "group": "VPN",                "processes": ["surfshark", "Surfshark", "SurfsharkService"],                  "enabled": True},
    {"name": "IPVanish",              "group": "VPN",                "processes": ["ipvanish", "IPVanish", "IPVanishService"],                     "enabled": True},
    {"name": "PureVPN",               "group": "VPN",                "processes": ["purevpn", "PureVPN", "PureVPNService"],                        "enabled": True},
    {"name": "HotspotShield",         "group": "VPN",                "processes": ["hotspotshield", "HotspotShield", "HssWPR", "HssSrv", "HssCP"], "enabled": True},
    {"name": "TunnelBear",            "group": "VPN",                "processes": ["tunnelbear", "TunnelBear", "TunnelBearService"],               "enabled": True},
    {"name": "Windscribe",            "group": "VPN",                "processes": ["windscribe", "Windscribe", "WindscribeService"],               "enabled": True},
    {"name": "ProtonVPN",             "group": "VPN",                "processes": ["protonvpn", "ProtonVPN", "ProtonVPNService"],                  "enabled": True},
    {"name": "Mullvad VPN",           "group": "VPN",                "processes": ["mullvad", "Mullvad", "mullvad-daemon"],                        "enabled": True},
    {"name": "Private Internet Access","group": "VPN",               "processes": ["pia", "PrivateInternetAccess", "pia-service"],                 "enabled": True},
    {"name": "VyprVPN",               "group": "VPN",                "processes": ["vyprvpn", "VyprVPN", "VyprVPNService"],                        "enabled": True},
    {"name": "HideMyAss",             "group": "VPN",                "processes": ["hidemyass", "HideMyAss", "HMAService"],                        "enabled": True},
    {"name": "AtlasVPN",              "group": "VPN",                "processes": ["atlas", "AtlasVPN"],                                            "enabled": True},
    {"name": "StrongVPN",             "group": "VPN",                "processes": ["strongvpn", "StrongVPN"],                                       "enabled": True},
    {"name": "TorGuard",              "group": "VPN",                "processes": ["torguard", "TorGuard"],                                         "enabled": True},
    {"name": "Astrill",               "group": "VPN",                "processes": ["astrill", "Astrill"],                                           "enabled": True},
    {"name": "Cisco AnyConnect",      "group": "VPN",                "processes": ["vpnui", "cvpnd", "ipsecdialer", "CiscoVPN"],                   "enabled": True},
    {"name": "FortiClient VPN",       "group": "VPN",                "processes": ["FortiClient", "FortiSSLVPNdaemon", "FortiTray"],               "enabled": True},
    {"name": "GlobalProtect",         "group": "VPN",                "processes": ["PanGPS", "PanGPA", "GlobalProtect"],                           "enabled": True},
    {"name": "SonicWall NetExtender", "group": "VPN",                "processes": ["SWGVpnClient", "NetExtender"],                                 "enabled": True},
    {"name": "Check Point VPN",       "group": "VPN",                "processes": ["trac", "TracSrvWrapper", "cpservice"],                         "enabled": True},
    {"name": "Juniper VPN",           "group": "VPN",                "processes": ["dsAccessService", "JuniperAccessService"],                     "enabled": True},
]

# ═══════════════════════════════════════════════════════════════════════════════
#  Config
# ═══════════════════════════════════════════════════════════════════════════════

def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            defaults_by_name = {d["name"]: d for d in DEFAULT_APPS}
            existing = {a["name"] for a in data.get("apps", [])}
            # Backfill missing group field for existing apps
            for app in data.get("apps", []):
                if "group" not in app and app["name"] in defaults_by_name:
                    app["group"] = defaults_by_name[app["name"]].get("group", "Other")
                elif "group" not in app:
                    app["group"] = "Other"
            # Merge in new default apps added in future versions
            for default in DEFAULT_APPS:
                if default["name"] not in existing:
                    data.setdefault("apps", []).append(default)
            return data
        except Exception:
            pass
    config: dict = {"apps": [dict(a) for a in DEFAULT_APPS], "autostart": True, "notify": True}
    save_config(config)
    return config


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

# ═══════════════════════════════════════════════════════════════════════════════
#  Auto-start (registry)
# ═══════════════════════════════════════════════════════════════════════════════

def _launch_cmd() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{Path(sys.argv[0]).resolve()}"'


def set_autostart(enable: bool) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _launch_cmd())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except Exception as e:
        print(f"[autostart] {e}", file=sys.stderr)


def get_autostart() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_REG, 0,
                            winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except FileNotFoundError:
        return False

# ═══════════════════════════════════════════════════════════════════════════════
#  Process killing
# ═══════════════════════════════════════════════════════════════════════════════

def kill_apps(config: dict, group: str | None = None) -> tuple[int, list[str]]:
    """Kill every enabled app process (optionally filtered by group).
    Returns (count_killed, [display_names])."""
    targets: dict[str, str] = {}
    for app in config.get("apps", []):
        if not app.get("enabled", True):
            continue
        if group is not None and app.get("group", "Other") != group:
            continue
        for proc in app.get("processes", []):
            if not proc:
                continue
            nl = proc.lower()
            targets[nl]          = app["name"]
            targets[nl + ".exe"] = app["name"]

    killed: list[str] = []
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name in targets and name not in _SAFE_PROCS:
                app_name = targets[name]
                proc.kill()
                if app_name not in killed:
                    killed.append(app_name)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    return len(killed), killed

# ═══════════════════════════════════════════════════════════════════════════════
#  Tray icon image
# ═══════════════════════════════════════════════════════════════════════════════

def make_icon_image() -> Image.Image:
    """Red circle with a white X — universal 'stop/kill' symbol."""
    sz = 64
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, sz - 3, sz - 3], fill=(210, 38, 38, 255), outline=(150, 18, 18, 255), width=3)
    pad, lw = 16, 10
    d.line([pad, pad, sz - pad, sz - pad], fill=(255, 255, 255, 255), width=lw)
    d.line([sz - pad, pad, pad, sz - pad], fill=(255, 255, 255, 255), width=lw)
    return img

# ═══════════════════════════════════════════════════════════════════════════════
#  Settings UI (runs in a subprocess via --settings flag)
# ═══════════════════════════════════════════════════════════════════════════════

class _AddEditDialog(tk.Toplevel):
    """Modal dialog to add or edit an app entry."""

    def __init__(self, parent: tk.Misc, title: str, app: dict):
        super().__init__(parent)
        self.result: dict | None = None
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        pad = {"padx": 10, "pady": 5}

        ttk.Label(self, text="Display name:").grid(row=0, column=0, sticky="w", **pad)
        self._name = tk.StringVar(value=app.get("name", ""))
        ttk.Entry(self, textvariable=self._name, width=38).grid(row=0, column=1, **pad)

        ttk.Label(self, text="Group:").grid(row=1, column=0, sticky="w", **pad)
        self._group = tk.StringVar(value=app.get("group", "Other"))
        ttk.Combobox(self, textvariable=self._group, values=APP_GROUPS,
                     state="readonly", width=35).grid(row=1, column=1, **pad)

        ttk.Label(self, text="Process name(s)\n(comma-separated):").grid(row=2, column=0, sticky="nw", **pad)
        self._procs = tk.StringVar(value=", ".join(app.get("processes", [])))
        ttk.Entry(self, textvariable=self._procs, width=38).grid(row=2, column=1, **pad)

        self._enabled = tk.BooleanVar(value=app.get("enabled", True))
        ttk.Checkbutton(self, text="Enabled", variable=self._enabled).grid(
            row=3, column=0, columnspan=2, sticky="w", padx=10, pady=2)

        btn = ttk.Frame(self)
        btn.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(btn, text="OK",     command=self._ok,      width=10).pack(side="left", padx=4)
        ttk.Button(btn, text="Cancel", command=self.destroy,  width=10).pack(side="left", padx=4)

        self.bind("<Return>", lambda _: self._ok())
        self.bind("<Escape>", lambda _: self.destroy())
        self._center(parent)
        parent.wait_window(self)

    def _center(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        dw, dh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

    def _ok(self) -> None:
        name  = self._name.get().strip()
        procs = [p.strip() for p in self._procs.get().split(",") if p.strip()]
        if not name:
            messagebox.showerror("Error", "Display name cannot be empty.", parent=self)
            return
        if not procs:
            messagebox.showerror("Error", "Enter at least one process name.", parent=self)
            return
        self.result = {
            "name": name,
            "group": self._group.get() or "Other",
            "processes": procs,
            "enabled": self._enabled.get(),
        }
        self.destroy()


class _ScanDialog(tk.Toplevel):
    """Shows running processes not already covered by the config."""

    def __init__(self, parent: tk.Misc, procs: list[str], on_add):
        super().__init__(parent)
        self.title("Scan Results — Select Processes to Add")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.minsize(420, 320)

        ttk.Label(self, text="Running processes not in your kill list.\n"
                             "Select one or more to add as new entries:",
                  justify="left").pack(anchor="w", padx=12, pady=(10, 4))

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=12, pady=4)
        sb = ttk.Scrollbar(frame, orient="vertical")
        self._lb = tk.Listbox(frame, selectmode="extended", yscrollcommand=sb.set,
                              font=("Consolas", 9), activestyle="none")
        sb.configure(command=self._lb.yview)
        self._lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for p in procs:
            self._lb.insert("end", p)

        row = ttk.Frame(self)
        row.pack(fill="x", padx=12, pady=8)
        ttk.Button(row, text="Add Selected", command=lambda: self._add(on_add)).pack(side="left")
        ttk.Button(row, text="Close",        command=self.destroy).pack(side="right")

        self.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        dw, dh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 2}")

        parent.wait_window(self)

    def _add(self, on_add) -> None:
        selected = [self._lb.get(i) for i in self._lb.curselection()]
        if selected:
            on_add(selected)
        self.destroy()


def run_settings() -> None:
    """Full settings UI — launched as a subprocess with --settings."""
    config = load_config()
    apps: list[dict] = [dict(a) for a in config.get("apps", [])]

    root = tk.Tk()
    root.title(f"{APP_NAME}  v{APP_VERSION}  — Settings")
    root.resizable(True, True)
    root.minsize(740, 500)

    try:
        ttk.Style(root).theme_use("vista")
    except Exception:
        pass

    root.update_idletasks()
    W, H = 900, 580
    root.geometry(f"{W}x{H}+{(root.winfo_screenwidth()  - W) // 2}"
                           f"+{(root.winfo_screenheight() - H) // 2}")

    main = ttk.Frame(root, padding=12)
    main.pack(fill="both", expand=True)

    # ── Filter row
    filter_row = ttk.Frame(main)
    filter_row.pack(fill="x", pady=(0, 6))

    ttk.Label(filter_row, text="Show group:").pack(side="left")
    filter_var = tk.StringVar(value="All Groups")
    filter_cb = ttk.Combobox(filter_row, textvariable=filter_var,
                             values=["All Groups"] + APP_GROUPS,
                             state="readonly", width=22)
    filter_cb.pack(side="left", padx=(6, 0))

    # ── App list label
    ttk.Label(main,
              text="Apps to kill when you trigger KillSwitch  "
                   "(double-click or Space to toggle on/off):",
              font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))

    # ── Treeview
    lf = ttk.Frame(main)
    lf.pack(fill="both", expand=True)

    tree = ttk.Treeview(lf, columns=("on", "group", "name", "procs"),
                        show="headings", selectmode="browse")
    tree.heading("on",    text="On/Off")
    tree.heading("group", text="Group")
    tree.heading("name",  text="App Name")
    tree.heading("procs", text="Process Name(s)")
    tree.column("on",    width=58,  anchor="center", stretch=False)
    tree.column("group", width=140, anchor="w",      stretch=False)
    tree.column("name",  width=200, anchor="w")
    tree.column("procs", width=430, anchor="w")

    vsb = ttk.Scrollbar(lf, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    tree.tag_configure("off", foreground="#9a9a9a")

    # Map tree item id -> index into `apps`
    _item_to_idx: dict[str, int] = {}

    def refresh() -> None:
        _item_to_idx.clear()
        sel = tree.selection()
        # Remember selected app name so we can restore selection after rebuild
        sel_name = None
        if sel:
            vals = tree.item(sel[0], "values")
            sel_name = vals[2] if vals else None

        for item in tree.get_children():
            tree.delete(item)

        gfilter = filter_var.get()
        for idx, app in enumerate(apps):
            if gfilter != "All Groups" and app.get("group", "Other") != gfilter:
                continue
            on_str = "✓  on" if app.get("enabled", True) else "✗  off"
            procs  = ", ".join(app.get("processes", [])) or "(none — browser-based)"
            tags   = () if app.get("enabled", True) else ("off",)
            iid = tree.insert("", "end", values=(on_str, app.get("group", "Other"), app["name"], procs), tags=tags)
            _item_to_idx[iid] = idx

        if sel_name:
            for iid in tree.get_children():
                if tree.item(iid, "values")[2] == sel_name:
                    tree.selection_set(iid)
                    tree.see(iid)
                    break

    filter_cb.bind("<<ComboboxSelected>>", lambda _: refresh())
    refresh()

    def selected_idx() -> int | None:
        sel = tree.selection()
        if not sel:
            return None
        return _item_to_idx.get(sel[0])

    def toggle(event=None) -> None:
        idx = selected_idx()
        if idx is None:
            return
        apps[idx]["enabled"] = not apps[idx].get("enabled", True)
        refresh()

    tree.bind("<Double-1>", toggle)
    tree.bind("<space>",    toggle)

    # ── Button row
    btn_row = ttk.Frame(main)
    btn_row.pack(fill="x", pady=(6, 0))

    def add_app() -> None:
        dlg = _AddEditDialog(root, "Add App", {"group": filter_var.get() if filter_var.get() != "All Groups" else "Other"})
        if dlg.result:
            apps.append(dlg.result)
            refresh()

    def edit_app() -> None:
        idx = selected_idx()
        if idx is None:
            messagebox.showinfo("No selection", "Select an app first.", parent=root)
            return
        dlg = _AddEditDialog(root, "Edit App", apps[idx])
        if dlg.result:
            apps[idx] = dlg.result
            refresh()

    def remove_app() -> None:
        idx = selected_idx()
        if idx is None:
            messagebox.showinfo("No selection", "Select an app first.", parent=root)
            return
        if messagebox.askyesno("Remove", f"Remove \"{apps[idx]['name']}\"?", parent=root):
            apps.pop(idx)
            refresh()

    def scan_running() -> None:
        covered: set[str] = set()
        for app in apps:
            for p in app.get("processes", []):
                covered.add(p.lower())
                covered.add(p.lower() + ".exe")

        found: list[str] = []
        seen:  set[str]  = set()
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info["name"] or ""
                nl   = name.lower()
                if nl and nl not in covered and nl not in seen and nl not in _SAFE_PROCS:
                    found.append(name)
                    seen.add(nl)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        found.sort(key=str.lower)

        if not found:
            messagebox.showinfo("Scan Complete",
                                "No additional running processes found\n"
                                "(all running apps are already in your list).",
                                parent=root)
            return

        def on_add(selected: list[str]) -> None:
            for p in selected:
                apps.append({"name": p, "group": "Other", "processes": [p], "enabled": True})
            refresh()

        _ScanDialog(root, found, on_add)

    ttk.Button(btn_row, text="Add App",           command=add_app).pack(side="left", padx=2)
    ttk.Button(btn_row, text="Edit",              command=edit_app).pack(side="left", padx=2)
    ttk.Button(btn_row, text="Remove",            command=remove_app).pack(side="left", padx=2)
    ttk.Separator(btn_row, orient="vertical").pack(side="left", padx=10, fill="y")
    ttk.Button(btn_row, text="Scan Running Apps", command=scan_running).pack(side="left", padx=2)

    # ── Options
    ttk.Separator(main, orient="horizontal").pack(fill="x", pady=(12, 6))

    opt_row = ttk.Frame(main)
    opt_row.pack(fill="x")

    autostart_var = tk.BooleanVar(value=get_autostart())
    notify_var    = tk.BooleanVar(value=config.get("notify", True))

    ttk.Checkbutton(opt_row, text="Start with Windows",
                    variable=autostart_var).pack(side="left", padx=(0, 24))
    ttk.Checkbutton(opt_row, text="Show a notification after killing apps",
                    variable=notify_var).pack(side="left")

    # ── Save / Cancel
    save_row = ttk.Frame(main)
    save_row.pack(fill="x", pady=(10, 0))

    def save() -> None:
        config["apps"]      = apps
        config["autostart"] = autostart_var.get()
        config["notify"]    = notify_var.get()
        save_config(config)
        set_autostart(autostart_var.get())
        root.destroy()

    ttk.Button(save_row, text="Cancel", command=root.destroy, width=10).pack(side="right", padx=(4, 0))
    ttk.Button(save_row, text="Save",   command=save,          width=10).pack(side="right")

    root.mainloop()

# ═══════════════════════════════════════════════════════════════════════════════
#  Tray app
# ═══════════════════════════════════════════════════════════════════════════════

_MUTEX_NAME = f"Global\\{APP_NAME}_SingleInstance"

def _acquire_mutex() -> bool:
    """Return True if we are the first instance."""
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    return ctypes.windll.kernel32.GetLastError() != 183  # 183 = ERROR_ALREADY_EXISTS


def _spawn_settings() -> None:
    """Launch a settings window in a separate process."""
    CREATE_NO_WINDOW = 0x08000000
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--settings"]
    else:
        cmd = [sys.executable, str(Path(sys.argv[0]).resolve()), "--settings"]
    subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW)


def _make_group_killer(group: str):
    """Factory to create a group-specific kill callback (avoids closure capture issues)."""
    def _kill(icon, item=None):
        c = _fresh_config[0]
        count, killed = kill_apps(c, group=group)
        if c.get("notify", True):
            if killed:
                icon.notify(f"[{group}] Killed: {', '.join(killed)}", APP_NAME)
            else:
                icon.notify(f"[{group}] No apps were running.", APP_NAME)
    return _kill


_fresh_config: list[dict] = [{}]  # shared mutable holder


def run_tray() -> None:
    if not _acquire_mutex():
        sys.exit(0)

    _fresh_config[0] = load_config()

    def cfg() -> dict:
        _fresh_config[0] = load_config()
        return _fresh_config[0]

    def do_kill(icon, item=None) -> None:
        c = cfg()
        count, killed = kill_apps(c)
        if c.get("notify", True):
            if killed:
                icon.notify(f"Killed: {', '.join(killed)}", APP_NAME)
            else:
                icon.notify("No target apps were running.", APP_NAME)

    def do_settings(icon, item=None) -> None:
        _spawn_settings()

    def do_exit(icon, item=None) -> None:
        icon.stop()

    group_items = tuple(
        pystray.MenuItem(group, _make_group_killer(group))
        for group in APP_GROUPS
    )

    menu = pystray.Menu(
        pystray.MenuItem("Kill All Now", do_kill, default=True),
        pystray.MenuItem("Kill by Group…", pystray.Menu(*group_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings…",   do_settings),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit",        do_exit),
    )

    icon = pystray.Icon(
        APP_NAME,
        make_icon_image(),
        f"{APP_NAME} — double-click to kill all  |  right-click for menu",
        menu,
    )

    if cfg().get("autostart", True):
        set_autostart(True)

    icon.run()

# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--settings" in sys.argv:
        run_settings()
    else:
        run_tray()
