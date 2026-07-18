from unittest.mock import MagicMock, patch


def test_preload_pdfs_generates_for_each_year():
    from app.routes.preview import preload_pdfs

    calls = []

    def fake_generate(cy):
        calls.append(cy)
        return b"fake-pdf-bytes"

    with patch("app.routes.preview.os.getenv", return_value="2025-2026,2026-2027"), \
         patch("app.routes.preview._generate_pdf", side_effect=fake_generate), \
         patch("app.routes.preview.cache") as mock_cache, \
         patch("app.routes.preview.threading.Thread") as mock_thread_cls:
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        preload_pdfs()

        mock_thread_cls.assert_called_once()
        assert mock_thread_cls.call_args.kwargs.get("daemon") is True
        assert mock_thread.start.called

        worker = mock_thread_cls.call_args.kwargs["target"]
        worker()

    assert calls == ["2025-2026", "2026-2027"]
    mock_cache.put.assert_any_call("full_pdf:2025-2026", b"fake-pdf-bytes", ttl=3600)
    mock_cache.put.assert_any_call("full_pdf:2026-2027", b"fake-pdf-bytes", ttl=3600)


def test_preload_pdfs_skips_when_no_years():
    from app.routes.preview import preload_pdfs

    with patch("app.routes.preview.os.getenv", return_value=""), \
         patch("app.routes.preview.threading.Thread") as mock_thread_cls:
        preload_pdfs()
        mock_thread_cls.assert_not_called()


def test_preload_pdfs_handles_generation_failure():
    from app.routes.preview import preload_pdfs

    def fail_generate(cy):
        return None

    with patch("app.routes.preview.os.getenv", return_value="2025-2026"), \
         patch("app.routes.preview._generate_pdf", side_effect=fail_generate), \
         patch("app.routes.preview.cache") as mock_cache, \
         patch("app.routes.preview.threading.Thread") as mock_thread_cls:
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        preload_pdfs()

        worker = mock_thread_cls.call_args.kwargs["target"]
        worker()

    mock_cache.put.assert_not_called()


def test_generate_pdf_returns_none_on_failure():
    from app.routes.preview import _generate_pdf

    with patch("app.routes.preview.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.in_.return_value.eq.return_value.execute.side_effect = RuntimeError("DB down")
        result = _generate_pdf("2025-2026")

    assert result is None


def test_pdf_response_sets_correct_headers():
    from app.routes.preview import pdf_response

    response = pdf_response(b"pdf-data", "test.pdf", download=False)
    assert response.headers["Content-Type"] == "application/pdf"
    assert 'inline; filename="test.pdf"' in response.headers["Content-Disposition"]
    assert "s-maxage=300" in response.headers["Cache-Control"]


def test_pdf_response_download_disposition():
    from app.routes.preview import pdf_response

    response = pdf_response(b"pdf-data", "test.pdf", download=True)
    assert 'attachment; filename="test.pdf"' in response.headers["Content-Disposition"]


def test_preload_thread_name():
    from app.routes.preview import preload_pdfs

    with patch("app.routes.preview.os.getenv", return_value="2025-2026"), \
         patch("app.routes.preview._generate_pdf", return_value=b"pdf"), \
         patch("app.routes.preview.cache"), \
         patch("app.routes.preview.threading.Thread") as mock_thread_cls:
        mock_thread_cls.return_value = MagicMock()
        preload_pdfs()
        assert mock_thread_cls.call_args.kwargs.get("name") == "pdf-preload"
