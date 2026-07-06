import sys
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import MagicMock

# Headless CI/dev machines may not have Tk installed; several modules import tkinter at load.
_tcl_error = type("TclError", (Exception,), {})
_tk_module = MagicMock()
_tk_module.TclError = _tcl_error
_tk_module.Event = object
sys.modules.setdefault("_tkinter", MagicMock())
sys.modules.setdefault("tkinter", _tk_module)

from kpanel_client.api import BootstrapResult, ResolveResult  # noqa: E402


@dataclass
class FakeApi:
    """Test double for KPanelApiClient."""

    reachable: bool = True
    bootstrap: BootstrapResult = field(
        default_factory=lambda: BootstrapResult(
            ok=True,
            registration_code="KPANEL-TEST01",
            device_token="device-token",
        )
    )
    bootstrap_results: list[BootstrapResult] | None = None
    resolve: ResolveResult = field(
        default_factory=lambda: ResolveResult(
            status="configured",
            configured_url="https://dashboard.example.com",
        )
    )
    device_token: str = ""
    ack_results: list[bool] | None = None
    ack_calls: list[tuple[str, str, str, str]] = field(default_factory=list)
    report_calls: list[dict] = field(default_factory=list)
    _bootstrap_calls: int = 0

    def set_device_token(self, device_token: str) -> None:
        self.device_token = device_token

    def is_reachable(self) -> bool:
        return self.reachable

    def bootstrap_device(self, device_id: str, registration_code: str) -> BootstrapResult:
        if self.bootstrap_results is not None:
            index = min(self._bootstrap_calls, len(self.bootstrap_results) - 1)
            self._bootstrap_calls += 1
            return self.bootstrap_results[index]
        return self.bootstrap

    def resolve_registration(
        self,
        device_id: str,
        registration_code: str,
        client_version: str | None = None,
    ) -> ResolveResult:
        return self.resolve

    def get_device_config(self, device_id: str) -> ResolveResult:
        return self.resolve

    def ack_device_action(
        self,
        device_id: str,
        registration_code: str,
        action: str,
        status: str,
    ) -> bool:
        self.ack_calls.append((device_id, registration_code, action, status))
        if self.ack_results is not None:
            return self.ack_results.pop(0)
        return True

    def report_update_event(self, device_id: str, registration_code: str, **kwargs) -> bool:
        self.report_calls.append(
            {
                "device_id": device_id,
                "registration_code": registration_code,
                **kwargs,
            }
        )
        return True


def make_subprocess_result(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def make_requests_response(
    status_code: int = 200,
    json_data: dict | None = None,
    *,
    raise_json: bool = False,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if raise_json:
        response.json.side_effect = ValueError("bad json")
    else:
        response.json.return_value = json_data or {}
    return response


class FakeTkWidget:
    def __init__(self, *args, **kwargs):
        self.children = []
        self._options = {}
        self.image = None
        self.menu = MagicMock(config=MagicMock())

    def pack(self, **kwargs):
        return None

    def pack_forget(self):
        return None

    def bind(self, *args, **kwargs):
        return None

    def bind_all(self, *args, **kwargs):
        return None

    def config(self, **kwargs):
        self._options.update(kwargs)

    def configure(self, **kwargs):
        self.config(**kwargs)

    def focus_set(self):
        return None

    def focus_force(self):
        return None

    def focus_get(self):
        return None

    def destroy(self):
        return None

    def update_idletasks(self):
        return None

    def winfo_screenwidth(self):
        return 1366

    def winfo_screenheight(self):
        return 768

    def winfo_width(self):
        return 1200

    def protocol(self, *args, **kwargs):
        return None

    def after(self, _ms, callback):
        callback()
        return None

    def mainloop(self):
        return None

    def title(self, _value):
        return None

    def attributes(self, *_args, **_kwargs):
        return None

    def overrideredirect(self, *_args, **_kwargs):
        return None

    def geometry(self, *_args, **_kwargs):
        return None

    def minsize(self, *_args, **_kwargs):
        return None

    def set(self, *_args, **_kwargs):
        return None

    def yview(self, *_args, **_kwargs):
        return None

    def yview_scroll(self, *_args, **_kwargs):
        return None

    def create_window(self, *_args, **_kwargs):
        return 1

    def bbox(self, *_args, **_kwargs):
        return (0, 0, 100, 100)

    def itemconfigure(self, *_args, **_kwargs):
        return None

    def invoke(self):
        return None

    def __getitem__(self, key):
        if key == "menu":
            return self.menu
        return MagicMock()


class FakeStringVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


def install_fake_tk_module(monkeypatch, module_name: str):
    fake = MagicMock()
    fake.Tk = FakeTkWidget
    fake.Toplevel = FakeTkWidget
    fake.Frame = FakeTkWidget
    fake.Label = FakeTkWidget
    fake.Button = FakeTkWidget
    fake.Canvas = FakeTkWidget
    fake.Scrollbar = FakeTkWidget
    fake.Entry = FakeTkWidget
    fake.OptionMenu = lambda parent, var, *values: FakeTkWidget()
    fake.StringVar = FakeStringVar
    fake.TclError = _tcl_error
    fake.Event = object
    fake.PhotoImage = MagicMock
    monkeypatch.setitem(sys.modules, "tkinter", fake)
    monkeypatch.setattr(f"{module_name}.tk", fake, raising=False)
    return fake
