from symai import Expression

_prompt = """Generate a descriptive title for the given text in at most <n>{n}</n> words.

<text>{text}</text>"""


def generate_title(intent: str, max_n_words: int = 7):
    """Generates a short title that describes the given user `intent` in at most `max_n_words`"""

    for _ in range(3):  # at most three retries
        res = Expression.prompt(_prompt.format(text=intent, n=max_n_words)).value

        if not res or not isinstance(res, str):
            continue

        words = res.strip().split()
        if len(words) > max_n_words or len(words) == 0:
            # retry! either too short or too long
            continue

        return " ".join(words).strip("\"'")

    msg = f"Could not generate title for text '{intent}' in <={max_n_words} words"
    raise ValueError(msg)
