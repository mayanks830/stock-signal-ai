POSITIVE = [
    "beat", "beats", "topped", "exceeded", "surpassed", "upgrade", "upgraded",
    "raises guidance", "raised guidance", "raises outlook", "partnership", "launches",
    "record", "strong", "surge", "surges", "outperform", "buy rating", "approval",
    "approved", "wins", "awarded", "breakthrough", "growth", "profit", "bullish",
    "above expectations", "better than expected", "dividend", "buyback",
]

NEGATIVE = [
    "miss", "misses", "missed", "below expectations", "downgrade", "downgraded",
    "lowers guidance", "lowered guidance", "cuts guidance", "recall", "investigation",
    "lawsuit", "drop", "drops", "weak", "bearish", "sell rating", "warning",
    "breach", "fraud", "loss", "losses", "layoff", "layoffs", "restructuring",
    "worse than expected", "disappointing", "concern", "risk", "decline",
]


def score_headline(headline: str) -> float:
    text = headline.lower()
    pos = sum(1 for kw in POSITIVE if kw in text)
    neg = sum(1 for kw in NEGATIVE if kw in text)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 2)


def score_headlines(news: list[dict]) -> float:
    if not news:
        return 0.0
    scores = [score_headline(n.get("title", "")) for n in news]
    return round(sum(scores) / len(scores), 2)


def label_headlines(news: list[dict]) -> list[dict]:
    labeled = []
    for item in news:
        score = score_headline(item.get("title", ""))
        label = "POSITIVE" if score > 0 else ("NEGATIVE" if score < 0 else "NEUTRAL")
        labeled.append({**item, "sentiment": label, "score": score})
    return labeled
