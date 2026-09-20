from pathlib import Path
import json
import re


APPIAN_DOCS_BASE = (
    Path.home()
    / "appian-ai"
    / "knowledge"
    / "appian-docs"
    / "26.8"
)

APPIAN_DOCS_INDEX = (
    APPIAN_DOCS_BASE
    / "index"
    / "documents.jsonl"
)


def normalize(text: str) -> str:
    return text.lower().strip()


def tokenize(query: str):
    return [
        token
        for token in re.findall(
            r"[a-zA-Z0-9_!:.]+",
            normalize(query),
        )
        if len(token) > 1
    ]


def load_appian_catalog():
    documents = []

    if not APPIAN_DOCS_INDEX.exists():
        return documents

    with APPIAN_DOCS_INDEX.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            line = line.strip()

            if not line:
                continue

            try:
                documents.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return documents


def score_document(document, tokens):
    title = normalize(document.get("title", ""))

    headings = normalize(
        " ".join(document.get("headings", []))
    )

    source = normalize(
        document.get("source_file", "")
    )

    score = 0

    for token in tokens:
        if token in title:
            score += 10

        if token in headings:
            score += 5

        if token in source:
            score += 3

    return score


def read_document(document):
    relative_path = document.get("text_file")

    if not relative_path:
        return ""

    path = APPIAN_DOCS_BASE / relative_path

    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def search_appian_docs(
    query: str,
    limit: int = 5,
):
    tokens = tokenize(query)

    if not tokens:
        return []

    catalog = load_appian_catalog()

    candidates = []

    for document in catalog:
        score = score_document(
            document,
            tokens,
        )

        if score > 0:
            candidates.append(
                (
                    score,
                    document,
                )
            )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    results = []

    for score, document in candidates[:limit]:
        content = read_document(document)

        results.append(
            {
                "source": "appian_docs",
                "version": document.get(
                    "version",
                    "26.8",
                ),
                "title": document.get("title"),
                "source_file": document.get(
                    "source_file"
                ),
                "score": score,
                "content": content[:12000],
            }
        )

    return results


def search_project_knowledge(
    project_id: int,
    query: str,
    limit: int = 5,
):
    from db import get_connection

    tokens = tokenize(query)

    if not tokens:
        return []

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            knowledge_items.id,
            knowledge_items.knowledge_type,
            knowledge_items.title,
            knowledge_items.current_status,
            knowledge_items.confidence,
            knowledge_versions.id AS version_id,
            knowledge_versions.version_number,
            knowledge_versions.content,
            knowledge_versions.source_type,
            knowledge_versions.source_reference
        FROM knowledge_items
        JOIN knowledge_versions
            ON knowledge_versions.id =
               knowledge_items.current_version_id
        WHERE knowledge_items.project_id = ?
          AND knowledge_items.current_status
              IN ('confirmed', 'current')
        """,
        (project_id,),
    ).fetchall()

    conn.close()

    results = []

    for row in rows:
        title = normalize(row["title"] or "")
        content = normalize(row["content"] or "")
        knowledge_type = normalize(
            row["knowledge_type"] or ""
        )

        score = 0

        for token in tokens:
            if token in title:
                score += 10

            if token in knowledge_type:
                score += 5

            if token in content:
                score += 2

        if score == 0:
            continue

        results.append(
            {
                "source": "project_knowledge",
                "project_id": project_id,
                "knowledge_id": row["id"],
                "version_id": row["version_id"],
                "version_number": row["version_number"],
                "type": row["knowledge_type"],
                "title": row["title"],
                "status": row["current_status"],
                "confidence": row["confidence"],
                "source_type": row["source_type"],
                "source_reference": row[
                    "source_reference"
                ],
                "score": score,
                "content": row["content"],
            }
        )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:limit]
