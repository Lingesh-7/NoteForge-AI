import re


def clean_topics(text):
    topics = []

    for line in text.split("\n"):
        line = line.strip()

        if not line:
            continue

        # remove numbering
        line = re.sub(r"^\d+[\).\-\s]*", "", line)

        if not line:
            continue

        if ":" in line:
            main, subs = line.split(":", 1)
            main = main.strip()

            subtopics = [s.strip() for s in subs.split(",") if s.strip()]

            if subtopics:
                for sub in subtopics:
                    topics.append(f"{main} - {sub}")
            elif main:
                topics.append(main)
        else:
            topics.append(line)

    return topics
