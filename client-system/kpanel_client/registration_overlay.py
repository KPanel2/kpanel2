import argparse
import tkinter as tk

from kpanel_client.brand_ui import COLORS, apply_window_style, load_logo_label


def main() -> None:
    parser = argparse.ArgumentParser(description="Show persistent registration overlay")
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--registration-code", required=True)
    parser.add_argument("--api-base-url", required=True)
    args = parser.parse_args()

    root = tk.Tk()
    apply_window_style(root, "KPanel Registration Required")
    root.overrideredirect(False)
    root.attributes("-fullscreen", True)
    root.update_idletasks()

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()

    # Responsive sizing: everything derived from actual screen dimensions.
    outer_padx = max(20, sw // 32)
    outer_pady = max(16, sh // 28)
    card_padx = max(12, sw // 64)
    logo_w = int(sw * 0.18)
    logo_h = int(sh * 0.14)
    wrap = max(300, sw - outer_padx * 2 - card_padx * 2 - 40)
    kicker_size = max(10, sw // 96)
    heading_size = max(16, sw // 48)
    body_size = max(11, sw // 80)
    label_size = max(10, sw // 100)
    value_size = max(14, sw // 60)

    outer = tk.Frame(root, bg=COLORS["surface"])
    outer.pack(fill="both", expand=True, padx=outer_padx, pady=outer_pady)

    canvas = tk.Canvas(outer, bg=COLORS["surface"], highlightthickness=0, bd=0)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")
    canvas.configure(yscrollcommand=scrollbar.set)

    content = tk.Frame(canvas, bg=COLORS["surface"])
    content_window = canvas.create_window((0, 0), window=content, anchor="nw")

    def _sync_scroll_region(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfigure(content_window, width=canvas.winfo_width())

    content.bind("<Configure>", _sync_scroll_region)
    canvas.bind("<Configure>", _sync_scroll_region)

    def _on_mousewheel(event: tk.Event) -> None:
        delta = getattr(event, "delta", 0)
        if delta:
            canvas.yview_scroll(int(-1 * (delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    canvas.bind_all("<Button-4>", lambda _event: canvas.yview_scroll(-1, "units"))
    canvas.bind_all("<Button-5>", lambda _event: canvas.yview_scroll(1, "units"))

    logo = load_logo_label(content, max_width=logo_w, max_height=logo_h)
    if logo is not None:
        logo.pack(anchor="center", pady=(0, max(8, sh // 40)))

    tk.Label(
        content,
        text="Activation Required",
        fg=COLORS["accent"],
        bg=COLORS["surface"],
        font=("Inter", kicker_size, "bold"),
    ).pack(anchor="center")
    tk.Label(
        content,
        text="This panel still needs a mapped URL.",
        fg=COLORS["text"],
        bg=COLORS["surface"],
        font=("Space Grotesk", heading_size, "bold"),
        wraplength=wrap,
        justify="center",
    ).pack(anchor="center", pady=(6, 8))
    tk.Label(
        content,
        text="Open the KPanel portal and claim this registration code. Once mapped, the panel will continue automatically.",
        fg=COLORS["muted"],
        bg=COLORS["surface"],
        font=("Inter", body_size),
        wraplength=wrap,
        justify="center",
    ).pack(anchor="center", pady=(0, max(10, sh // 48)))

    cards = tk.Frame(content, bg=COLORS["surface"])
    cards.pack(fill="x", pady=(0, 10))

    def make_card(parent: tk.Widget, label: str, value: str) -> tk.Frame:
        card = tk.Frame(
            parent,
            bg=COLORS["surface_2"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            padx=card_padx,
            pady=max(8, sh // 60),
        )
        tk.Label(
            card,
            text=label,
            fg=COLORS["accent"],
            bg=COLORS["surface_2"],
            font=("Inter", label_size, "bold"),
        ).pack(anchor="w")
        tk.Label(
            card,
            text=value,
            fg=COLORS["text"],
            bg=COLORS["surface_2"],
            font=("Space Grotesk", value_size, "bold"),
            wraplength=wrap - card_padx * 2,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))
        return card

    make_card(cards, "Device ID", args.device_id).pack(fill="x", pady=(0, 10))
    make_card(cards, "Registration Code", args.registration_code).pack(fill="x", pady=(0, 10))
    make_card(cards, "API Base", args.api_base_url).pack(fill="x")

    root.bind("<Escape>", lambda _event: root.destroy())
    root.mainloop()


if __name__ == "__main__":
    main()
