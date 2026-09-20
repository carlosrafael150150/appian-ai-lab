import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "lab.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def init_db():
    conn = get_connection()

    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            provider TEXT,
            remote_url TEXT,
            local_path TEXT,
            default_branch TEXT DEFAULT 'main',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, name),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS environments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            name TEXT NOT NULL,
            environment_type TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'available',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, name),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            repository_id INTEGER,
            environment_id INTEGER,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            branch TEXT,
            status TEXT NOT NULL DEFAULT 'idle',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, name),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(repository_id) REFERENCES repositories(id) ON DELETE SET NULL,
            FOREIGN KEY(environment_id) REFERENCES environments(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            system_instructions TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            provider TEXT,
            model_id TEXT NOT NULL,
            description TEXT,
            configuration_json TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS compute_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            provider TEXT NOT NULL,
            resource_type TEXT,
            gpu_type TEXT,
            gpu_memory_gb REAL,
            status TEXT NOT NULL DEFAULT 'offline',
            max_concurrent_executions INTEGER NOT NULL DEFAULT 1,
            configuration_json TEXT,
            secret_ref TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS model_deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            model_id INTEGER NOT NULL,
            compute_profile_id INTEGER NOT NULL,
            endpoint TEXT,
            status TEXT NOT NULL DEFAULT 'offline',
            max_concurrent_executions INTEGER,
            configuration_json TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(model_id)
                REFERENCES models(id)
                ON DELETE CASCADE,
            FOREIGN KEY(compute_profile_id)
                REFERENCES compute_profiles(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            instructions TEXT,
            version TEXT,
            scope TEXT NOT NULL DEFAULT 'global',
            project_id INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS playbooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            instructions TEXT,
            version TEXT,
            scope TEXT NOT NULL DEFAULT 'global',
            project_id INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS mcp_servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            server_url TEXT,
            transport TEXT,
            configuration_json TEXT,
            scope TEXT NOT NULL DEFAULT 'global',
            project_id INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            connection_type TEXT NOT NULL,
            description TEXT,
            configuration_json TEXT,
            secret_ref TEXT,
            scope TEXT NOT NULL DEFAULT 'global',
            project_id INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            secret_ref TEXT NOT NULL UNIQUE,
            provider TEXT,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            policy_json TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'global',
            project_id INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            parent_task_id INTEGER,
            workspace_id INTEGER,
            environment_id INTEGER,
            agent_id INTEGER,
            model_id INTEGER,
            preferred_compute_profile_id INTEGER,
            task_type TEXT NOT NULL DEFAULT 'standard',
            title TEXT NOT NULL,
            objective TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            completed_at TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(parent_task_id) REFERENCES tasks(id) ON DELETE SET NULL,
            FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL,
            FOREIGN KEY(environment_id) REFERENCES environments(id) ON DELETE SET NULL,
            FOREIGN KEY(agent_id) REFERENCES agents(id) ON DELETE SET NULL,
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE SET NULL,
            FOREIGN KEY(preferred_compute_profile_id) REFERENCES compute_profiles(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS task_external_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            external_system TEXT NOT NULL,
            external_id TEXT,
            external_url TEXT,
            external_type TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(task_id, external_system, external_id),
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS task_dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            depends_on_task_id INTEGER NOT NULL,
            dependency_type TEXT NOT NULL DEFAULT 'blocks',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(task_id, depends_on_task_id),
            CHECK(task_id <> depends_on_task_id),
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(depends_on_task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            agent_id INTEGER,
            model_id INTEGER,
            content TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(agent_id) REFERENCES agents(id) ON DELETE SET NULL,
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            conversation_id INTEGER,
            agent_id INTEGER,
            model_id INTEGER,
            compute_profile_id INTEGER,
            model_deployment_id INTEGER,
            status TEXT NOT NULL DEFAULT 'running',
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            result_summary TEXT,
            error_message TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE SET NULL,
            FOREIGN KEY(agent_id) REFERENCES agents(id) ON DELETE SET NULL,
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE SET NULL,
            FOREIGN KEY(compute_profile_id) REFERENCES compute_profiles(id) ON DELETE SET NULL,
            FOREIGN KEY(model_deployment_id) REFERENCES model_deployments(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS execution_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT,
            tool_name TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            execution_id INTEGER,
            artifact_type TEXT NOT NULL,
            name TEXT NOT NULL,
            path TEXT,
            uri TEXT,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            execution_id INTEGER,
            review_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            requested_reason TEXT,
            decision_comment TEXT,
            decided_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            source_type TEXT NOT NULL,
            location TEXT,
            version TEXT,
            description TEXT,
            scope TEXT NOT NULL DEFAULT 'global',
            project_id INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS knowledge_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            knowledge_type TEXT NOT NULL,
            title TEXT NOT NULL,
            current_status TEXT NOT NULL DEFAULT 'proposed',
            confidence REAL,
            current_version_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS knowledge_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_item_id INTEGER NOT NULL,
            version_number INTEGER NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'current',
            source_type TEXT,
            source_reference TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(knowledge_item_id, version_number),
            FOREIGN KEY(knowledge_item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS knowledge_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_version_id INTEGER NOT NULL,
            evidence_type TEXT NOT NULL,
            reference TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(knowledge_version_id) REFERENCES knowledge_versions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS knowledge_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            task_id INTEGER,
            knowledge_item_id INTEGER,
            proposal_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            confidence REAL,
            status TEXT NOT NULL DEFAULT 'proposed',
            proposed_by TEXT NOT NULL DEFAULT 'agent',
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL,
            FOREIGN KEY(knowledge_item_id) REFERENCES knowledge_items(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS project_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL UNIQUE,
            version INTEGER NOT NULL DEFAULT 1,
            summary TEXT,
            functional_model TEXT,
            architecture TEXT,
            current_decisions TEXT,
            constraints TEXT,
            known_issues TEXT,
            roadmap TEXT,
            generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        ------------------------------------------------------------
        -- SCHEDULER
        ------------------------------------------------------------

        CREATE TABLE IF NOT EXISTS scheduler_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            max_parallel_executions INTEGER NOT NULL DEFAULT 1,
            scheduling_policy TEXT NOT NULL DEFAULT 'first_available',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT OR IGNORE INTO scheduler_settings (
            id,
            max_parallel_executions,
            scheduling_policy
        )
        VALUES (
            1,
            1,
            'first_available'
        );

        CREATE TABLE IF NOT EXISTS automations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            name TEXT NOT NULL UNIQUE,
            trigger_type TEXT NOT NULL,
            trigger_config_json TEXT,
            action_config_json TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            task_id INTEGER,
            execution_id INTEGER,
            model_id INTEGER,
            compute_profile_id INTEGER,
            event_type TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            gpu_seconds REAL DEFAULT 0,
            estimated_cost REAL DEFAULT 0,
            metadata_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL,
            FOREIGN KEY(execution_id) REFERENCES executions(id) ON DELETE SET NULL,
            FOREIGN KEY(model_id) REFERENCES models(id) ON DELETE SET NULL,
            FOREIGN KEY(compute_profile_id) REFERENCES compute_profiles(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            name TEXT NOT NULL,
            period TEXT NOT NULL,
            max_cost REAL,
            max_gpu_seconds REAL,
            max_tokens INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, name),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT,
            email TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS project_memberships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, user_id),
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_model_deployments_model
            ON model_deployments(model_id);

        CREATE INDEX IF NOT EXISTS idx_model_deployments_compute
            ON model_deployments(compute_profile_id);

        CREATE INDEX IF NOT EXISTS idx_model_deployments_status
            ON model_deployments(status);

        CREATE INDEX IF NOT EXISTS idx_tasks_project
            ON tasks(project_id);

        CREATE INDEX IF NOT EXISTS idx_tasks_parent
            ON tasks(parent_task_id);

        CREATE INDEX IF NOT EXISTS idx_tasks_status
            ON tasks(status);

        CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id);

        CREATE INDEX IF NOT EXISTS idx_executions_task
            ON executions(task_id);

        CREATE INDEX IF NOT EXISTS idx_execution_events_execution
            ON execution_events(execution_id);

        CREATE INDEX IF NOT EXISTS idx_knowledge_project
            ON knowledge_items(project_id);

        CREATE INDEX IF NOT EXISTS idx_knowledge_proposals_project
            ON knowledge_proposals(project_id);

        CREATE INDEX IF NOT EXISTS idx_usage_project
            ON usage_events(project_id);

        CREATE INDEX IF NOT EXISTS idx_usage_task
            ON usage_events(task_id);
        """
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DB_PATH}")
