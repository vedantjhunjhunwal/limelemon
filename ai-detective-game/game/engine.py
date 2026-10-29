"""Game rules and state. Calls the AI for content, falls back offline on failure."""
import uuid

from . import fallback
from .ai import AIUnavailable, StoryAI

MAX_TURNS = {"easy": 16, "normal": 12, "hard": 9}
MAX_QUESTION_LEN = 300
MAX_THEME_LEN = 120


class GameError(Exception):
    """Invalid player input or action; shown to the player, game state unchanged."""


def validate_case(case):
    """Check an AI-generated case is playable; raise AIUnavailable if not."""
    try:
        suspects, locations = case["suspects"], case["locations"]
        if len(suspects) < 3 or len(locations) < 3:
            raise ValueError("too few suspects/locations")
        if len({s["name"] for s in suspects}) != len(suspects):
            raise ValueError("duplicate suspect names")
        if sum(1 for s in suspects if s["is_culprit"]) != 1:
            raise ValueError("must have exactly one culprit")
        culprit = next(s["name"] for s in suspects if s["is_culprit"])
        if not any(l["points_to"] == culprit and not l["is_red_herring"] for l in locations):
            raise ValueError("no clue points to the culprit")
    except (KeyError, TypeError, ValueError) as e:
        raise AIUnavailable(f"AI generated an unplayable case ({e}) - using backup case.")
    return case


class Game:
    def __init__(self, ai, theme, difficulty):
        self.id = uuid.uuid4().hex
        self.ai = ai
        self.difficulty = difficulty
        self.turns_left = MAX_TURNS[difficulty]
        self.found = []          # location indexes searched, in order
        self.interviews = {}     # suspect index -> [{"q", "a"}]
        self.log = []
        self.over = False
        self.result = None
        self.notices = []
        self._seen_notices = set()
        try:
            self.case = validate_case(ai.generate_case(theme, difficulty))
            self.ai_generated = True
        except AIUnavailable as e:
            self._notify(e)
            self.case = fallback.generate_case(theme, difficulty)
            self.ai_generated = False

    # ---- helpers ----------------------------------------------------------
    def _notify(self, error):
        # show each distinct AI problem once per game, not on every action
        if str(error) not in self._seen_notices:
            self._seen_notices.add(str(error))
            self.notices.append(str(error))

    def _with_fallback(self, ai_fn, fallback_fn):
        try:
            return ai_fn(), True
        except AIUnavailable as e:
            self._notify(e)
            return fallback_fn(), False

    def _require_active(self):
        if self.over:
            raise GameError("This case is closed. Start a new game.")

    def _use_turn(self):
        if self.turns_left <= 0:
            raise GameError("You're out of time! You must make your accusation now.")
        self.turns_left -= 1

    def _index(self, value, items, label):
        try:
            i = int(value)
        except (TypeError, ValueError):
            raise GameError(f"Invalid {label}.")
        if not 0 <= i < len(items):
            raise GameError(f"No such {label}.")
        return i

    def found_clues(self):
        return [self.case["locations"][i]["clue"] for i in self.found]

    # ---- player actions ---------------------------------------------------
    def investigate(self, location_id):
        self._require_active()
        i = self._index(location_id, self.case["locations"], "location")
        if i in self.found:
            raise GameError("You've already searched there. Try somewhere else.")
        self._use_turn()
        loc = self.case["locations"][i]
        self.found.append(i)
        text, ai_used = self._with_fallback(
            lambda: self.ai.narrate_investigation(self.case, loc, len(self.found)),
            lambda: fallback.narrate_investigation(loc))
        entry = {"type": "investigate", "title": loc["name"], "text": text, "ai": ai_used}
        self.log.append(entry)
        return entry

    def interrogate(self, suspect_id, question):
        self._require_active()
        i = self._index(suspect_id, self.case["suspects"], "suspect")
        question = (question or "").strip()
        if not question:
            raise GameError("Type a question for the suspect.")
        if len(question) > MAX_QUESTION_LEN:
            raise GameError(f"Keep your question under {MAX_QUESTION_LEN} characters.")
        self._use_turn()
        suspect = self.case["suspects"][i]
        history = self.interviews.setdefault(i, [])
        answer, ai_used = self._with_fallback(
            lambda: self.ai.interrogate(self.case, suspect, history, question, self.found_clues()),
            lambda: fallback.interrogate(suspect, question, self.found_clues()))
        history.append({"q": question, "a": answer})
        entry = {"type": "interrogate", "title": suspect["name"], "question": question,
                 "text": answer, "ai": ai_used}
        self.log.append(entry)
        return entry

    def hint(self):
        self._require_active()
        self._use_turn()
        questioned = [self.case["suspects"][i]["name"] for i in self.interviews]
        text, ai_used = self._with_fallback(
            lambda: self.ai.hint(self.case, self.found_clues(), questioned),
            lambda: fallback.hint(self.case, len(self.found)))
        entry = {"type": "hint", "title": "Your assistant", "text": text, "ai": ai_used}
        self.log.append(entry)
        return entry

    def accuse(self, suspect_id, reasoning):
        self._require_active()
        i = self._index(suspect_id, self.case["suspects"], "suspect")
        reasoning = (reasoning or "").strip()
        if len(reasoning) < 10:
            raise GameError("Explain your reasoning (at least a sentence) before accusing.")
        if len(reasoning) > 1000:
            raise GameError("Please keep your reasoning under 1000 characters.")
        accused = self.case["suspects"][i]
        correct = accused["is_culprit"]
        verdict, ai_used = self._with_fallback(
            lambda: self.ai.judge_accusation(self.case, accused, reasoning, correct),
            lambda: fallback.judge_accusation(self.case, accused, reasoning, correct))
        reasoning_score = max(0, min(100, int(verdict.get("reasoning_score", 0))))
        score = (500 + self.turns_left * 20 if correct else 0) + reasoning_score * 3
        self.over = True
        self.result = {
            "correct": correct, "accused": accused["name"],
            "culprit": next(s["name"] for s in self.case["suspects"] if s["is_culprit"]),
            "solution": self.case["solution"], "feedback": verdict.get("feedback", ""),
            "epilogue": verdict.get("epilogue", ""), "reasoning_score": reasoning_score,
            "score": score, "ai": ai_used,
            "rank": ("Master Detective" if score >= 850 else "Inspector" if score >= 650
                     else "Rookie" if correct else "Case Unsolved"),
        }
        return self.result

    # ---- view for the browser (never leaks the solution mid-game) --------
    def public_state(self):
        c = self.case
        notices, self.notices = self.notices, []
        return {
            "id": self.id, "title": c["title"], "setting": c["setting"], "intro": c["intro"],
            "victim": c["victim"], "difficulty": self.difficulty,
            "turns_left": self.turns_left, "over": self.over, "result": self.result,
            "ai_enabled": self.ai.enabled, "ai_generated_case": self.ai_generated,
            "suspects": [{"id": i, "name": s["name"], "role": s["role"],
                          "personality": s["personality"],
                          "questioned": i in self.interviews} for i, s in enumerate(c["suspects"])],
            "locations": [{"id": i, "name": l["name"], "description": l["description"],
                           "searched": i in self.found} for i, l in enumerate(c["locations"])],
            "clues": [{"location": c["locations"][i]["name"], "text": c["locations"][i]["clue"]}
                      for i in self.found],
            "log": self.log, "notices": notices,
        }


class GameStore:
    """In-memory store of running games (fine for a single-player prototype)."""

    def __init__(self, ai=None):
        self.ai = ai or StoryAI()
        self.games = {}

    def new_game(self, theme, difficulty):
        theme = (theme or "").strip()
        if len(theme) > MAX_THEME_LEN:
            raise GameError(f"Theme must be under {MAX_THEME_LEN} characters.")
        if difficulty not in MAX_TURNS:
            raise GameError("Difficulty must be easy, normal or hard.")
        game = Game(self.ai, theme or "a snowed-in mountain lodge", difficulty)
        if len(self.games) > 200:
            self.games.pop(next(iter(self.games)))
        self.games[game.id] = game
        return game

    def get(self, game_id):
        game = self.games.get(game_id)
        if not game:
            raise GameError("Game not found - it may have expired. Start a new case.")
        return game
