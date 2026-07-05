import argparse
import tkinter as tk

from kpanel_client.brand_ui import COLORS, apply_window_style, load_logo_label


def main() -> None:
    parser = argparse.ArgumentParser(description="Show persistent service-offline overlay")
    parser.add_argument("--url", required=True)
    args = parser.parse_args()

    root = tk.Tk()
    apply_window_style(root, "KPanel Offline")
    root.update_idletasks()

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    wrap = max(300, sw - max(32, sw // 18) * 2 - 80)
    kicker_size = max(10, sw // 96)
    heading_size = max(16, sw // 48)
    body_size = max(11, sw // 80)

    outer = tk.Frame(root, bg=COLORS["surface"])
    outer.pack(fill="both", expand=True, padx=max(32, sw // 18), pady=max(28, sh // 18))

    logo = load_logo_label(outer, max_width=int(sw * 0.18), max_height=int(sh * 0.14))
    if logo is not None:
        logo.pack(anchor="center", pady=(0, 24))

    tk.Label(
        outer,
        text="Offline",
        fg=COLORS["accent"],
        bg=COLORS["surface"],
        font=("Inter", kicker_size, "bold"),
    ).pack(anchor="center")
    tk.Label(
        outer,
        text="Configured service is unavailable.",
        fg=COLORS["text"],
        bg=COLORS["surface"],
        font=("Space Grotesk", heading_size, "bold"),
        wraplength=wrap,
        justify="center",
    ).pack(anchor="center", pady=(8, 12))
    tk.Label(
        outer,
        text=(
            f"Cannot reach:\n{args.url}\n\n"
            "The panel will keep retrying automatically."
        ),
        fg=COLORS["muted"],
        bg=COLORS["surface"],
        font=("Inter", body_size),
        wraplength=wrap,
        justify="center",
    ).pack(anchor="center")

    root.mainloop()


if __name__ == "__main__":
    main()
