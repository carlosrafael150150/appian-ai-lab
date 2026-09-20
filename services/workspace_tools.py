from pathlib import Path
from urllib.parse import unquote
import subprocess
import re
import xml.etree.ElementTree as ET

from db import get_connection


IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
}


def normalize(text: str) -> str:
    return (text or "").lower().strip()


def tokenize(query: str):
    return [
        token
        for token in re.findall(
            r"[a-zA-Z0-9_!:.]+",
            normalize(query),
        )
        if len(token) > 1
    ]


def get_task_workspace(task_id: int):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            workspaces.id,
            workspaces.name,
            workspaces.path,
            workspaces.branch,
            workspaces.status,
            repositories.id AS repository_id,
            repositories.name AS repository_name,
            repositories.remote_url
        FROM tasks
        JOIN workspaces
            ON workspaces.id = tasks.workspace_id
        LEFT JOIN repositories
            ON repositories.id = workspaces.repository_id
        WHERE tasks.id = ?
        """,
        (task_id,),
    ).fetchone()

    conn.close()

    if not row:
        raise ValueError(
            f"Task {task_id} has no workspace assigned"
        )

    workspace = dict(row)
    path = Path(workspace["path"]).resolve()

    if not path.exists():
        raise ValueError(
            f"Workspace path does not exist: {path}"
        )

    workspace["resolved_path"] = path

    return workspace


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def extract_xml_metadata(path: Path):
    metadata = {
        "name": None,
        "uuid": None,
        "description": None,
    }

    try:
        root = ET.parse(path).getroot()

        for element in root.iter():
            tag = local_name(element.tag).lower()

            text = (
                element.text.strip()
                if element.text
                else ""
            )

            if not text:
                continue

            if (
                metadata["name"] is None
                and tag in {
                    "name",
                    "displayname",
                    "display-name",
                    "title",
                }
            ):
                metadata["name"] = text

            if (
                metadata["uuid"] is None
                and tag in {
                    "uuid",
                    "id",
                }
            ):
                metadata["uuid"] = text

            if (
                metadata["description"] is None
                and tag == "description"
            ):
                metadata["description"] = text

    except Exception:
        pass

    return metadata


def search_workspace(
    task_id: int,
    query: str,
    limit: int = 10,
):
    workspace = get_task_workspace(task_id)
    root = workspace["resolved_path"]

    tokens = tokenize(query)

    if not tokens:
        return []

    results = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if any(
            part in IGNORED_DIRECTORIES
            for part in relative.parts
        ):
            continue

        if path.suffix.lower() not in {
            ".xml",
            ".xsd",
        }:
            continue

        object_type = (
            relative.parts[0]
            if len(relative.parts) > 1
            else "root"
        )

        metadata = {
            "name": None,
            "uuid": None,
            "description": None,
        }

        if path.suffix.lower() == ".xml":
            metadata = extract_xml_metadata(path)

        name = (
            metadata["name"]
            or unquote(path.stem)
        )

        searchable_name = normalize(name)
        searchable_type = normalize(object_type)
        searchable_path = normalize(str(relative))
        searchable_description = normalize(
            metadata["description"]
        )

        score = 0

        for token in tokens:
            if token in searchable_name:
                score += 15

            if token in searchable_type:
                score += 8

            if token in searchable_path:
                score += 5

            if token in searchable_description:
                score += 3

        if score == 0:
            continue

        results.append(
            {
                "source": "workspace",
                "task_id": task_id,
                "workspace_id": workspace["id"],
                "type": object_type,
                "name": name,
                "uuid": metadata["uuid"],
                "description": metadata["description"],
                "path": str(relative),
                "extension": path.suffix.lower(),
                "score": score,
            }
        )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:limit]


def read_workspace_file(
    task_id: int,
    relative_path: str,
):
    workspace = get_task_workspace(task_id)
    root = workspace["resolved_path"]

    target = (root / relative_path).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(
            "Requested file is outside the workspace"
        )

    if not target.exists() or not target.is_file():
        raise ValueError(
            f"File not found: {relative_path}"
        )

    return {
        "task_id": task_id,
        "workspace_id": workspace["id"],
        "path": relative_path,
        "content": target.read_text(
            encoding="utf-8",
            errors="ignore",
        ),
    }


def run_git(root: Path, *args):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or "Git command failed"
        )

    return result.stdout


def workspace_status(task_id: int):
    workspace = get_task_workspace(task_id)
    root = workspace["resolved_path"]

    output = run_git(
        root,
        "status",
        "--short",
    )

    changes = []

    for line in output.splitlines():
        if not line.strip():
            continue

        changes.append(
            {
                "status": line[:2],
                "path": line[3:],
            }
        )

    return {
        "task_id": task_id,
        "workspace_id": workspace["id"],
        "branch": workspace["branch"],
        "clean": len(changes) == 0,
        "changes": changes,
    }


def workspace_diff(task_id: int):
    workspace = get_task_workspace(task_id)
    root = workspace["resolved_path"]

    unstaged = run_git(
        root,
        "diff",
        "--no-ext-diff",
    )

    staged = run_git(
        root,
        "diff",
        "--cached",
        "--no-ext-diff",
    )

    return {
        "task_id": task_id,
        "workspace_id": workspace["id"],
        "branch": workspace["branch"],
        "unstaged": unstaged,
        "staged": staged,
    }


def workspace_changeset(task_id: int):
    workspace = get_task_workspace(task_id)
    root = workspace["resolved_path"]

    output = run_git(
        root,
        "status",
        "--porcelain=v1",
        "-z",
    )

    entries = output.split("\0")
    changes = []

    index = 0

    while index < len(entries):
        entry = entries[index]

        if not entry:
            index += 1
            continue

        status = entry[:2]
        path = entry[3:]

        index_status = status[0]
        worktree_status = status[1]

        change_type = "modified"

        if status == "??":
            change_type = "untracked"

        elif "A" in status:
            change_type = "added"

        elif "D" in status:
            change_type = "deleted"

        elif "R" in status:
            change_type = "renamed"

        elif "C" in status:
            change_type = "copied"

        elif "M" in status:
            change_type = "modified"

        original_path = None

        if (
            index_status in {"R", "C"}
            or worktree_status in {"R", "C"}
        ):
            if index + 1 < len(entries):
                original_path = path
                index += 1
                path = entries[index]

        absolute_path = (root / path).resolve()

        size = None

        if absolute_path.exists() and absolute_path.is_file():
            size = absolute_path.stat().st_size

        parts = Path(path).parts

        object_type = (
            parts[0]
            if len(parts) > 1
            else "root"
        )

        changes.append(
            {
                "status": status,
                "index_status": index_status,
                "worktree_status": worktree_status,
                "change_type": change_type,
                "path": path,
                "original_path": original_path,
                "object_type": object_type,
                "size": size,
            }
        )

        index += 1

    summary = {
        "modified": 0,
        "added": 0,
        "deleted": 0,
        "renamed": 0,
        "copied": 0,
        "untracked": 0,
    }

    for change in changes:
        change_type = change["change_type"]

        if change_type in summary:
            summary[change_type] += 1

    return {
        "task_id": task_id,
        "workspace_id": workspace["id"],
        "workspace": workspace["name"],
        "branch": workspace["branch"],
        "clean": len(changes) == 0,
        "summary": summary,
        "changes": changes,
    }


def read_untracked_file(
    task_id: int,
    relative_path: str,
):
    workspace = get_task_workspace(task_id)
    root = workspace["resolved_path"]

    target = (root / relative_path).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(
            "Requested file is outside the workspace"
        )

    if not target.exists() or not target.is_file():
        raise ValueError(
            f"File not found: {relative_path}"
        )

    status = run_git(
        root,
        "status",
        "--porcelain",
        "--",
        relative_path,
    ).strip()

    if not status.startswith("??"):
        raise ValueError(
            "Requested file is not untracked"
        )

    return {
        "task_id": task_id,
        "workspace_id": workspace["id"],
        "path": relative_path,
        "content": target.read_text(
            encoding="utf-8",
            errors="ignore",
        ),
    }
