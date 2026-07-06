from unittest.mock import MagicMock, patch

import pytest

from kpanel_client import brand_ui
from tests.conftest import FakeTkWidget, install_fake_tk_module


class FakeWidget:
    def __init__(self, **attrs):
        self.attrs = attrs
        self.image = None


class FakeRoot:
    def __init__(self, screen_width=1024, screen_height=600):
        self._screen_width = screen_width
        self._screen_height = screen_height

    def winfo_screenwidth(self):
        return self._screen_width

    def winfo_screenheight(self):
        return self._screen_height


class FakeImage:
    def __init__(self, width=400, height=200):
        self._width = width
        self._height = height
        self.subsample_calls = []

    def width(self):
        return self._width

    def height(self):
        return self._height

    def subsample(self, x, y):
        self.subsample_calls.append((x, y))
        return self


@pytest.mark.parametrize(
    ("screen_width", "expected"),
    [
        (1920, (13, 34, 16)),
        (1366, (12, 30, 14)),
        (800, (11, 24, 13)),
    ],
)
def test_font_sizes_for_screen_width(screen_width, expected):
    root = FakeRoot(screen_width=screen_width)
    assert brand_ui._font_sizes(root) == expected


def test_apply_window_style_configures_root(monkeypatch):
    install_fake_tk_module(monkeypatch, "kpanel_client.brand_ui")
    root = FakeTkWidget()
    brand_ui.apply_window_style(root, "KPanel Test", geometry="800x480")
    assert root is not None


@patch.object(brand_ui, "load_logo_label", return_value=None)
def test_build_shell_without_logo(load_logo):
    root = FakeRoot(screen_width=1366)
    panel = brand_ui.build_shell(root, "Kicker", "Heading", "Body copy")
    assert panel is not None
    load_logo.assert_called_once()


@patch.object(brand_ui.tk, "PhotoImage")
@patch.object(brand_ui.tk, "Label", side_effect=lambda parent, **kwargs: FakeWidget(**kwargs))
def test_load_logo_label_returns_none_when_asset_missing(label, photo, tmp_path, monkeypatch):
    monkeypatch.setattr(brand_ui, "_asset_path", lambda filename: tmp_path / filename)
    assert brand_ui.load_logo_label(FakeWidget(), max_width=100, max_height=50) is None
    photo.assert_not_called()


@patch.object(brand_ui.tk, "PhotoImage")
@patch.object(brand_ui.tk, "Label", side_effect=lambda parent, **kwargs: FakeWidget(**kwargs))
def test_load_logo_label_scales_large_image(label, photo, tmp_path, monkeypatch):
    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(b"png")
    monkeypatch.setattr(brand_ui, "_asset_path", lambda filename: logo_path)

    image = FakeImage(width=800, height=400)
    photo.return_value = image

    widget = brand_ui.load_logo_label(FakeWidget(), max_width=100, max_height=50)

    assert widget is not None
    assert image.subsample_calls == [(8, 8)]


@patch.object(brand_ui.tk, "PhotoImage", side_effect=brand_ui.tk.TclError("bad image"))
@patch.object(brand_ui.tk, "Label")
def test_load_logo_label_returns_none_on_tcl_error(label, photo, tmp_path, monkeypatch):
    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(b"png")
    monkeypatch.setattr(brand_ui, "_asset_path", lambda filename: logo_path)

    assert brand_ui.load_logo_label(FakeWidget(), max_width=100, max_height=50) is None


def test_primary_and_secondary_buttons(monkeypatch):
    install_fake_tk_module(monkeypatch, "kpanel_client.brand_ui")
    parent = FakeTkWidget()
    clicked = []

    primary = brand_ui.primary_button(parent, "Go", lambda: clicked.append("go"))
    secondary = brand_ui.secondary_button(parent, "Back", lambda: clicked.append("back"))

    assert primary is not None
    assert secondary is not None


def test_branded_action_dialog_returns_choice(monkeypatch):
    install_fake_tk_module(monkeypatch, "kpanel_client.brand_ui")
    monkeypatch.setattr(brand_ui, "load_logo_label", lambda *args, **kwargs: None)
    result = brand_ui.branded_action_dialog(
        title="Test",
        kicker="Kicker",
        heading="Heading",
        body="Body",
        actions=[("ok", "OK"), ("cancel", "Cancel")],
        primary="ok",
    )
    assert result == "ok"


def test_branded_info_dialog_delegates_to_action_dialog(monkeypatch):
    install_fake_tk_module(monkeypatch, "kpanel_client.brand_ui")
    with patch.object(brand_ui, "branded_action_dialog", return_value="ok") as dialog:
        brand_ui.branded_info_dialog("Title", "Kicker", "Heading", "Body", auto_close_ms=1000)
    dialog.assert_called_once()
