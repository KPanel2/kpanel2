import subprocess
import shutil
import tkinter as tk

from kpanel_client.brand_ui import COLORS, apply_window_style, primary_button, secondary_button


def _scan_ssids(skip_known_networks: bool) -> list[str]:
    command = [
        "nmcli",
        "-t",
        "-f",
        "SSID",
        "dev",
        "wifi",
        "list",
        "--rescan",
        "yes",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return []

    ssids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    deduped = []
    seen = set()
    for ssid in ssids:
        if ssid in seen:
            continue
        seen.add(ssid)
        deduped.append(ssid)

    if not skip_known_networks:
        return deduped

    known_result = subprocess.run(
        ["nmcli", "-t", "-f", "NAME", "connection", "show"],
        capture_output=True,
        text=True,
        check=False,
    )
    if known_result.returncode != 0:
        return deduped

    known_names = {line.strip() for line in known_result.stdout.splitlines() if line.strip()}
    return [ssid for ssid in deduped if ssid not in known_names]


def connect_wifi(ssid: str, password: str, timeout_sec: int) -> bool:
    if not ssid:
        return False

    cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        cmd.extend(["password", password])
    cmd.extend(["--wait", str(timeout_sec)])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0


def _launch_onscreen_keyboard(existing_pid: int | None) -> int | None:
    if existing_pid:
        try:
            # Keep one keyboard process around instead of spawning duplicates.
            if subprocess.run(["kill", "-0", str(existing_pid)], check=False).returncode == 0:
                return existing_pid
        except Exception:
            pass

    candidates = [
        ["onboard"],
        ["matchbox-keyboard"],
        ["wvkbd-mobintl"],
        ["wvkbd"],
    ]

    for cmd in candidates:
        if not shutil.which(cmd[0]):
            continue
        try:
            proc = subprocess.Popen(cmd)
            return proc.pid
        except Exception:
            continue
    return None


def prompt_and_connect_wifi(timeout_sec: int, skip_known_networks: bool) -> str:
    ssids = _scan_ssids(skip_known_networks)
    if not ssids:
        return "no-networks"

    root = tk.Tk()
    apply_window_style(root, "KPanel Wi-Fi Setup")
    # Borderless fullscreen windows can lose text focus on some Pi setups.
    # Keep a managed fullscreen window so keyboard input reaches Entry widgets.
    root.overrideredirect(False)
    root.attributes("-fullscreen", True)

    selected_ssid = tk.StringVar(value=ssids[0] if ssids else "")
    manual_ssid = tk.StringVar(value="")
    password = tk.StringVar(value="")
    connected = {"status": "cancelled"}
    osk_pid: int | None = None

    outer = tk.Frame(root, bg=COLORS["surface"])
    outer.pack(fill="both", expand=True, padx=48, pady=36)

    header = tk.Frame(outer, bg=COLORS["surface"])
    header.pack(fill="x")
    tk.Label(
        header,
        text="Network Setup",
        fg=COLORS["accent"],
        bg=COLORS["surface"],
        font=("Inter", 14, "bold"),
    ).pack(anchor="center")
    tk.Label(
        header,
        text="Join a Wi-Fi network.",
        fg=COLORS["text"],
        bg=COLORS["surface"],
        font=("Space Grotesk", 32, "bold"),
    ).pack(anchor="center", pady=(8, 10))
    tk.Label(
        header,
        text="Internet is unavailable. Select a wireless network and enter the password to continue panel provisioning.",
        fg=COLORS["muted"],
        bg=COLORS["surface"],
        font=("Inter", 14),
        justify="center",
        wraplength=980,
    ).pack(anchor="center")

    form_card = tk.Frame(
        outer,
        bg=COLORS["surface_2"],
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        padx=24,
        pady=18,
    )
    form_card.pack(fill="x", pady=(24, 0))

    label_width = 18
    field_font = ("Inter", 14)
    label_font = ("Inter", 14, "bold")

    status_label = tk.Label(
        outer,
        text="",
        fg=COLORS["danger"],
        bg=COLORS["surface"],
        font=("Inter", 12, "bold"),
    )
    status_label.pack(side="bottom", anchor="center", pady=(0, 8))

    btn_frame = tk.Frame(outer, bg=COLORS["surface"])
    btn_frame.pack(side="bottom", anchor="center", pady=(0, 16))

    form = tk.Frame(form_card, bg=COLORS["surface_2"])
    form.pack(fill="x")

    ssid_frame = tk.Frame(form, bg=COLORS["surface_2"])
    ssid_frame.pack(fill="x", pady=8)
    tk.Label(
        ssid_frame,
        text="Wi-Fi network",
        width=label_width,
        anchor="w",
        fg=COLORS["text"],
        bg=COLORS["surface_2"],
        font=label_font,
    ).pack(side="left")

    if ssids:
        option_menu = tk.OptionMenu(ssid_frame, selected_ssid, *ssids)
        option_menu.config(
            width=40,
            bg=COLORS["surface_2"],
            fg=COLORS["text"],
            activebackground=COLORS["surface"],
            activeforeground=COLORS["text"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            font=field_font,
        )
        option_menu["menu"].config(
            bg=COLORS["surface_2"],
            fg=COLORS["text"],
            activebackground=COLORS["primary_2"],
            activeforeground=COLORS["text"],
            font=field_font,
        )
        option_menu.pack(side="left", fill="x", expand=True)
    else:
        ssid_entry = tk.Entry(
            ssid_frame,
            textvariable=selected_ssid,
            bg=COLORS["surface_2"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            font=field_font,
            takefocus=True,
        )
        ssid_entry.pack(side="left", fill="x", expand=True)

    manual_ssid_frame = tk.Frame(form, bg=COLORS["surface_2"])
    manual_ssid_frame.pack(fill="x", pady=8)
    tk.Label(
        manual_ssid_frame,
        text="Manual SSID",
        width=label_width,
        anchor="w",
        fg=COLORS["text"],
        bg=COLORS["surface_2"],
        font=label_font,
    ).pack(side="left")
    manual_ssid_entry = tk.Entry(
        manual_ssid_frame,
        textvariable=manual_ssid,
        bg=COLORS["surface_2"],
        fg=COLORS["text"],
        insertbackground=COLORS["text"],
        relief="flat",
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        font=field_font,
        takefocus=True,
    )
    manual_ssid_entry.pack(side="left", fill="x", expand=True)

    pw_frame = tk.Frame(form, bg=COLORS["surface_2"])
    pw_frame.pack(fill="x", pady=8)
    tk.Label(
        pw_frame,
        text="Password",
        width=label_width,
        anchor="w",
        fg=COLORS["text"],
        bg=COLORS["surface_2"],
        font=label_font,
    ).pack(side="left")
    pw_entry = tk.Entry(
        pw_frame,
        textvariable=password,
        show="*",
        bg=COLORS["surface_2"],
        fg=COLORS["text"],
        insertbackground=COLORS["text"],
        relief="flat",
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        font=field_font,
        takefocus=True,
    )
    pw_entry.pack(side="left", fill="x", expand=True)

    def ensure_text_focus(entry: tk.Entry) -> None:
        root.focus_force()
        entry.focus_set()

    def on_entry_focus(event: tk.Event) -> None:
        nonlocal osk_pid
        widget = event.widget
        if isinstance(widget, tk.Entry):
            ensure_text_focus(widget)
            osk_pid = _launch_onscreen_keyboard(osk_pid)

    for entry in (manual_ssid_entry, pw_entry):
        entry.bind("<Button-1>", on_entry_focus)
        entry.bind("<FocusIn>", on_entry_focus)

    def on_connect() -> None:
        status_label.config(text="Connecting...", fg=COLORS["primary"])
        root.update_idletasks()
        ssid = manual_ssid.get().strip() or selected_ssid.get().strip()
        ok = connect_wifi(ssid, password.get(), timeout_sec)
        if ok:
            connected["status"] = "connected"
            status_label.config(text="Wi-Fi connected successfully.", fg=COLORS["accent"])
            root.destroy()
        else:
            status_label.config(
                text="Connection failed. Check credentials and try again.",
                fg=COLORS["danger"],
            )

    def on_skip() -> None:
        on_close()

    def on_close() -> None:
        if osk_pid:
            subprocess.run(["kill", str(osk_pid)], check=False)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.bind("<Escape>", lambda _event: on_close())
    root.bind("<Button-1>", lambda _event: root.focus_force())

    secondary_button(btn_frame, "Skip", on_skip).pack(side="right", padx=(12, 0))
    primary_button(btn_frame, "Connect", on_connect).pack(side="right")

    root.after(100, lambda: manual_ssid_entry.focus_force())

    root.mainloop()
    return connected["status"]
