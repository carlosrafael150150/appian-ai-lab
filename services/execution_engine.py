from db import get_connection
from services.context_builder import build_task_context


ACTIVE_EXECUTION_STATUSES = {
    "preparing",
    "running",
    "waiting_for_user",
    "waiting_for_approval",
    "reviewing",
    "testing",
}


def get_scheduler_settings(conn):
    settings = conn.execute(
        """
        SELECT *
        FROM scheduler_settings
        WHERE id = 1
        """
    ).fetchone()

    if not settings:
        raise RuntimeError(
            "Scheduler settings are not configured"
        )

    return settings


def count_active_executions(conn):
    placeholders = ",".join(
        "?" for _ in ACTIVE_EXECUTION_STATUSES
    )

    return conn.execute(
        f"""
        SELECT COUNT(*)
        FROM executions
        WHERE status IN ({placeholders})
        """,
        tuple(ACTIVE_EXECUTION_STATUSES),
    ).fetchone()[0]


def count_compute_executions(
    conn,
    compute_profile_id: int,
):
    placeholders = ",".join(
        "?" for _ in ACTIVE_EXECUTION_STATUSES
    )

    return conn.execute(
        f"""
        SELECT COUNT(*)
        FROM executions
        WHERE compute_profile_id = ?
          AND status IN ({placeholders})
        """,
        (
            compute_profile_id,
            *ACTIVE_EXECUTION_STATUSES,
        ),
    ).fetchone()[0]


def count_deployment_executions(
    conn,
    model_deployment_id: int,
):
    placeholders = ",".join(
        "?" for _ in ACTIVE_EXECUTION_STATUSES
    )

    return conn.execute(
        f"""
        SELECT COUNT(*)
        FROM executions
        WHERE model_deployment_id = ?
          AND status IN ({placeholders})
        """,
        (
            model_deployment_id,
            *ACTIVE_EXECUTION_STATUSES,
        ),
    ).fetchone()[0]


def find_available_deployments(
    conn,
    model_id: int,
    preferred_compute_profile_id=None,
):
    query = """
        SELECT
            model_deployments.id,
            model_deployments.name,
            model_deployments.model_id,
            model_deployments.compute_profile_id,
            model_deployments.endpoint,
            model_deployments.status,
            model_deployments.max_concurrent_executions
                AS deployment_max_concurrent,
            compute_profiles.name AS compute_name,
            compute_profiles.provider AS compute_provider,
            compute_profiles.gpu_type,
            compute_profiles.gpu_memory_gb,
            compute_profiles.status AS compute_status,
            compute_profiles.max_concurrent_executions
                AS compute_max_concurrent
        FROM model_deployments
        JOIN compute_profiles
            ON compute_profiles.id =
               model_deployments.compute_profile_id
        WHERE model_deployments.model_id = ?
          AND model_deployments.enabled = 1
          AND compute_profiles.enabled = 1
          AND model_deployments.status = 'online'
          AND compute_profiles.status = 'online'
    """

    parameters = [model_id]

    if preferred_compute_profile_id is not None:
        query += """
          AND compute_profiles.id = ?
        """
        parameters.append(
            preferred_compute_profile_id
        )

    query += """
        ORDER BY model_deployments.id
    """

    rows = conn.execute(
        query,
        parameters,
    ).fetchall()

    available = []

    for row in rows:
        compute_active = count_compute_executions(
            conn,
            row["compute_profile_id"],
        )

        deployment_active = (
            count_deployment_executions(
                conn,
                row["id"],
            )
        )

        compute_has_capacity = (
            compute_active
            < row["compute_max_concurrent"]
        )

        deployment_limit = row[
            "deployment_max_concurrent"
        ]

        deployment_has_capacity = (
            deployment_limit is None
            or deployment_active
            < deployment_limit
        )

        if (
            compute_has_capacity
            and deployment_has_capacity
        ):
            deployment = dict(row)
            deployment["compute_active"] = (
                compute_active
            )
            deployment["deployment_active"] = (
                deployment_active
            )

            available.append(deployment)

    return available


def check_task_readiness(task_id: int):
    conn = get_connection()

    task = conn.execute(
        """
        SELECT
            tasks.*,
            projects.name AS project_name,
            workspaces.name AS workspace_name,
            agents.name AS agent_name,
            models.name AS model_name,
            preferred_compute.name
                AS preferred_compute_name
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
        raise ValueError(
            f"Task {task_id} not found"
        )

    placeholders = ",".join(
        "?" for _ in ACTIVE_EXECUTION_STATUSES
    )

    active_execution = conn.execute(
        f"""
        SELECT id, status
        FROM executions
        WHERE task_id = ?
          AND status IN ({placeholders})
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            task_id,
            *ACTIVE_EXECUTION_STATUSES,
        ),
    ).fetchone()

    dependencies = conn.execute(
        """
        SELECT
            dependency.depends_on_task_id,
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

    scheduler = get_scheduler_settings(conn)

    global_active = count_active_executions(conn)

    global_capacity_available = (
        global_active
        < scheduler["max_parallel_executions"]
    )

    available_deployments = []

    if task["model_id"] is not None:
        available_deployments = (
            find_available_deployments(
                conn,
                model_id=task["model_id"],
                preferred_compute_profile_id=task[
                    "preferred_compute_profile_id"
                ],
            )
        )

    conn.close()

    checks = []
    blockers = []

    def add_check(
        name,
        ready,
        reason=None,
    ):
        checks.append(
            {
                "name": name,
                "ready": ready,
                "reason": reason,
            }
        )

        if not ready and reason:
            blockers.append(reason)

    add_check(
        "task_status",
        task["status"] not in {
            "completed",
            "cancelled",
        },
        (
            None
            if task["status"] not in {
                "completed",
                "cancelled",
            }
            else (
                f"Task status is "
                f"{task['status']}"
            )
        ),
    )

    add_check(
        "workspace",
        task["workspace_id"] is not None,
        (
            None
            if task["workspace_id"] is not None
            else "No workspace assigned"
        ),
    )

    add_check(
        "agent",
        task["agent_id"] is not None,
        (
            None
            if task["agent_id"] is not None
            else "No agent assigned"
        ),
    )

    add_check(
        "model",
        task["model_id"] is not None,
        (
            None
            if task["model_id"] is not None
            else "No model assigned"
        ),
    )

    add_check(
        "single_active_execution",
        active_execution is None,
        (
            None
            if active_execution is None
            else (
                "Task already has active "
                f"execution #{active_execution['id']}"
            )
        ),
    )

    blocked_dependencies = [
        {
            "id": dependency[
                "depends_on_task_id"
            ],
            "title": dependency["title"],
            "status": dependency["status"],
        }
        for dependency in dependencies
        if dependency["status"] != "completed"
    ]

    add_check(
        "dependencies",
        len(blocked_dependencies) == 0,
        (
            None
            if not blocked_dependencies
            else (
                "One or more task "
                "dependencies are incomplete"
            )
        ),
    )

    add_check(
        "scheduler_capacity",
        global_capacity_available,
        (
            None
            if global_capacity_available
            else (
                "Global scheduler concurrency "
                "limit has been reached"
            )
        ),
    )

    deployment_available = (
        len(available_deployments) > 0
    )

    if task["model_id"] is None:
        deployment_reason = (
            "No model assigned"
        )

    elif (
        task["preferred_compute_profile_id"]
        is not None
    ):
        deployment_reason = (
            "No online compatible deployment "
            "with available capacity exists on "
            "the preferred compute resource"
        )

    else:
        deployment_reason = (
            "No online compatible model "
            "deployment with available "
            "capacity exists"
        )

    add_check(
        "model_deployment",
        deployment_available,
        (
            None
            if deployment_available
            else deployment_reason
        ),
    )

    selected_candidate = (
        available_deployments[0]
        if available_deployments
        else None
    )

    return {
        "task_id": task_id,
        "project": task["project_name"],
        "task": task["title"],
        "ready": len(blockers) == 0,
        "checks": checks,
        "blockers": blockers,
        "blocked_dependencies": (
            blocked_dependencies
        ),
        "assignment": {
            "workspace": task["workspace_name"],
            "agent": task["agent_name"],
            "model": task["model_name"],
            "preferred_compute": task[
                "preferred_compute_name"
            ],
        },
        "scheduler": {
            "policy": scheduler[
                "scheduling_policy"
            ],
            "max_parallel_executions": (
                scheduler[
                    "max_parallel_executions"
                ]
            ),
            "active_executions": global_active,
        },
        "selected_candidate": (
            {
                "deployment_id": (
                    selected_candidate["id"]
                ),
                "deployment": (
                    selected_candidate["name"]
                ),
                "compute_profile_id": (
                    selected_candidate[
                        "compute_profile_id"
                    ]
                ),
                "compute": (
                    selected_candidate[
                        "compute_name"
                    ]
                ),
                "endpoint": (
                    selected_candidate["endpoint"]
                ),
            }
            if selected_candidate
            else None
        ),
    }


def create_execution(task_id: int):
    readiness = check_task_readiness(
        task_id
    )

    if not readiness["ready"]:
        return {
            "created": False,
            "reason": "task_not_ready",
            "readiness": readiness,
        }

    candidate = readiness[
        "selected_candidate"
    ]

    context = build_task_context(task_id)

    conn = get_connection()

    task = conn.execute(
        """
        SELECT
            id,
            agent_id,
            model_id
        FROM tasks
        WHERE id = ?
        """,
        (task_id,),
    ).fetchone()

    conversation = conn.execute(
        """
        SELECT id
        FROM conversations
        WHERE task_id = ?
        ORDER BY id
        LIMIT 1
        """,
        (task_id,),
    ).fetchone()

    cursor = conn.execute(
        """
        INSERT INTO executions (
            task_id,
            conversation_id,
            agent_id,
            model_id,
            compute_profile_id,
            model_deployment_id,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'preparing')
        """,
        (
            task_id,
            (
                conversation["id"]
                if conversation
                else None
            ),
            task["agent_id"],
            task["model_id"],
            candidate["compute_profile_id"],
            candidate["deployment_id"],
        ),
    )

    execution_id = cursor.lastrowid

    conn.execute(
        """
        INSERT INTO execution_events (
            execution_id,
            event_type,
            message
        )
        VALUES (?, 'EXECUTION_CREATED', ?)
        """,
        (
            execution_id,
            (
                "Execution created using "
                f"deployment "
                f"{candidate['deployment']}"
            ),
        ),
    )

    conn.execute(
        """
        UPDATE tasks
        SET
            status = 'running',
            started_at = COALESCE(
                started_at,
                CURRENT_TIMESTAMP
            ),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (task_id,),
    )

    conn.commit()
    conn.close()

    return {
        "created": True,
        "execution_id": execution_id,
        "status": "preparing",
        "deployment": candidate,
        "context": context,
    }
