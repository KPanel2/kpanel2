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
    root.configure(bg=COLORS["bg"])
    root.geometry(geometry)
    root.minsize(900, 560)


def build_shell(root: tk.Tk | tk.Toplevel, kicker: str, heading: str, body: str) -> tk.Frame:
    outer = tk.Frame(root, bg=COLORS["bg"], padx=28, pady=24)
    outer.pack(fill="both", expand=True)

    panel = tk.Frame(
        outer,
        bg=COLORS["surface"],
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        padx=28,
        pady=26,
    )
    panel.pack(fill="both", expand=True)

    header = tk.Frame(panel, bg=COLORS["surface"])
    header.pack(fill="x", pady=(0, 20))

    logo = load_logo_label(header)
    if logo is not None:
        logo.pack(side="left", padx=(0, 18))

    copy = tk.Frame(header, bg=COLORS["surface"])
    copy.pack(side="left", fill="x", expand=True)

    tk.Label(
        copy,
        text=kicker,
        fg=COLORS["accent"],
        bg=COLORS["surface"],
        font=("Inter", 11, "bold"),
    ).pack(anchor="w")
    tk.Label(
        copy,
        text=heading,
        fg=COLORS["text"],
        bg=COLORS["surface"],
        font=("Space Grotesk", 26, "bold"),
    ).pack(anchor="w", pady=(6, 8))
    tk.Label(
        copy,
        text=body,
        fg=COLORS["muted"],
        bg=COLORS["surface"],
        justify="left",
        wraplength=720,
        font=("Inter", 13),
    ).pack(anchor="w")

    return panel


def load_logo_label(parent: tk.Widget) -> tk.Label | None:
    logo_path = _asset_path("logo.png")
    if not logo_path.exists():
        return None

    try:
        image = tk.PhotoImage(file=str(logo_path))
    except tk.TclError:
        return None

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


def branded_info_dialog(title: str, kicker: str, heading: str, body: str) -> None:
    root = tk.Tk()
    apply_window_style(root, title)
    panel = build_shell(root, kicker, heading, body)

    button_row = tk.Frame(panel, bg=COLORS["surface"])
    button_row.pack(side="bottom", anchor="e", pady=(20, 0))
    primary_button(button_row, "OK", root.destroy).pack(side="right")

    root.mainloop()