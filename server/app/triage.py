def triage_score(answers):
    score = 0
    if answers.get("chest_pain"): score += 2
    if answers.get("shortness_of_breath"): score += 2
    if answers.get("dizziness"): score += 1

    if score >= 3: return score, "urgent"
    elif score == 2: return score, "attention"
    else: return score, "normal"
