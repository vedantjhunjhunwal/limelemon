# 🕵️ AI Detective: a Generative-AI mystery game

A playable browser-based detective game. **Every case is written by Generative AI while you play.**
You choose a setting ("a luxury train crossing the Alps in 1920", "a space station", "a school
science fair"…). The AI then invents the victim, four suspects with secrets and alibis, five
locations with hidden clues and red herrings, and the solution. You search rooms, question suspects
in your own words, ask your assistant for hints, and finally accuse someone and explain why.
The AI plays each suspect in character, judges how good your reasoning was, and writes the ending.

## Submission contents

| Required item | Where to find it |
|---|---|
| **Working prototype / project files** | The whole `ai-detective-game/` folder. Run it with `python app.py` (see [How to run](#how-to-run)) |
| **Short README: game concept, tools used, how to run** | This file: [Game concept](#game-concept), [Tools used](#tools-used), [How to run](#how-to-run) |
| **Where and how Generative AI is used** | [Where and how Generative AI is used](#where-and-how-generative-ai-is-used) below; the code is in `game/ai.py` |
| **Short demonstration during evaluation** | [`DEMO.md`](DEMO.md): a 5-minute step-by-step script that goes from the start to an outcome. Also see `screenshots/` and the automated tests in `tests/` |

The assignment brief is in [`ASSIGNMENT.md`](ASSIGNMENT.md), and [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) shows how each requirement is met.

## Game concept

| Phase | What the player does | What the AI generates |
|-------|---------------------|------------------------|
| 1. New case | Types a theme, picks a difficulty | The whole case: title, intro, victim, 4 suspects (personality, alibi, secret, one culprit), 5 locations + clues (genuine and red herrings), motive, method, solution |
| 2. Investigate | Clicks a location (costs 1 turn) | Atmospheric narration of the search and the clue found |
| 3. Interrogate | Types **any free-text question** to a suspect (1 turn) | In-character NPC dialogue. The NPC remembers the conversation, knows which evidence you have found, and the culprit lies but slips up when you confront them with evidence |
| 4. Hint | Asks the assistant (1 turn) | A hint based on what you have and have not found yet |
| 5. Accuse | Picks a suspect and writes their reasoning | A score for the reasoning (0-100), feedback, and a dramatic epilogue (justice served or the killer escapes) |

**Outcome:** win (right culprit) or lose (wrong culprit, the killer escapes). Score = 500 for the right
culprit + 20 per unused turn + 3 × the reasoning score. Ranks: Master Detective / Inspector / Rookie / Case Unsolved.
Difficulty changes the number of turns (16 / 12 / 9) and red herrings (1 / 1 / 2).

## Tools used

- **Python 3.10+** with **Flask** (web server and game API)
- **Anthropic Claude API** (`anthropic` Python SDK), default model `claude-opus-5-5`, using
  **structured outputs** (JSON schema) so generated cases are machine-readable
- **HTML / CSS / vanilla JavaScript** front end (no build step)
- **pytest** for automated tests (the AI is mocked)

## How to run

```bash
cd ai-detective-game
pip install -r requirements.txt

# AI mode (recommended): get a key at https://console.anthropic.com
export ANTHROPIC_API_KEY="sk-ant-..."        # Windows: set ANTHROPIC_API_KEY=sk-ant-...
python app.py
```

Then open **http://127.0.0.1:5000** in a browser.
Shortcuts: `./run.sh` (macOS/Linux) or `run.bat` (Windows) create a virtualenv, install dependencies and start the server.

Optional settings:
- `CLAUDE_MODEL=claude-haiku-5-5` uses a faster, cheaper model (any Claude model id works)
- `OFFLINE_MODE=1` forces the built-in backup generator (no AI calls)
- `PORT=8000` changes the port

**No API key?** The game still runs in *offline mode*, using a procedural backup generator, and the
top-right badge says so. That way the demo works even without internet. With a key, all content is AI-generated.

Run the tests: `python -m pytest -q`

## Where and how Generative AI is used

All AI calls are in [`game/ai.py`](game/ai.py). There are five runtime uses:

1. **Case generation** (`generate_case`): the player's theme and difficulty go into a prompt. Claude
   returns a full mystery as JSON, which a **JSON schema** (structured outputs) holds to a fixed shape.
   The engine then **validates** it (exactly one culprit, at least one genuine clue pointing to them,
   unique names). If the case can't be played, a backup case is used instead.
2. **Investigation narration** (`narrate_investigation`): Claude writes the discovery scene for the clue in that room.
3. **NPC interrogation** (`interrogate`): each suspect is a separate role-play, with a system prompt
   holding their personality, alibi, secret, whether they are guilty, and **the evidence the player has found so far**.
   The last 8 question/answer pairs are sent as conversation history, so suspects remember what you
   asked. Because the player types free text, every conversation is different.
4. **Adaptive hints** (`hint`): Claude sees the secret solution and the player's progress, and nudges
   the player without giving the answer away.
5. **Judging and epilogue** (`judge_accusation`): the game code decides right or wrong (so the AI can't
   be argued into a different verdict). Claude scores the *quality* of the player's written reasoning
   against the true motive and method, and writes a personal ending.

The solution is **never sent to the browser** until the game ends (`Game.public_state`), so players can't cheat.

## Error handling

- **Invalid player input** is rejected with a friendly message and **costs no turn**: empty or
  overlong questions, unknown suspect or location ids, searching a room twice, acting after the
  turns run out, accusing without a reason, a non-JSON request, or an expired game id.
- **AI/API errors** (missing or invalid key, rate limit, timeout, network failure, server error,
  refusal, empty or malformed JSON, an unplayable case) are caught in `StoryAI._call` and become
  `AIUnavailable`. The engine then uses **offline backup content** for that step and shows a
  one-time warning toast. Each log entry is tagged `AI` or `offline` so you can see which was used.
  An invalid key turns the AI off for the session, so the game doesn't keep retrying.
- The SDK retries temporary failures automatically (2 retries, 90 s timeout).
- Unexpected server errors return a JSON error instead of crashing. The front end shows server and
  network errors in a toast and inserts all AI text with `textContent` (no HTML injection).

## Project structure

```
ai-detective-game/
├── app.py               Flask server + JSON API
├── game/
│   ├── ai.py            Claude integration (prompts, schemas, error handling)
│   ├── engine.py        Game rules, state, validation, scoring
│   └── fallback.py      Offline backup generator
├── templates/index.html Game UI
├── static/app.js        Front-end logic
├── static/style.css     Styling
├── tests/test_game.py   Automated tests (AI mocked)
├── DEMO.md              Script for the demonstration
├── ASSIGNMENT.md        The assignment brief
├── SUBMISSION_CHECKLIST.md  Requirement → implementation mapping
├── requirements.txt, run.sh, run.bat
```
