"""Offline backup content, used when the AI is not configured or a call fails.

It builds a random (but internally consistent) case from small word pools, so
the game is still fully playable without network access.
"""
import random

NAMES = ["Evelyn Hart", "Marcus Vale", "Priya Nair", "Oscar Bellamy", "Lena Fischer",
         "Theo Grant", "Isabel Cruz", "Rafael Moreau", "Hana Sato", "Victor Ashby"]
ROLES = [("the butler", "formal, precise, protective of the household"),
         ("the business partner", "charming, ambitious, quick to change the subject"),
         ("the estranged niece", "sarcastic, defensive, secretly sentimental"),
         ("the family doctor", "calm, clinical, chooses words carefully"),
         ("the gardener", "quiet, blunt, notices everything"),
         ("the famous chef", "dramatic, proud, easily offended")]
SECRETS = ["I've been gambling away my savings", "I'm secretly writing a tell-all memoir",
           "I forged a reference letter to get hired", "I'm planning to elope next week",
           "I've been selling antiques from the attic", "I was once arrested under another name"]
ALIBIS = ["I was in the library reading all evening", "I was walking in the garden",
          "I was on a long phone call in the study", "I was preparing dessert in the kitchen",
          "I went to bed early with a headache", "I was fixing the generator in the cellar"]
LOCATIONS = [("The Study", "a wood-panelled room lined with ledgers"),
             ("The Kitchen", "copper pans, a cold stove and a half-eaten cake"),
             ("The Greenhouse", "humid air, orchids and a cracked pane of glass"),
             ("The Library", "towering shelves and a fireplace still warm"),
             ("The Cellar", "damp stone steps and rows of dusty wine"),
             ("The Ballroom", "a grand piano and scattered party streamers")]
MOTIVES = ["the victim had discovered they were embezzling money",
           "they would inherit a fortune under the new will",
           "the victim was about to expose a long-buried scandal"]
METHODS = ["poisoned the victim's evening tea", "pushed the victim down the stairs",
           "tampered with the victim's heart medication"]


def generate_case(theme, difficulty):
    rng = random.Random()
    names = rng.sample(NAMES, 5)
    victim, suspect_names = names[0], names[1:]
    roles, secrets = rng.sample(ROLES, 4), rng.sample(SECRETS, 4)
    alibis, locs = rng.sample(ALIBIS, 4), rng.sample(LOCATIONS, 5)
    culprit_idx = rng.randrange(4)
    motive, method = rng.choice(MOTIVES), rng.choice(METHODS)
    setting = theme.strip() or "Blackwood Manor on a stormy night"

    suspects = []
    for i, name in enumerate(suspect_names):
        suspects.append({
            "name": name, "role": roles[i][0], "personality": roles[i][1],
            "alibi": f"{alibis[i]}.", "secret": f"{secrets[i]}.",
            "is_culprit": i == culprit_idx,
        })
    culprit = suspects[culprit_idx]
    innocents = [s for s in suspects if not s["is_culprit"]]
    herrings = 2 if difficulty == "hard" else 1
    clue_texts = [
        (f"A torn note in {culprit['name']}'s handwriting: 'It ends tonight.'", culprit, False),
        (f"A witness statement saying {culprit['name']} was NOT where they claimed: "
         f"their story ('{culprit['alibi']}') doesn't hold up.", culprit, False),
        (f"Evidence that someone {method}; it matches {culprit['name']}'s access.", culprit, False),
    ]
    for s in rng.sample(innocents, herrings):
        clue_texts.append((f"A muddy footprint near the scene, matching {s['name']}'s shoes - "
                           "but the mud is days old.", s, True))
    while len(clue_texts) < 5:
        clue_texts.append((f"A receipt showing {culprit['name']} recently bought something "
                           "unusual.", culprit, False))
    rng.shuffle(clue_texts)

    locations = [{"name": n, "description": d, "clue": c, "points_to": who["name"],
                  "is_red_herring": rh}
                 for (n, d), (c, who, rh) in zip(locs, clue_texts)]
    return {
        "title": f"The {rng.choice(['Silent', 'Midnight', 'Crimson', 'Final'])} "
                 f"{rng.choice(['Toast', 'Curtain', 'Waltz', 'Ledger'])}",
        "setting": setting,
        "intro": (f"The setting: {setting}. {victim} has been found dead, and the guests are "
                  "trapped until morning. Four people had the chance to do it. You have "
                  "limited time to search the grounds, question the suspects and name the killer."),
        "victim": {"name": victim, "description": "the wealthy host of the evening"},
        "suspects": suspects, "locations": locations,
        "motive": motive, "method": method,
        "solution": f"{culprit['name']} {method} because {motive}.",
    }


def narrate_investigation(location):
    return (f"You carefully search {location['name']} - {location['description']}. "
            f"Something catches your eye. {location['clue']}")


def interrogate(suspect, question, found_clues):
    q = question.lower()
    mentions_evidence = any(suspect["name"].split()[0].lower() in c.lower() for c in found_clues)
    if any(w in q for w in ("alibi", "where", "when", "doing")):
        return f"\"I told you already. {suspect['alibi']}\" *{suspect['name'].split()[0]} meets your gaze.*"
    if any(w in q for w in ("secret", "hide", "hiding", "lie", "lying", "truth")):
        if suspect["is_culprit"]:
            return "\"I have nothing to hide, detective.\" *Their hands tremble slightly.*"
        return f"*A long sigh.* \"Fine... {suspect['secret']} But I didn't kill anyone!\""
    if mentions_evidence and suspect["is_culprit"]:
        return "\"That... that proves nothing! Anyone could have done that!\" *They avoid your eyes.*"
    if any(w in q for w in ("victim", "kill", "murder", "die", "dead")):
        return "\"It's terrible. We all had our disagreements with them, but murder?\""
    return f"\"I'm {suspect['role']}. I'm not sure what you want me to say, detective.\""


def hint(case, found_count):
    if found_count < 3:
        return "Assistant: \"We haven't searched enough. Every room hides something - keep looking.\""
    return ("Assistant: \"Compare each suspect's alibi with the clues. One of those stories "
            "doesn't hold together - and watch out for evidence that looks too old.\"")


def judge_accusation(case, accused, reasoning, correct):
    words = set(reasoning.lower().split())
    key = set((case["motive"] + " " + case["method"]).lower().split())
    overlap = len(words & key - {"the", "a", "to", "of", "they", "was", "had", "victim's"})
    score = min(100, 40 + overlap * 10) if correct else min(30, overlap * 5)
    if correct:
        epilogue = (f"The room falls silent. {accused['name']} finally breaks: the truth is that "
                    f"they {case['method']} because {case['motive']}. Justice is served.")
        feedback = "Well done - you named the right suspect."
    else:
        culprit = next(s for s in case["suspects"] if s["is_culprit"])
        epilogue = (f"{accused['name']} is led away protesting. Weeks later, new evidence "
                    f"reveals {culprit['name']} was the real killer - and they are long gone.")
        feedback = "The evidence pointed elsewhere. Look again at the alibis and red herrings."
    return {"reasoning_score": score, "feedback": feedback, "epilogue": epilogue}
