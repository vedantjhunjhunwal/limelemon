import json
import os
import sys
from types import SimpleNamespace

import anthropic
try:  # anthropic>=2 uses httpx2, older releases use httpx
    import httpx2 as httpx
except ImportError:
    import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["OFFLINE_MODE"] = "1"

from game import fallback  # noqa: E402
from game.ai import StoryAI  # noqa: E402
from game.engine import Game, GameError, GameStore  # noqa: E402


def reply(text, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    """Stands in for anthropic.Anthropic; returns canned responses in order."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def ai_with(responses):
    ai = StoryAI()
    ai.client = FakeClient(responses)
    return ai


def offline_store():
    return GameStore(StoryAI())


def test_offline_full_game_reaches_outcome():
    game = offline_store().new_game("a haunted lighthouse", "normal")
    assert not game.ai_generated and game.notices
    game.investigate(0)
    game.interrogate(1, "Where were you last night?")
    game.hint()
    culprit = next(i for i, s in enumerate(game.case["suspects"]) if s["is_culprit"])
    result = game.accuse(culprit, "They " + game.case["method"] + " because " + game.case["motive"])
    assert result["correct"] and game.over and result["score"] > 500


def test_wrong_accusation_loses():
    game = offline_store().new_game("", "easy")
    innocent = next(i for i, s in enumerate(game.case["suspects"]) if not s["is_culprit"])
    assert not game.accuse(innocent, "I just have a feeling about them.")["correct"]


@pytest.mark.parametrize("action", [
    lambda g: g.investigate(99),
    lambda g: g.investigate("abc"),
    lambda g: g.interrogate(0, "   "),
    lambda g: g.interrogate(0, "x" * 400),
    lambda g: g.accuse(0, "short"),
])
def test_invalid_input_rejected_without_using_turn(action):
    game = offline_store().new_game("", "normal")
    turns = game.turns_left
    with pytest.raises(GameError):
        action(game)
    assert game.turns_left == turns


def test_cannot_search_twice_or_act_after_turns_run_out():
    game = offline_store().new_game("", "hard")
    game.investigate(0)
    with pytest.raises(GameError):
        game.investigate(0)
    game.turns_left = 0
    with pytest.raises(GameError):
        game.hint()


def test_ai_generated_case_and_dialogue_are_used():
    case = fallback.generate_case("space station", "normal")
    ai = ai_with([reply(json.dumps(case)), reply("\"I was in the observatory,\" she says.")])
    game = Game(ai, "space station", "normal")
    assert game.ai_generated
    entry = game.interrogate(0, "Where were you?")
    assert entry["ai"] and "observatory" in entry["text"]
    # the structured-output schema was requested for the case
    assert ai.client.calls[0]["output_config"]["format"]["type"] == "json_schema"


def test_api_errors_fall_back_to_offline_content():
    conn_err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    ai = ai_with([conn_err, reply("", stop="refusal")])
    game = Game(ai, "", "normal")
    assert not game.ai_generated and "reach the AI" in game.notices[0]
    entry = game.investigate(0)
    assert not entry["ai"] and entry["text"]


def test_unplayable_or_malformed_ai_case_falls_back():
    bad = fallback.generate_case("", "normal")
    for s in bad["suspects"]:
        s["is_culprit"] = True
    for r in (reply(json.dumps(bad)), reply("not json {")):
        game = Game(ai_with([r]), "", "normal")
        assert not game.ai_generated


def test_public_state_hides_solution():
    game = offline_store().new_game("", "normal")
    state = json.dumps(game.public_state())
    assert "is_culprit" not in state and game.case["solution"] not in state


def test_http_api_flow():
    import app as web
    web.store = offline_store()
    client = web.app.test_client()
    r = client.post("/api/new", json={"theme": "a jazz club", "difficulty": "normal"})
    gid = r.get_json()["id"]
    assert client.post(f"/api/{gid}/investigate", json={"location_id": 0}).status_code == 200
    bad = client.post(f"/api/{gid}/interrogate", json={"suspect_id": 0, "question": ""})
    assert bad.status_code == 400 and "error" in bad.get_json()
    assert client.post("/api/new", data="nope").status_code == 400
    assert client.post("/api/missing/hint", json={}).status_code == 400
