from pathlib import Path
import subprocess

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from db import get_connection, init_db
from services.context_builder import build_task_context
from services.knowledge_tools import search_appian_docs, search_project_knowledge
from services.workspace_tools import search_workspace, read_workspace_file, workspace_status, workspace_diff, workspace_changeset


app = FastAPI(title="Appian AI Lab")
templates = Jinja2Templates(directory="templates")

init_db()


def git_value(path, *args):
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return result.stdout.strip()

    except Exception:
        pass

    return None


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    conn = get_connection()

    counts = {}

    for table in [
        "projects",
        "repositories",
        "workspaces",
        "tasks",
        "agents",
        "models",
        "compute_profiles",
        "knowledge_items",
        "skills",
        "playbooks",
        "mcp_servers",
    ]:
        counts[table] = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

    tasks = conn.execute(
        """
        SELECT
            tasks.id,
            tasks.title,
            tasks.status,
            projects.name AS project_name
        FROM tasks
        JOIN projects
            ON projects.id = tasks.project_id
        ORDER BY tasks.id DESC
        LIMIT 10
        """
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "counts": counts,
            "tasks": tasks,
        },
    )


@app.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request):
    conn = get_connection()

    projects = conn.execute(
        """
        SELECT
            projects.*,
            COUNT(DISTINCT repositories.id) AS repository_count,
            COUNT(DISTINCT tasks.id) AS task_count
        FROM projects
        LEFT JOIN repositories
            ON repositories.project_id = projects.id
        LEFT JOIN tasks
            ON tasks.project_id = projects.id
        GROUP BY projects.id
        ORDER BY projects.name
        """
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context={
            "projects": projects,
        },
    )


@app.post("/projects")
def create_project(
    name: str = Form(...),
    description: str = Form(""),
    local_path: str = Form(...),
):
    path = Path(local_path.strip()).expanduser().resolve()

    if not path.exists() or not path.is_dir():
        return RedirectResponse(
            "/projects?error=invalid_path",
            status_code=303,
        )

    if not (path / ".git").exists():
        return RedirectResponse(
            "/projects?error=not_git",
            status_code=303,
        )

    remote_url = git_value(
        path,
        "remote",
        "get-url",
        "origin",
    ) or ""

    branch = git_value(
        path,
        "branch",
        "--show-current",
    ) or "main"

    conn = get_connection()

    try:
        cursor = conn.execute(
            """
            INSERT INTO projects (
                name,
                description
            )
            VALUES (?, ?)
            """,
            (
                name.strip(),
                description.strip(),
            ),
        )

        project_id = cursor.lastrowid

        cursor = conn.execute(
            """
            INSERT INTO repositories (
                project_id,
                name,
                provider,
                remote_url,
                local_path,
                default_branch
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                path.name,
                "github"
                if "github.com" in remote_url
                else "git",
                remote_url,
                str(path),
                branch,
            ),
        )

        repository_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO workspaces (
                project_id,
                repository_id,
                name,
                path,
                branch,
                status
            )
            VALUES (?, ?, ?, ?, ?, 'idle')
            """,
            (
                project_id,
                repository_id,
                "main",
                str(path),
                branch,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        conn.close()
        raise

    conn.close()

    return RedirectResponse(
        f"/projects/{project_id}",
        status_code=303,
    )


@app.get(
    "/projects/{project_id}",
    response_class=HTMLResponse,
)
def project_detail(
    request: Request,
    project_id: int,
):
    conn = get_connection()

    project = conn.execute(
        "SELECT * FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()

    if not project:
        conn.close()
        return RedirectResponse(
            "/projects",
            status_code=303,
        )

    repositories = conn.execute(
        """
        SELECT *
        FROM repositories
        WHERE project_id = ?
        ORDER BY name
        """,
        (project_id,),
    ).fetchall()

    workspaces = conn.execute(
        """
        SELECT
            workspaces.*,
            repositories.name AS repository_name
        FROM workspaces
        LEFT JOIN repositories
            ON repositories.id = workspaces.repository_id
        WHERE workspaces.project_id = ?
        ORDER BY workspaces.name
        """,
        (project_id,),
    ).fetchall()

    tasks = conn.execute(
        """
        SELECT
            tasks.*,
            agents.name AS agent_name,
            models.name AS model_name
        FROM tasks
        LEFT JOIN agents
            ON agents.id = tasks.agent_id
        LEFT JOIN models
            ON models.id = tasks.model_id
        WHERE tasks.project_id = ?
        ORDER BY tasks.id DESC
        """,
        (project_id,),
    ).fetchall()

    snapshot = conn.execute(
        """
        SELECT *
        FROM project_snapshots
        WHERE project_id = ?
        """,
        (project_id,),
    ).fetchone()

    knowledge_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM knowledge_items
        WHERE project_id = ?
        """
        ,
        (project_id,),
    ).fetchone()[0]

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="project_detail.html",
        context={
            "project": project,
            "repositories": repositories,
            "workspaces": workspaces,
            "tasks": tasks,
            "snapshot": snapshot,
            "knowledge_count": knowledge_count,
        },
    )


@app.get(
    "/projects/{project_id}/tasks/new",
    response_class=HTMLResponse,
)
def new_task_page(
    request: Request,
    project_id: int,
):
    conn = get_connection()

    project = conn.execute(
        """
        SELECT *
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    ).fetchone()

    if not project:
        conn.close()
        return RedirectResponse(
            "/projects",
            status_code=303,
        )

    workspaces = conn.execute(
        """
        SELECT *
        FROM workspaces
        WHERE project_id = ?
        ORDER BY name
        """,
        (project_id,),
    ).fetchall()

    parent_tasks = conn.execute(
        """
        SELECT
            id,
            title
        FROM tasks
        WHERE project_id = ?
        ORDER BY id DESC
        """,
        (project_id,),
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="task_new.html",
        context={
            "project": project,
            "workspaces": workspaces,
            "parent_tasks": parent_tasks,
        },
    )


@app.post("/projects/{project_id}/tasks")
def create_task(
    project_id: int,
    task_type: str = Form("standard"),
    title: str = Form(...),
    objective: str = Form(""),
    workspace_id: str = Form(""),
    parent_task_id: str = Form(""),
    external_system: str = Form(""),
    external_id: str = Form(""),
    external_url: str = Form(""),
):
    conn = get_connection()

    project = conn.execute(
        """
        SELECT id
        FROM projects
        WHERE id = ?
        """,
        (project_id,),
    ).fetchone()

    if not project:
        conn.close()

        return RedirectResponse(
            "/projects",
            status_code=303,
        )

    workspace_value = (
        int(workspace_id)
        if workspace_id.strip()
        else None
    )

    parent_value = (
        int(parent_task_id)
        if parent_task_id.strip()
        else None
    )

    cursor = conn.execute(
        """
        INSERT INTO tasks (
            project_id,
            parent_task_id,
            workspace_id,
            task_type,
            title,
            objective,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'queued')
        """,
        (
            project_id,
            parent_value,
            workspace_value,
            task_type,
            title.strip(),
            objective.strip(),
        ),
    )

    task_id = cursor.lastrowid

    if (
        external_system.strip()
        or external_id.strip()
        or external_url.strip()
    ):
        conn.execute(
            """
            INSERT INTO task_external_references (
                task_id,
                external_system,
                external_id,
                external_url
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                task_id,
                external_system.strip() or "external",
                external_id.strip() or None,
                external_url.strip() or None,
            ),
        )

    conn.execute(
        """
        INSERT INTO conversations (
            task_id,
            title,
            status
        )
        VALUES (?, ?, 'active')
        """,
        (
            task_id,
            title.strip(),
        ),
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        f"/tasks/{task_id}",
        status_code=303,
    )


@app.get(
    "/tasks/{task_id}",
    response_class=HTMLResponse,
)
def task_detail(
    request: Request,
    task_id: int,
):
    conn = get_connection()

    task = conn.execute(
        """
        SELECT
            tasks.*,
            projects.name AS project_name,
            workspaces.name AS workspace_name,
            agents.name AS agent_name,
            models.name AS model_name
        FROM tasks
        JOIN projects
            ON projects.id = tasks.project_id
        LEFT JOIN workspaces
            ON workspaces.id = tasks.workspace_id
        LEFT JOIN agents
            ON agents.id = tasks.agent_id
        LEFT JOIN models
            ON models.id = tasks.model_id
        WHERE tasks.id = ?
        """,
        (task_id,),
    ).fetchone()

    if not task:
        conn.close()
        return RedirectResponse(
            "/projects",
            status_code=303,
        )

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
        messages = conn.execute(
            """
            SELECT *
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id
            """,
            (conversation["id"],),
        ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="task_detail.html",
        context={
            "task": task,
            "conversation": conversation,
            "messages": messages,
        },
    )


@app.post("/tasks/{task_id}/messages")
def create_message(
    task_id: int,
    content: str = Form(...),
):
    content = content.strip()

    if not content:
        return RedirectResponse(
            f"/tasks/{task_id}",
            status_code=303,
        )

    conn = get_connection()

    conversation = conn.execute(
        """
        SELECT conversations.id
        FROM conversations
        JOIN tasks
            ON tasks.id = conversations.task_id
        WHERE tasks.id = ?
        ORDER BY conversations.id
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()

    if not conversation:
        conn.close()

        return RedirectResponse(
            f"/tasks/{task_id}",
            status_code=303,
        )

    conn.execute(
        """
        INSERT INTO messages (
            conversation_id,
            role,
            content
        )
        VALUES (?, 'user', ?)
        """,
        (
            conversation["id"],
            content,
        ),
    )

    conn.execute(
        """
        UPDATE conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (conversation["id"],),
    )

    conn.execute(
        """
        UPDATE tasks
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (task_id,),
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        f"/tasks/{task_id}",
        status_code=303,
    )


@app.get("/api/tasks/{task_id}/context")
def task_context(task_id: int):
    return build_task_context(task_id)


@app.get("/api/knowledge/appian/search")
def appian_knowledge_search(
    q: str,
    limit: int = 5,
):
    return {
        "query": q,
        "source": "Appian Documentation",
        "version": "26.8",
        "results": search_appian_docs(
            query=q,
            limit=limit,
        ),
    }


@app.get("/api/projects/{project_id}/knowledge/search")
def project_knowledge_search(
    project_id: int,
    q: str,
    limit: int = 5,
):
    return {
        "query": q,
        "source": "Project Knowledge",
        "project_id": project_id,
        "results": search_project_knowledge(
            project_id=project_id,
            query=q,
            limit=limit,
        ),
    }


@app.get("/api/tasks/{task_id}/workspace/search")
def task_workspace_search(
    task_id: int,
    q: str,
    limit: int = 10,
):
    return {
        "query": q,
        "results": search_workspace(
            task_id=task_id,
            query=q,
            limit=limit,
        ),
    }


@app.get("/api/tasks/{task_id}/workspace/file")
def task_workspace_file(
    task_id: int,
    path: str,
):
    return read_workspace_file(
        task_id=task_id,
        relative_path=path,
    )


@app.get("/api/tasks/{task_id}/workspace/status")
def task_workspace_status(task_id: int):
    return workspace_status(task_id)


@app.get("/api/tasks/{task_id}/workspace/diff")
def task_workspace_diff(task_id: int):
    return workspace_diff(task_id)


@app.get("/api/tasks/{task_id}/workspace/changeset")
def task_workspace_changeset(task_id: int):
    return workspace_changeset(task_id)
