from unittest.mock import patch

import pytest


def test_invalidate_curriculum_cache_clears_all_prefixes():
    import app.cache as cache_module
    from app.services.curriculum import invalidate_curriculum_cache

    invalidated = []
    original_invalidate = cache_module.invalidate

    def spy(prefix=""):
        invalidated.append(prefix)
        return original_invalidate(prefix)

    with patch.object(cache_module, "invalidate", side_effect=spy):
        invalidate_curriculum_cache()

    assert "full_pdf:" in invalidated
    assert "full_html:" in invalidated
    assert "sem_pdf:" in invalidated
    assert "course:" in invalidated
    assert len(invalidated) == 4


def test_invalidate_curriculum_cache_is_idempotent():
    from app.services.curriculum import invalidate_curriculum_cache

    invalidate_curriculum_cache()
    invalidate_curriculum_cache()
    invalidate_curriculum_cache()


def test_refined_course_caches_result():
    import app.cache as cache_module
    from app.services.curriculum import refined_course

    fake_row = {
        "id": 999,
        "course_title": "Cached Course",
        "semester": 3,
        "course_code": "UE25CS999A",
        "submission_id": 1,
    }

    with patch("app.services.curriculum.first_row", return_value=fake_row), \
         patch("app.services.curriculum.attach_submissions", side_effect=lambda rows: [{**rows[0], "_submission": {}}]), \
         patch("app.services.curriculum.build_course_preview", return_value={"id": 999, "title": "Cached Course"}) as mock_build, \
         patch.object(cache_module, "get", return_value=None), \
         patch.object(cache_module, "put"):
        result = refined_course(999)

    assert result == {"id": 999, "title": "Cached Course"}
    mock_build.assert_called_once()


def test_refined_course_returns_cached_on_hit():
    import app.cache as cache_module
    from app.services.curriculum import refined_course

    cached_data = {"id": 888, "title": "Already Cached"}

    with patch.object(cache_module, "get", return_value=cached_data):
        result = refined_course(888)

    assert result == cached_data


def test_refined_course_raises_on_missing():
    from app.services.curriculum import refined_course

    with patch("app.services.curriculum.first_row", return_value=None):
        with pytest.raises(LookupError, match="not found"):
            refined_course(12345)


def test_attach_submissions_caches_submission_data():
    import app.cache as cache_module
    from app.services.curriculum import attach_submissions

    rows = [{"id": 1, "submission_id": 10}, {"id": 2, "submission_id": 20}]

    with patch.object(cache_module, "get", return_value=None), \
         patch.object(cache_module, "put") as mock_put, \
         patch("app.services.curriculum.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"id": 10, "credit_category": "5"},
            {"id": 20, "credit_category": "4"},
        ]
        result = attach_submissions(rows)

    assert result[0]["_submission"]["credit_category"] == "5"
    assert result[1]["_submission"]["credit_category"] == "4"
    mock_put.assert_called_once()


def test_attach_submissions_skips_when_no_submission_ids():
    from app.services.curriculum import attach_submissions

    rows = [{"id": 1, "submission_id": None}, {"id": 2}]
    result = attach_submissions(rows)
    assert all(row.get("_submission") is None for row in result)
