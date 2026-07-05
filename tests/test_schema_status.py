from postgrest.exceptions import APIError

from app.services import schema


class Query:
    def __init__(self, table, missing):
        self.table = table
        self.missing = missing

    def select(self, *_):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        if self.table in self.missing:
            raise APIError({"message": f"Could not find the table 'public.{self.table}' in the schema cache"})
        return type("Result", (), {"data": []})()


class Supabase:
    def __init__(self, missing=()):
        self.missing = set(missing)

    def table(self, name):
        return Query(name, self.missing)


def test_schema_status_is_ok_when_tables_exist(monkeypatch):
    monkeypatch.setattr(schema, "supabase", Supabase())

    assert schema.schema_status()["ok"] is True


def test_schema_status_lists_missing_tables(monkeypatch):
    monkeypatch.setattr(schema, "supabase", Supabase({"agent_drafts"}))

    status = schema.schema_status()

    assert status["ok"] is False
    assert status["missing_tables"] == ["agent_drafts"]
