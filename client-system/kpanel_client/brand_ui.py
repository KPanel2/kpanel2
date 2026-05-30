from pathlib import Path
import tkinter as tk


COLORS = {
    "bg": "#07111D",
    "surface": "#0F233D",
    "surface_2": "#0B1D33",
    "text": "#F4FBFF",
    "muted": "#9BB3C9",
    "primary": "#22C7FF",
    "primary_2": "#1A6DFF",
    "accent": "#8BE71E",
    "border": "#214261",
    "danger": "#FF6B7A",
}


def _asset_path(filename: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / filename


def apply_window_style(root: tk.Tk | tk.Toplevel, title: str, geometry: str = "1024x600") -> None:
    root.title(title)
    root.configure(bg=COLORS["surface"])
    root.overrideredirect(True)
    root.attributes("-fullscreen", True)
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{screen_width}x{screen_height}+0+0")
    root.minsize(800, 480)


def _font_sizes(root: tk.Tk | tk.Toplevel) -> tuple[int, int, int]:
    screen_width = root.winfo_screenwidth()
    if screen_width >= 1600:
        return (13, 34, 16)
    if screen_width >= 1280:
        return (12, 30, 14)
    return (11, 24, 13)


def build_shell(root: tk.Tk | tk.Toplevel, kicker: str, heading: str, body: str) -> tk.Frame:
    kicker_size, heading_size, body_size = _font_sizes(root)
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    side_pad = max(32, screen_width // 18)
    wraplength = max(400, screen_width - side_pad * 2 - 80)

    outer = tk.Frame(root, bg=COLORS["surface"])
    outer.pack(fill="both", expand=True)

    panel = tk.Frame(
        outer,
        bg=COLORS["surface"],
    )
    panel.pack(fill="both", expand=True)

    content = tk.Frame(
        panel,
        bg=COLORS["surface"],
        padx=max(32, screen_width // 18),
        pady=max(28, screen_height // 18),
    )
    content.pack(fill="both", expand=True)

    # Keep header content natural-height so bottom form controls remain visible.
    header = tk.Frame(content, bg=COLORS["surface"])
    header.pack(fill="x", expand=False)

    logo_w = int(screen_width * 0.18)
    logo_h = int(screen_height * 0.14)
    logo = load_logo_label(header, max_width=logo_w, max_height=logo_h)
    if logo is not None:
        logo.pack(anchor="center", pady=(0, 24))

    copy = tk.Frame(header, bg=COLORS["surface"])
    copy.pack(fill="both", expand=True)

    tk.Label(
        copy,
        text=kicker,
        fg=COLORS["accent"],
        bg=COLORS["surface"],
        font=("Inter", kicker_size, "bold"),
    ).pack(anchor="center")
    tk.Label(
        copy,
        text=heading,
        fg=COLORS["text"],
        bg=COLORS["surface"],
        font=("Space Grotesk", heading_size, "bold"),
        justify="center",
        wraplength=wraplength,
    ).pack(anchor="center", pady=(8, 12))
    tk.Label(
        copy,
        text=body,
        fg=COLORS["muted"],
        bg=COLORS["surface"],
        justify="center",
        wraplength=wraplength,
        font=("Inter", body_size),
    ).pack(anchor="center")

    return content


def load_logo_label(parent: tk.Widget, max_width: int, max_height: int) -> tk.Label | None:
    logo_path = _asset_path("logo.png")
    if not logo_path.exists():
        return None

    try:
        image = tk.PhotoImage(file=str(logo_path))
    except tk.TclError:
        return None

    width = max(image.width(), 1)
    height = max(image.height(), 1)
    width_scale = max(1, (width + max_width - 1) // max_width)
    height_scale = max(1, (height + max_height - 1) // max_height)
    scale = max(width_scale, height_scale)
    if scale > 1:
        image = image.subsample(scale, scale)

    label = tk.Label(parent, image=image, bg=COLORS["surface"])
    label.image = image
    return label


def primary_button(parent: tk.Widget, text: str, command) -> tk.Button:
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=COLORS["primary"],
        fg="#03111B",
        activebackground=COLORS["primary_2"],
        activeforeground=COLORS["text"],
        relief="flat",
        bd=0,
        padx=22,
        pady=12,
        font=("Inter", 12, "bold"),
        cursor="hand2",
    )


def secondary_button(parent: tk.Widget, text: str, command) -> tk.Button:
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=COLORS["surface_2"],
        fg=COLORS["text"],
        activebackground=COLORS["surface"],
        activeforeground=COLORS["text"],
        relief="flat",
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        bd=0,
        padx=20,
        pady=12,
        font=("Inter", 12, "bold"),
        cursor="hand2",
    )


def branded_action_dialog(
    title: str,
    kicker: str,
    heading: str,
    body: str,
    actions: list[tuple[str, str]],
    primary: str | None = None,
    auto_close_ms: int = 0,
) -> str:
    root = tk.Tk()
    apply_window_style(root, title)
    panel = build_shell(root, kicker, heading, body)

    result = {"value": primary or (actions[0][0] if actions else "")}
    button_row = tk.Frame(panel, bg=COLORS["surface"])
    button_row.pack(side="bottom", anchor="center", pady=(24, 0))

    def choose(value: str) -> None:
        result["value"] = value
        root.destroy()

    buttons: list[tk.Button] = []
    for value, label in actions:
        factory = primary_button if value == primary else secondary_button
        button = factory(button_row, label, lambda selected=value: choose(selected))
        button.pack(side="left", padx=8)
        buttons.append(button)

    if buttons:
        buttons[0].focus_set()

    root.bind("<Escape>", lambda _event: choose("dismiss"))
    root.bind("<Return>", lambda _event: root.focus_get().invoke() if isinstance(root.focus_get(), tk.Button) else None)
    if auto_close_ms > 0:
        root.after(auto_close_ms, lambda: choose("timeout"))

    root.mainloop()
    return result["value"]


def branded_info_dialog(
    title: str,
    kicker: str,
    heading: str,
    body: str,
    auto_close_ms: int = 0,
) -> None:
    branded_action_dialog(
        title=title,
        kicker=kicker,
        heading=heading,
        body=body,
        actions=[("ok", "OK")],
        primary="ok",
        auto_close_ms=auto_close_ms,
    )