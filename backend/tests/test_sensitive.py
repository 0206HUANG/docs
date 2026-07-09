import pytest

from app.services.pipeline.sensitive import check_sensitive_words


def test_no_match():
    assert check_sensitive_words("Hello world", ["lawsuit", "transfer"]) == []


def test_single_match():
    matched = check_sensitive_words("Please transfer funds immediately", ["transfer", "lawsuit"])
    assert "transfer" in matched


def test_multiple_matches():
    matched = check_sensitive_words("lawsuit and compensation demanded", ["lawsuit", "compensation", "transfer"])
    assert "lawsuit" in matched
    assert "compensation" in matched
    assert "transfer" not in matched


def test_case_insensitive():
    matched = check_sensitive_words("LAWSUIT filed", ["lawsuit"])
    assert "lawsuit" in matched


def test_empty_text():
    assert check_sensitive_words("", ["lawsuit"]) == []


def test_empty_words():
    assert check_sensitive_words("some text", []) == []


def test_chinese_sensitive_word():
    matched = check_sensitive_words("需要赔偿损失", ["赔偿", "转账"])
    assert "赔偿" in matched


def test_no_false_positive():
    # partial word should still match (substring search)
    matched = check_sensitive_words("compensation claim", ["compensation"])
    assert "compensation" in matched
