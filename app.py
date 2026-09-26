from pathlib import Path
import subprocess

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from db import get_connection, init_db
from services.context_builder import build_task_context
from services.knowledge_tools import search_appian_docs, search_project_knowledge
from services.workspace_tools import search_workspace, read_workspace_file, workspace_status, workspace_diff, workspace_changeset
from services.execution_engine import check_task_readiness, create_execution


app = FastAPI(title="Appian AI Lab")
templates = Jinja2Templates(directory="templates")

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)

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
            "active_page": "dashboard",
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
            "active_page": "projects",
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
            "active_page": "projects"
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

    agents = conn.execute(
        """
        SELECT *
        FROM agents
        WHERE enabled = 1
        ORDER BY name
        """
    ).fetchall()

    models = conn.execute(
        """
        SELECT *
        FROM models
        WHERE enabled = 1
        ORDER BY name
        """
    ).fetchall()

    compute_profiles = conn.execute(
        """
        SELECT *
        FROM compute_profiles
        WHERE enabled = 1
        ORDER BY name
        """
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="task_new.html",
        context={
            "project": project,
            "workspaces": workspaces,
            "parent_tasks": parent_tasks,
            "agents": agents,
            "models": models,
            "compute_profiles": compute_profiles,
            "active_page": "projects",
        },
    )


@app.post("/projects/{project_id}/tasks")
def create_task(
    project_id: int,
    task_type: str = Form("standard"),
    title: str = Form(...),
    objective: str = Form(""),
    workspace_id: str = Form(""),
    agent_id: str = Form(""),
    model_id: str = Form(""),
    preferred_compute_profile_id: str = Form(""),
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

    agent_value = (
        int(agent_id)
        if agent_id.strip()
        else None
    )

    model_value = (
        int(model_id)
        if model_id.strip()
        else None
    )

    preferred_compute_value = (
        int(preferred_compute_profile_id)
        if preferred_compute_profile_id.strip()
        else None
    )

    cursor = conn.execute(
        """
        INSERT INTO tasks (
            project_id,
            parent_task_id,
            workspace_id,
            agent_id,
            model_id,
            preferred_compute_profile_id,
            task_type,
            title,
            objective,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')
        """,
        (
            project_id,
            parent_value,
            workspace_value,
            agent_value,
            model_value,
            preferred_compute_value,
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
            models.name AS model_name,
            preferred_compute.name AS preferred_compute_name
        FROM tasks
        JOIN projects
            ON projects.id = tasks.project_id
        LEFT JOIN workspaces
            ON workspaces.id = tasks.workspace_id
        LEFT JOIN agents
            ON agents.id = tasks.agent_id
        LEFT JOIN models
            ON models.id = tasks.model_id
        LEFT JOIN compute_profiles AS preferred_compute
            ON preferred_compute.id =
               tasks.preferred_compute_profile_id
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
            "active_page": "projects"
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


@app.get("/api/tasks/{task_id}/readiness")
def task_readiness(task_id: int):
    return check_task_readiness(task_id)


@app.post("/api/tasks/{task_id}/executions")
def start_task_execution(task_id: int):
    return create_execution(task_id)

@app.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request):
    conn = get_connection()

    agents = conn.execute(
        """
        SELECT *
        FROM agents
        ORDER BY name
        """
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="agents.html",
        context={
            "agents": agents,
            "active_page": "agents",
        },
    )


@app.get("/agents/new", response_class=HTMLResponse)
def new_agent_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="agent_new.html",
        context={
            "active_page": "agents",
        },
    )


@app.post("/agents")
def create_agent(
    name: str = Form(...),
    description: str = Form(""),
    system_instructions: str = Form(""),
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO agents (
            name,
            description,
            system_instructions,
            enabled
        )
        VALUES (?, ?, ?, 1)
        """,
        (
            name.strip(),
            description.strip(),
            system_instructions.strip(),
        ),
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/agents",
        status_code=303,
    )

@app.get("/models", response_class=HTMLResponse)
def models_page(request: Request):
    conn = get_connection()

    models = conn.execute(
        """
        SELECT
            models.*,
            COUNT(model_deployments.id)
                AS deployment_count
        FROM models
        LEFT JOIN model_deployments
            ON model_deployments.model_id = models.id
        GROUP BY models.id
        ORDER BY models.name
        """
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="models.html",
        context={
            "models": models,
            "active_page": "models",
        },
    )


@app.get("/models/new", response_class=HTMLResponse)
def new_model_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="model_new.html",
        context={
            "active_page": "models",
        },
    )


@app.post("/models")
def create_model(
    name: str = Form(...),
    provider: str = Form(""),
    model_id: str = Form(...),
    description: str = Form(""),
    configuration_json: str = Form(""),
):
    configuration = (
        configuration_json.strip()
        if configuration_json.strip()
        else None
    )

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO models (
            name,
            provider,
            model_id,
            description,
            configuration_json,
            enabled
        )
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (
            name.strip(),
            provider.strip() or None,
            model_id.strip(),
            description.strip() or None,
            configuration,
        ),
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/models",
        status_code=303,
    )

@app.get("/compute", response_class=HTMLResponse)
def compute_page(request: Request):
    conn = get_connection()

    compute_profiles = conn.execute(
        """
        SELECT
            compute_profiles.*,

            COUNT(
                DISTINCT model_deployments.id
            ) AS deployment_count,

            COUNT(
                DISTINCT CASE
                    WHEN executions.status IN (
                        'preparing',
                        'running',
                        'waiting_for_user',
                        'waiting_for_approval',
                        'reviewing',
                        'testing'
                    )
                    THEN executions.id
                END
            ) AS active_executions

        FROM compute_profiles

        LEFT JOIN model_deployments
            ON model_deployments.compute_profile_id =
               compute_profiles.id

        LEFT JOIN executions
            ON executions.compute_profile_id =
               compute_profiles.id

        GROUP BY compute_profiles.id

        ORDER BY compute_profiles.name
        """
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="compute.html",
        context={
            "compute_profiles": compute_profiles,
            "active_page": "compute",
        },
    )


@app.get("/compute/new", response_class=HTMLResponse)
def new_compute_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="compute_new.html",
        context={
            "active_page": "compute",
        },
    )


@app.post("/compute")
def create_compute(
    name: str = Form(...),
    provider: str = Form(...),
    resource_type: str = Form("gpu"),
    gpu_type: str = Form(""),
    gpu_memory_gb: str = Form(""),
    max_concurrent_executions: int = Form(1),
    configuration_json: str = Form(""),
    secret_ref: str = Form(""),
):
    gpu_memory = (
        float(gpu_memory_gb)
        if gpu_memory_gb.strip()
        else None
    )

    configuration = (
        configuration_json.strip()
        if configuration_json.strip()
        else None
    )

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO compute_profiles (
            name,
            provider,
            resource_type,
            gpu_type,
            gpu_memory_gb,
            status,
            max_concurrent_executions,
            configuration_json,
            secret_ref,
            enabled
        )
        VALUES (?, ?, ?, ?, ?, 'offline', ?, ?, ?, 1)
        """,
        (
            name.strip(),
            provider.strip(),
            resource_type.strip() or None,
            gpu_type.strip() or None,
            gpu_memory,
            max_concurrent_executions,
            configuration,
            secret_ref.strip() or None,
        ),
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/compute",
        status_code=303,
    )

@app.get("/deployments", response_class=HTMLResponse)
def deployments_page(request: Request):
    conn = get_connection()

    deployments = conn.execute(
        """
        SELECT
            model_deployments.*,
            models.name AS model_name,
            compute_profiles.name AS compute_name,

            COUNT(
                DISTINCT CASE
                    WHEN executions.status IN (
                        'preparing',
                        'running',
                        'waiting_for_user',
                        'waiting_for_approval',
                        'reviewing',
                        'testing'
                    )
                    THEN executions.id
                END
            ) AS active_executions

        FROM model_deployments

        JOIN models
            ON models.id =
               model_deployments.model_id

        JOIN compute_profiles
            ON compute_profiles.id =
               model_deployments.compute_profile_id

        LEFT JOIN executions
            ON executions.model_deployment_id =
               model_deployments.id

        GROUP BY model_deployments.id

        ORDER BY model_deployments.name
        """
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="deployments.html",
        context={
            "deployments": deployments,
            "active_page": "deployments",
        },
    )


@app.get(
    "/deployments/new",
    response_class=HTMLResponse,
)
def new_deployment_page(request: Request):
    conn = get_connection()

    models = conn.execute(
        """
        SELECT *
        FROM models
        WHERE enabled = 1
        ORDER BY name
        """
    ).fetchall()

    compute_profiles = conn.execute(
        """
        SELECT *
        FROM compute_profiles
        WHERE enabled = 1
        ORDER BY name
        """
    ).fetchall()

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="deployment_new.html",
        context={
            "models": models,
            "compute_profiles": compute_profiles,
            "active_page": "deployments",
        },
    )


@app.post("/deployments")
def create_deployment(
    name: str = Form(...),
    model_id: int = Form(...),
    compute_profile_id: int = Form(...),
    endpoint: str = Form(""),
    max_concurrent_executions: str = Form(""),
    configuration_json: str = Form(""),
):
    concurrency = (
        int(max_concurrent_executions)
        if max_concurrent_executions.strip()
        else None
    )

    configuration = (
        configuration_json.strip()
        if configuration_json.strip()
        else None
    )

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO model_deployments (
            name,
            model_id,
            compute_profile_id,
            endpoint,
            status,
            max_concurrent_executions,
            configuration_json,
            enabled
        )
        VALUES (?, ?, ?, ?, 'offline', ?, ?, 1)
        """,
        (
            name.strip(),
            model_id,
            compute_profile_id,
            endpoint.strip() or None,
            concurrency,
            configuration,
        ),
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/deployments",
        status_code=303,
    )

@app.get("/scheduler", response_class=HTMLResponse)
def scheduler_page(request: Request):
    conn = get_connection()

    settings = conn.execute(
        """
        SELECT *
        FROM scheduler_settings
        WHERE id = 1
        """
    ).fetchone()

    active_statuses = (
        "preparing",
        "running",
        "waiting_for_user",
        "waiting_for_approval",
        "reviewing",
        "testing",
    )

    placeholders = ",".join(
        "?" for _ in active_statuses
    )

    active_executions = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM executions
        WHERE status IN ({placeholders})
        """,
        active_statuses,
    ).fetchone()[0]

    total_compute = conn.execute(
        """
        SELECT COUNT(*)
        FROM compute_profiles
        WHERE enabled = 1
        """
    ).fetchone()[0]

    online_compute = conn.execute(
        """
        SELECT COUNT(*)
        FROM compute_profiles
        WHERE enabled = 1
          AND status = 'online'
        """
    ).fetchone()[0]

    total_deployments = conn.execute(
        """
        SELECT COUNT(*)
        FROM model_deployments
        WHERE enabled = 1
        """
    ).fetchone()[0]

    online_deployments = conn.execute(
        """
        SELECT COUNT(*)
        FROM model_deployments
        WHERE enabled = 1
          AND status = 'online'
        """
    ).fetchone()[0]

    compute_rows = conn.execute(
        f"""
        SELECT
            compute_profiles.id,
            compute_profiles.name,
            compute_profiles.status,
            compute_profiles.max_concurrent_executions,

            COUNT(
                DISTINCT CASE
                    WHEN executions.status
                        IN ({placeholders})
                    THEN executions.id
                END
            ) AS active_executions

        FROM compute_profiles

        LEFT JOIN executions
            ON executions.compute_profile_id =
               compute_profiles.id

        WHERE compute_profiles.enabled = 1

        GROUP BY compute_profiles.id

        ORDER BY compute_profiles.name
        """,
        active_statuses,
    ).fetchall()

    compute_capacity = []

    infrastructure_slots = 0

    for row in compute_rows:
        row_dict = dict(row)

        if row["status"] == "online":
            available = max(
                0,
                row["max_concurrent_executions"]
                - row["active_executions"],
            )
        else:
            available = 0

        row_dict["available_slots"] = available

        infrastructure_slots += available

        compute_capacity.append(row_dict)

    global_slots = max(
        0,
        settings["max_parallel_executions"]
        - active_executions,
    )

    if online_deployments == 0:
        available_slots = 0
    else:
        available_slots = min(
            global_slots,
            infrastructure_slots,
        )

    capacity = {
        "active_executions": active_executions,
        "total_compute": total_compute,
        "online_compute": online_compute,
        "total_deployments": total_deployments,
        "online_deployments": online_deployments,
        "global_slots": global_slots,
        "available_slots": available_slots,
    }

    conn.close()

    return templates.TemplateResponse(
        request=request,
        name="scheduler.html",
        context={
            "settings": settings,
            "capacity": capacity,
            "compute_capacity": compute_capacity,
            "active_page": "scheduler",
        },
    )


@app.post("/scheduler")
def update_scheduler(
    max_parallel_executions: int = Form(...),
    scheduling_policy: str = Form(
        "first_available"
    ),
):
    if max_parallel_executions < 1:
        max_parallel_executions = 1

    allowed_policies = {
        "first_available",
    }

    if scheduling_policy not in allowed_policies:
        scheduling_policy = "first_available"

    conn = get_connection()

    conn.execute(
        """
        UPDATE scheduler_settings
        SET
            max_parallel_executions = ?,
            scheduling_policy = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
        """,
        (
            max_parallel_executions,
            scheduling_policy,
        ),
    )

    conn.commit()
    conn.close()

    return RedirectResponse(
        "/scheduler",
        status_code=303,
    )
