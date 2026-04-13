import subprocess
import tkinter as tk

from kpanel_client.brand_ui import COLORS, apply_window_style, build_shell, primary_button, secondary_button


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


def prompt_and_connect_wifi(timeout_sec: int, skip_known_networks: bool) -> str:
    ssids = _scan_ssids(skip_known_networks)
    if not ssids:
        return "no-networks"

    root = tk.Tk()
    apply_window_style(root, "KPanel Wi-Fi Setup")

    selected_ssid = tk.StringVar(value=ssids[0] if ssids else "")
    password = tk.StringVar(value="")
    connected = {"status": "cancelled"}

    panel = build_shell(
        root,
        kicker="Network Setup",
        heading="Join a Wi-Fi network.",
        body="Internet is unavailable. Select a wireless network and enter the password to continue panel provisioning.",
    )

    form = tk.Frame(panel, bg=COLORS["surface"])
    form.pack(fill="x", pady=(12, 0))

    ssid_frame = tk.Frame(form, bg=COLORS["surface"])
    ssid_frame.pack(fill="x", pady=8)
    tk.Label(
        ssid_frame,
        text="Wi-Fi network",
        width=16,
        anchor="w",
        fg=COLORS["text"],
        bg=COLORS["surface"],
        font=("Inter", 12, "bold"),
    ).pack(side="left")

    if ssids:
        option_menu = tk.OptionMenu(ssid_frame, selected_ssid, *ssids)
        option_menu.config(
            width=36,
            bg=COLORS["surface_2"],
            fg=COLORS["text"],
            activebackground=COLORS["surface"],
            activeforeground=COLORS["text"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            font=("Inter", 12),
        )
        option_menu["menu"].config(
            bg=COLORS["surface_2"],
            fg=COLORS["text"],
            activebackground=COLORS["primary_2"],
            activeforeground=COLORS["text"],
            font=("Inter", 12),
        )
        option_menu.pack(side="left", fill="x", expand=True)
    else:
        tk.Entry(
            ssid_frame,
            textvariable=selected_ssid,
            bg=COLORS["surface_2"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            font=("Inter", 12),
        ).pack(side="left", fill="x", expand=True)

    pw_frame = tk.Frame(form, bg=COLORS["surface"])
    pw_frame.pack(fill="x", pady=8)
    tk.Label(
        pw_frame,
        text="Password",
        width=16,
        anchor="w",
        fg=COLORS["text"],
        bg=COLORS["surface"],
        font=("Inter", 12, "bold"),
    ).pack(side="left")
    tk.Entry(
        pw_frame,
        textvariable=password,
        show="*",
        bg=COLORS["surface_2"],
        fg=COLORS["text"],
        insertbackground=COLORS["text"],
        relief="flat",
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        font=("Inter", 12),
    ).pack(side="left", fill="x", expand=True)

    status_label = tk.Label(
        panel,
        text="",
        fg=COLORS["danger"],
        bg=COLORS["surface"],
        font=("Inter", 11, "bold"),
    )
    status_label.pack(anchor="w", pady=(18, 0))

    def on_connect() -> None:
        status_label.config(text="Connecting...", fg=COLORS["primary"])
        root.update_idletasks()
        ok = connect_wifi(selected_ssid.get().strip(), password.get(), timeout_sec)
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
        root.destroy()

    btn_frame = tk.Frame(panel, bg=COLORS["surface"])
    btn_frame.pack(anchor="e", pady=(18, 0))
    secondary_button(btn_frame, "Skip", on_skip).pack(side="right", padx=(12, 0))
    primary_button(btn_frame, "Connect", on_connect).pack(side="right")

    root.mainloop()
    return connected["status"]
