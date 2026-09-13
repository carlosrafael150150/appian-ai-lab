from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from db import get_connection, init_db

app = FastAPI(title="Appian AI Lab")
templates = Jinja2Templates(directory="templates")

init_db()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    conn = get_connection()

    counts = {}

    for table in [
        "projects",
        "workspaces",
        "agents",
        "models",
        "compute_profiles",
        "skills",
        "mcp_servers",
        "knowledge_sources",
        "connections",
        "tasks",
    ]:
        counts[table] = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

    tasks = conn.execute("""
        SELECT
            tasks.id,
            tasks.title,
            tasks.status,
            projects.name AS project_name
        FROM tasks
        LEFT JOIN projects ON projects.id = tasks.project_id
        ORDER BY tasks.id DESC
        LIMIT 10
    """).fetchall()

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
        "SELECT * FROM projects ORDER BY name"
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context={
            "projects": projects,
        },
    )


@app.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(request: Request, project_id: int):
    conn = get_connection()

    project = conn.execute(
        "SELECT * FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()

    if not project:
        conn.close()
        return RedirectResponse("/projects", status_code=303)

    workspaces = conn.execute(
        """
        SELECT *
        FROM workspaces
        WHERE project_id = ?
        ORDER BY id
        """,
        (project_id,),
    ).fetchall()

    tasks = conn.execute(
        """
        SELECT *
        FROM tasks
        WHERE project_id = ?
        ORDER BY id DESC
        """,
        (project_id,),
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="project_detail.html",
        context={
            "project": project,
            "workspaces": workspaces,
            "tasks": tasks,
        },
    )


@app.post("/projects")
def create_project(
    name: str = Form(...),
    description: str = Form(""),
    repository: str = Form(""),
    local_path: str = Form(""),
):
    local_path = local_path.strip()

    if local_path:
        path = Path(local_path).expanduser()

        if not path.exists() or not path.is_dir():
            return RedirectResponse(
                "/projects?error=invalid_path",
                status_code=303,
            )

    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO projects (name, description, repository)
        VALUES (?, ?, ?)
        """,
        (
            name.strip(),
            description.strip(),
            repository.strip(),
        ),
    )

    project_id = cursor.lastrowid

    if local_path:
        conn.execute(
            """
            INSERT INTO workspaces
                (project_id, name, path, branch, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                "main",
                str(Path(local_path).expanduser().resolve()),
                "main",
                "idle",
            ),
        )

    conn.commit()
    conn.close()

    return RedirectResponse(
        f"/projects/{project_id}",
        status_code=303,
    )
