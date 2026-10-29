"""Flask web server for the AI Detective game.  Run:  python app.py"""
import os

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from game.engine import GameError, GameStore

app = Flask(__name__)
store = GameStore()


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise GameError("Request body must be JSON.")
    return data


@app.errorhandler(GameError)
def handle_game_error(e):
    return jsonify({"error": str(e)}), 400


@app.errorhandler(Exception)
def handle_unexpected(e):
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
    app.logger.exception("Unexpected error")
    return jsonify({"error": "Something went wrong on the server. Please try again."}), 500


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify({"ai_enabled": store.ai.enabled, "model": store.ai.model})


@app.post("/api/new")
def new_game():
    data = body()
    game = store.new_game(data.get("theme", ""), data.get("difficulty", "normal"))
    return jsonify(game.public_state())


@app.post("/api/<game_id>/investigate")
def investigate(game_id):
    game = store.get(game_id)
    game.investigate(body().get("location_id"))
    return jsonify(game.public_state())


@app.post("/api/<game_id>/interrogate")
def interrogate(game_id):
    game = store.get(game_id)
    data = body()
    game.interrogate(data.get("suspect_id"), data.get("question"))
    return jsonify(game.public_state())


@app.post("/api/<game_id>/hint")
def hint(game_id):
    game = store.get(game_id)
    game.hint()
    return jsonify(game.public_state())


@app.post("/api/<game_id>/accuse")
def accuse(game_id):
    game = store.get(game_id)
    data = body()
    game.accuse(data.get("suspect_id"), data.get("reasoning"))
    return jsonify(game.public_state())


if __name__ == "__main__":
    mode = f"AI mode ({store.ai.model})" if store.ai.enabled else "OFFLINE mode (no API key)"
    print(f"\n  AI Detective running in {mode}\n  Open http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
