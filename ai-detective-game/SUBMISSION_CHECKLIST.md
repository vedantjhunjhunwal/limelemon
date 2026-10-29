# How this submission meets the brief

**Chosen concept:** Mystery / Detective Game, with AI-powered NPCs (two of the listed concepts combined).

| Requirement | How it is met | Where |
|---|---|---|
| Playable game | Browser game: search locations, type questions to suspects, ask for hints, make an accusation | `templates/index.html`, `static/app.js` |
| Generative AI integration | The Claude API generates the case (victim, suspects, clues, solution), search narration, suspect dialogue, hints, reasoning score and epilogue **at runtime** | `game/ai.py` |
| Content based on player input/choices/progress | The case is built from the player's typed theme and difficulty. Dialogue answers the player's free-text questions and reacts to clues found. Hints adapt to progress. The ending reflects who was accused and why | `game/ai.py`, `game/engine.py` |
| Player interaction | Each action changes the game state (turns, notebook, log) and gets an immediate response | `game/engine.py` |
| Meaningful outcome | Accuse a suspect: win or lose, epilogue, true solution, score and rank | `Game.accuse` in `game/engine.py` |
| Error handling: invalid input | Empty or too-long questions, unknown ids, repeated searches, no turns left, missing reasoning, bad JSON and expired games are all rejected with a message, and no turn is used | `game/engine.py`, `app.py` |
| Error handling: AI/API errors | Missing or invalid key, rate limit, timeout, network, server error, refusal and malformed or unplayable output are caught, and backup content is used with a warning | `StoryAI._call`, `validate_case`, `game/fallback.py` |
| Not pre-written | Nothing is pre-written in AI mode. Every case and conversation is generated live (the offline backup exists only for when the AI fails) | |
| README (concept, tools, how to run) | Included | `README.md` |
| Explanation of where and how GenAI is used | Included | `README.md` → "Where and how Generative AI is used" |
| Demonstration | Step-by-step demo script, plus screenshots and automated tests | `DEMO.md`, `screenshots/`, `tests/` |
