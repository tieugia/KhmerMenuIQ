import pytest
from pydantic import ValidationError

from app import guardrails as g
from app.models import ChatRequest


def test_chat_request_rejects_blank_message():
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_chat_request_rejects_empty_message():
    with pytest.raises(ValidationError):
        ChatRequest(message="")


def test_chat_request_rejects_too_long_message():
    with pytest.raises(ValidationError):
        ChatRequest(message="a" * (g.MESSAGE_MAX_LENGTH + 1))


def test_chat_request_accepts_message_at_max_length():
    req = ChatRequest(message="a" * g.MESSAGE_MAX_LENGTH)
    assert len(req.message) == g.MESSAGE_MAX_LENGTH


def test_chat_request_strips_surrounding_whitespace():
    req = ChatRequest(message="  I want chicken  ")
    assert req.message == "I want chicken"
