from app.routes import chat


def test_chat_prompt_allows_reviewable_drafts(monkeypatch):
    monkeypatch.setattr(chat, "refined_course", lambda refined_id: {"course_title": "Algorithms"})

    prompt = chat.chat_system_prompt({"refined_id": 7})

    assert "create_course_draft" in prompt
    assert "create_document_draft" in prompt
    assert "active_session_id" in prompt
    assert "active_refined_id" in prompt
    assert "review the diff" in prompt
    assert "explain the exact fields" not in prompt
    assert "cannot edit" not in prompt
