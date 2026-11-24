import re
from bs4 import BeautifulSoup


def plain(html):
    soup = BeautifulSoup((html or "")[:180000], "html.parser")
    for tag in soup.select("script,style,nav,footer,header,aside,form,iframe"):
        tag.decompose()
    return " ".join(soup.stripped_strings).strip()


def chunks(text, limit=820):
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    buffer = ""
    for sentence in sentences:
        if len(buffer) + len(sentence) > limit and buffer:
            yield buffer
            buffer = ""
        if len(sentence) > limit:
            for start in range(0, len(sentence), limit):
                yield sentence[start : start + limit]
        else:
            buffer = (buffer + " " + sentence).strip()
    if buffer:
        yield buffer
