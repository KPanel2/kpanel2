from app import main as main_module


def test_ensure_room_columns_noop_when_slug_present(monkeypatch):
    class FakeInspector:
        def get_columns(self, _table):
            return [{"name": "id"}, {"name": "slug"}]

    monkeypatch.setattr(main_module, "inspect", lambda _engine: FakeInspector())
    main_module._ensure_room_columns()


def test_ensure_room_columns_skips_missing_table(monkeypatch):
    class FakeInspector:
        def get_columns(self, _table):
            raise RuntimeError("no such table")

    monkeypatch.setattr(main_module, "inspect", lambda _engine: FakeInspector())
    main_module._ensure_room_columns()


def test_ensure_room_columns_adds_slug(monkeypatch):
    class FakeInspector:
        def get_columns(self, _table):
            return [{"name": "id"}, {"name": "name"}]

    executed: list[str] = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement):
            executed.append(str(statement))

    class FakeEngine:
        def begin(self):
            return FakeConnection()

    monkeypatch.setattr(main_module, "inspect", lambda _engine: FakeInspector())
    monkeypatch.setattr(main_module, "engine", FakeEngine())
    main_module._ensure_room_columns()

    assert len(executed) == 1
    assert "slug" in executed[0]
