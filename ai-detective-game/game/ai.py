"""Generative AI layer: every call to Claude goes through this module.

If no API key is configured, or a call fails (network, rate limit, refusal,
malformed output), the caller gets an AIUnavailable exception and falls back
to the offline generator in `fallback.py`, so the game never crashes.
"""
import json
import os

import anthropic

DEFAULT_MODEL = "claude-opus-5-5"


class AIUnavailable(Exception):
    """Raised when the AI could not produce usable content."""


# JSON schema for a generated mystery case (used with structured outputs).
CASE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "setting": {"type": "string"},
        "intro": {"type": "string"},
        "victim": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
            "required": ["name", "description"],
            "additionalProperties": False,
        },
        "suspects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "personality": {"type": "string"},
                    "alibi": {"type": "string"},
                    "secret": {"type": "string"},
                    "is_culprit": {"type": "boolean"},
                },
                "required": ["name", "role", "personality", "alibi", "secret", "is_culprit"],
                "additionalProperties": False,
            },
        },
        "locations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "clue": {"type": "string"},
                    "points_to": {"type": "string"},
                    "is_red_herring": {"type": "boolean"},
                },
                "required": ["name", "description", "clue", "points_to", "is_red_herring"],
                "additionalProperties": False,
            },
        },
        "motive": {"type": "string"},
        "method": {"type": "string"},
        "solution": {"type": "string"},
    },
    "required": ["title", "setting", "intro", "victim", "suspects", "locations",
                 "motive", "method", "solution"],
    "additionalProperties": False,
}

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning_score": {"type": "integer"},
        "feedback": {"type": "string"},
        "epilogue": {"type": "string"},
    },
    "required": ["reasoning_score", "feedback", "epilogue"],
    "additionalProperties": False,
}

GM_SYSTEM = (
    "You are the game master of a text-based detective game. You write vivid, "
    "concise, family-friendly mystery fiction (no gore). Stay consistent with the "
    "case facts you are given, never reveal the culprit unless told to, and keep "
    "replies short enough to read in a game UI."
)


class StoryAI:
    def __init__(self):
        self.model = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)
        self.last_error = None
        self.client = None
        if os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("OFFLINE_MODE") != "1":
            self.client = anthropic.Anthropic(max_retries=2, timeout=90.0)

    @property
    def enabled(self):
        return self.client is not None

    # ---- low-level call with error handling -------------------------------
    def _call(self, prompt, max_tokens=2000, schema=None, system=GM_SYSTEM, messages=None):
        if not self.enabled:
            raise AIUnavailable("No ANTHROPIC_API_KEY set - running in offline mode.")
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages or [{"role": "user", "content": prompt}],
            "output_config": {"effort": "low"},
        }
        if schema:
            kwargs["output_config"]["format"] = {"type": "json_schema", "schema": schema}
        try:
            response = self.client.messages.create(**kwargs)
        except anthropic.AuthenticationError:
            self.client = None  # bad key: stop trying for the rest of the session
            raise AIUnavailable("Invalid API key - switched to offline mode.")
        except anthropic.RateLimitError:
            raise AIUnavailable("AI rate limit reached - using backup content.")
        except anthropic.APITimeoutError:
            raise AIUnavailable("AI request timed out - using backup content.")
        except anthropic.APIConnectionError:
            raise AIUnavailable("Could not reach the AI service - using backup content.")
        except anthropic.APIStatusError as e:
            raise AIUnavailable(f"AI service error ({e.status_code}) - using backup content.")

        if response.stop_reason == "refusal":
            raise AIUnavailable("The AI declined this request - using backup content.")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise AIUnavailable("The AI returned an empty response - using backup content.")
        if schema:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                raise AIUnavailable("The AI returned malformed data - using backup content.")
        return text

    # ---- game-specific generators ----------------------------------------
    def generate_case(self, theme, difficulty):
        prompt = (
            f"Create an original murder-mystery case for a detective game.\n"
            f"Player's requested theme/setting: \"{theme}\"\nDifficulty: {difficulty}\n\n"
            "Rules:\n"
            "- Exactly 4 suspects; exactly ONE has is_culprit=true.\n"
            "- Exactly 5 locations, each hiding one clue. 'points_to' must be the exact "
            "name of one suspect. At least 3 genuine clues must point to the culprit; "
            f"{'2' if difficulty == 'hard' else '1'} clue(s) should be red herrings "
            "pointing to innocent suspects.\n"
            "- Every suspect has a secret (innocent suspects hide something embarrassing "
            "but unrelated); the culprit's alibi has a flaw a clue exposes.\n"
            "- intro: 3-4 sentences setting the scene for the detective (the player).\n"
            "- solution: 2-3 sentences explaining who did it, how and why."
        )
        return self._call(prompt, max_tokens=4000, schema=CASE_SCHEMA)

    def narrate_investigation(self, case, location, found_count):
        prompt = (
            f"Case: {case['title']} ({case['setting']}). Victim: {case['victim']['name']}.\n"
            f"The detective searches: {location['name']} - {location['description']}\n"
            f"The clue they find: {location['clue']}\n"
            f"They have now found {found_count} of {len(case['locations'])} clues.\n"
            "Write 2-4 atmospheric sentences, in second person, describing the search and "
            "the discovery. Present the clue clearly but do not state who is guilty."
        )
        return self._call(prompt, max_tokens=600)

    def interrogate(self, case, suspect, history, question, found_clues):
        clues = "\n".join(f"- {c}" for c in found_clues) or "- (none yet)"
        system = (
            f"You are role-playing {suspect['name']}, {suspect['role']}, a suspect in a "
            f"detective game. Setting: {case['setting']}. Victim: {case['victim']['name']} "
            f"({case['victim']['description']}).\n"
            f"Personality: {suspect['personality']}\nYour alibi: {suspect['alibi']}\n"
            f"Your secret: {suspect['secret']}\n"
            + (
                f"YOU ARE THE CULPRIT. Motive: {case['motive']}. Method: {case['method']}. "
                "Lie to protect yourself, but if the detective confronts you with strong "
                "evidence, become flustered and let small inconsistencies slip. Never "
                "confess outright."
                if suspect["is_culprit"]
                else "You are innocent of the murder. You may be evasive about your secret "
                "but will reveal it if pressed hard or confronted with evidence."
            )
            + f"\n\nEvidence the detective has found so far:\n{clues}\n\n"
            "Reply in character, in 1-4 sentences of spoken dialogue (you may include a "
            "brief *action* in asterisks). Never break character or mention being an AI. "
            "If the question is off-topic or nonsense, react as the character naturally would."
        )
        messages = []
        for turn in history[-8:]:
            messages.append({"role": "user", "content": turn["q"]})
            messages.append({"role": "assistant", "content": turn["a"]})
        messages.append({"role": "user", "content": question})
        return self._call(None, max_tokens=500, system=system, messages=messages)

    def hint(self, case, found_clues, interviews):
        prompt = (
            f"Case facts (SECRET, do not reveal directly): culprit is "
            f"{next(s['name'] for s in case['suspects'] if s['is_culprit'])}; "
            f"solution: {case['solution']}\n"
            f"Clues found by the player: {found_clues or 'none'}\n"
            f"Suspects already questioned: {interviews or 'none'}\n"
            "As the detective's loyal assistant, give ONE short, nudging hint (1-2 "
            "sentences) about what to look at or ask next. Do not name the culprit."
        )
        return self._call(prompt, max_tokens=300)

    def judge_accusation(self, case, accused, reasoning, correct):
        prompt = (
            f"Case: {case['title']}. True culprit: "
            f"{next(s['name'] for s in case['suspects'] if s['is_culprit'])}. "
            f"Motive: {case['motive']}. Method: {case['method']}.\n"
            f"The detective accused {accused['name']} (accusation is "
            f"{'CORRECT' if correct else 'WRONG'}).\n"
            f"Their reasoning: \"{reasoning}\"\n\n"
            "Return: reasoning_score 0-100 for how well the reasoning matches the true "
            "motive/method/evidence (low if the accusation is wrong); feedback - one or two "
            "sentences to the player; epilogue - a 3-5 sentence dramatic ending scene "
            "reflecting whether justice was served."
        )
        return self._call(prompt, max_tokens=1200, schema=VERDICT_SCHEMA)
