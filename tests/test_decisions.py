import pydantic
import pytest

from human_o_matic.decisions import DecisionOption, DecisionRequest, DecisionRequired


def test_a_decision_request_is_compact_json() -> None:
    request = DecisionRequest(
        kind="drum_track",
        message="Which track holds the drums?",
        answer_with=("track",),
        options=(DecisionOption(value=1, label="Track 1", details={"note_count": 4}),),
    )

    assert request.model_dump(mode="json") == {
        "kind": "drum_track",
        "message": "Which track holds the drums?",
        "answer_with": ["track"],
        "options": [{"value": 1, "label": "Track 1", "details": {"note_count": 4}}],
        "details": {},
    }
    assert DecisionRequest.model_validate_json(request.model_dump_json()) == request


def test_a_decision_request_is_frozen_and_strict() -> None:
    request = DecisionRequest(kind="tempo", message="What is the tempo?")

    with pytest.raises(pydantic.ValidationError):
        request.message = "changed"
    with pytest.raises(pydantic.ValidationError):
        DecisionRequest.model_validate({"kind": "colour", "message": "?"})
    with pytest.raises(pydantic.ValidationError):
        DecisionRequest.model_validate({"kind": "tempo", "message": "?", "extra": 1})


def test_decision_required_carries_its_request() -> None:
    request = DecisionRequest(kind="tempo", message="What is the tempo?", answer_with=("bpm",))

    error = DecisionRequired(request)

    assert error.request is request
    assert str(error) == "What is the tempo?"
