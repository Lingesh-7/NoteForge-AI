import re

def clean_topics(text):
    topics = []

    for line in text.split("\n"):
        line = line.strip()

        if not line:
            continue

        # remove numbering
        line = re.sub(r"^\d+[\).\-\s]*", "", line)

        # split if colon exists
        if ":" in line:
            main, subs = line.split(":", 1)
            main = main.strip()

            subtopics = [s.strip() for s in subs.split(",") if s.strip()]

            for sub in subtopics:
                topics.append(f"{main} - {sub}")
        else:
            topics.append(line)

    return topics