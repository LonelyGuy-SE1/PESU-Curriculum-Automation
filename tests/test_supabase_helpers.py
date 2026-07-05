from app.supabase import first_row


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.limit_value = None

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        return type("Result", (), {"data": self.rows})()


def test_first_row_limits_and_returns_first_item():
    query = Query([{"id": 1}, {"id": 2}])

    assert first_row(query) == {"id": 1}
    assert query.limit_value == 1


def test_first_row_returns_none_for_empty_result():
    assert first_row(Query([])) is None
