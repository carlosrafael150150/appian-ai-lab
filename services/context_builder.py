from pathlib import Path

from db import get_connection


BASE_DIR = Path(__file__).resolve().parent.parent
SYSTEM_DOCS_DIR = BASE_DIR / "docs" / "agent-system"


SYSTEM_DOCUMENTS = [
    "ARCHITECTURE.md",
    "DOMAIN_MODEL.md",
    "AGENT_POLICY.md",
    "KNOWLEDGE_MODEL.md",
    "TASK_LIFECYCLE.md",
    "CONTEXT_MODEL.md",
]


def read_system_documents():
    documents = []

    for filename in SYSTEM_DOCUMENTS:
        path = SYSTEM_DOCS_DIR / filename

        if path.exists():
            documents.append(
                {
                    "name": filename,
                    "content": path.read_text(
                        encoding="utf-8"
                    ),
                }
            )

    return documents


def build_task_context(task_id: int):
    conn = get_connection()

    task = conn.execute(
        """
        SELECT
            tasks.*,
            projects.name AS project_name,
            projects.description AS project_description,
            workspaces.name AS workspace_name,
            workspaces.path AS workspace_path,
            workspaces.branch AS workspace_branch,
            environments.name AS environment_name,
            agents.name AS agent_name,
            models.name AS model_name,
            compute_profiles.name AS compute_name
        FROM tasks
        JOIN projects
            ON projects.id = tasks.project_id
        LEFT JOIN workspaces
            ON workspaces.id = tasks.workspace_id
        LEFT JOIN environments
            ON environments.id = tasks.environment_id
        LEFT JOIN agents
            ON agents.id = tasks.agent_id
        LEFT JOIN models
            ON models.id = tasks.model_id
        LEFT JOIN compute_profiles
            ON compute_profiles.id = tasks.compute_profile_id
        WHERE tasks.id = ?
        """,
        (task_id,),
    ).fetchone()

    if not task:
        conn.close()
        raise ValueError(f"Task {task_id} not found")

    conversation = conn.execute(
        """
        SELECT *
        FROM conversations
        WHERE task_id = ?
        ORDER BY id
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()

    messages = []

    if conversation:
        rows = conn.execute(
            """
            SELECT
                messages.*,
                agents.name AS agent_name,
                models.name AS model_name
            FROM messages
            LEFT JOIN agents
                ON agents.id = messages.agent_id
            LEFT JOIN models
                ON models.id = messages.model_id
            WHERE messages.conversation_id = ?
            ORDER BY messages.id
            """,
            (conversation["id"],),
        ).fetchall()

        messages = [dict(row) for row in rows]

    snapshot = conn.execute(
        """
        SELECT *
        FROM project_snapshots
        WHERE project_id = ?
        """,
        (task["project_id"],),
    ).fetchone()

    knowledge_rows = conn.execute(
        """
        SELECT
            knowledge_items.id,
            knowledge_items.knowledge_type,
            knowledge_items.title,
            knowledge_items.current_status,
            knowledge_items.confidence,
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
        ORDER BY knowledge_items.id
        """,
        (task["project_id"],),
    ).fetchall()

    external_refs = conn.execute(
        """
        SELECT *
        FROM task_external_references
        WHERE task_id = ?
        ORDER BY id
        """,
        (task_id,),
    ).fetchall()

    parent = None

    if task["parent_task_id"]:
        parent_row = conn.execute(
            """
            SELECT id, title, objective, status
            FROM tasks
            WHERE id = ?
            """,
            (task["parent_task_id"],),
        ).fetchone()

        if parent_row:
            parent = dict(parent_row)

    children = conn.execute(
        """
        SELECT id, title, objective, status
        FROM tasks
        WHERE parent_task_id = ?
        ORDER BY id
        """,
        (task_id,),
    ).fetchall()

    dependencies = conn.execute(
        """
        SELECT
            dependency.depends_on_task_id,
            dependency.dependency_type,
            prerequisite.title,
            prerequisite.status
        FROM task_dependencies AS dependency
        JOIN tasks AS prerequisite
            ON prerequisite.id =
               dependency.depends_on_task_id
        WHERE dependency.task_id = ?
        """,
        (task_id,),
    ).fetchall()

    conn.close()

    return {
        "platform": {
            "system_documents": read_system_documents(),
        },

        "project": {
            "id": task["project_id"],
            "name": task["project_name"],
            "description": task["project_description"],
            "snapshot": dict(snapshot) if snapshot else None,
            "knowledge": [
                dict(row) for row in knowledge_rows
            ],
        },

        "task": {
            "id": task["id"],
            "type": task["task_type"],
            "title": task["title"],
            "objective": task["objective"],
            "status": task["status"],
            "priority": task["priority"],
            "parent": parent,
            "children": [
                dict(row) for row in children
            ],
            "dependencies": [
                dict(row) for row in dependencies
            ],
            "external_references": [
                dict(row) for row in external_refs
            ],
        },

        "conversation": {
            "id": (
                conversation["id"]
                if conversation
                else None
            ),
            "messages": messages,
        },

        "workspace": {
            "id": task["workspace_id"],
            "name": task["workspace_name"],
            "path": task["workspace_path"],
            "branch": task["workspace_branch"],
        },

        "environment": {
            "id": task["environment_id"],
            "name": task["environment_name"],
        },

        "assignment": {
            "agent": task["agent_name"],
            "model": task["model_name"],
            "compute": task["compute_name"],
        },
    }
