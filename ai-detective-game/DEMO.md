# Demonstration script (about 5 minutes)

1. **Start**: `export ANTHROPIC_API_KEY=...` then `python app.py`, and open http://127.0.0.1:5000.
   Point out the green badge `AI: claude-opus-5-5` (top right).
2. **Player input shapes the AI**: type a theme such as *"a luxury train crossing the Alps in 1920"*,
   choose *Normal*, and click **Generate case**. Show that the title, victim, suspects and rooms all fit
   the theme. Generate a second case with a different theme to show it is not pre-written.
3. **Investigate**: search two or three locations. The clues appear in the Notebook, and each log
   entry is tagged `AI`.
4. **AI NPC dialogue**: question a suspect: *"Where were you at midnight?"*, then follow up using a
   clue you found: *"Then why was your handwriting on the note in the study?"* The suspect remembers the
   conversation and reacts to the evidence.
5. **Hint**: click *Ask assistant for a hint* and show that it depends on your progress.
6. **Error handling**:
   - Try to send an empty question, or search the same room twice: you get a friendly error and no turn is used.
   - Stop the server and click a button: the toast says it can't reach the server.
   - Restart with `OFFLINE_MODE=1 python app.py` (or with no key, or a wrong key): the game falls back to
     backup content and shows a warning, and entries are tagged `offline`.
7. **Outcome**: click **Make accusation**, pick a suspect, write your reasoning, and submit. Show the
   AI-written epilogue, the reasoning score and feedback, the true solution, the final score and the rank.
8. **Tests**: `python -m pytest -q` runs 13 tests, covering a full game, invalid input, AI errors
   falling back to offline content, and the HTTP API.
