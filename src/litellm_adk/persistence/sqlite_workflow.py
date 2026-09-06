"""SQLite persistence layer with WAL mode for workflows, executions, and credentials."""

import json
import os
import aiosqlite
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from ..workflow.schema import WorkflowDefinition
from ..workflow.state import ExecutionState, NodeExecutionRecord


DEFAULT_DB_PATH = os.getenv("LITELLM_ADK_DB", "workflows.db")


class SQLiteWorkflowStore:
    """Async SQLite persistence manager with Write-Ahead Logging (WAL)."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._initialized = False

    async def init_db(self) -> None:
        """Initializes database schema and WAL configuration."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA foreign_keys=ON;")
            await db.execute("PRAGMA busy_timeout=5000;")

            await db.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                active INTEGER DEFAULT 0,
                version TEXT DEFAULT '1',
                definition_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS workflow_versions (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                version TEXT NOT NULL,
                definition_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            );
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                workflow_version TEXT NOT NULL,
                status TEXT NOT NULL,
                trigger_data_json TEXT,
                variables_json TEXT,
                state_json TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL DEFAULT 0.0,
                total_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0
            );
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                masked_hint TEXT NOT NULL,
                secret_encrypted TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            await db.commit()
        self._initialized = True


class WorkflowRepository:
    """Repository managing workflow definitions and versions."""

    def __init__(self, store: SQLiteWorkflowStore):
        self.store = store

    async def save(self, workflow: WorkflowDefinition) -> None:
        await self.store.init_db()
        now_str = datetime.now(timezone.utc).isoformat()
        if not workflow.created_at:
            workflow.created_at = now_str
        workflow.updated_at = now_str

        def_json = workflow.model_dump_json()

        async with aiosqlite.connect(self.store.db_path) as db:
            await db.execute("""
            INSERT INTO workflows (id, name, description, active, version, definition_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                active=excluded.active,
                version=excluded.version,
                definition_json=excluded.definition_json,
                updated_at=excluded.updated_at;
            """, (
                workflow.id,
                workflow.name,
                workflow.description,
                1 if workflow.active else 0,
                workflow.version,
                def_json,
                workflow.created_at,
                workflow.updated_at,
            ))

            # Record version history
            ver_id = f"{workflow.id}_v{workflow.version}_{int(datetime.now().timestamp())}"
            await db.execute("""
            INSERT OR REPLACE INTO workflow_versions (id, workflow_id, version, definition_json, created_at)
            VALUES (?, ?, ?, ?, ?);
            """, (ver_id, workflow.id, workflow.version, def_json, now_str))

            await db.commit()

    async def get(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        await self.store.init_db()
        async with aiosqlite.connect(self.store.db_path) as db:
            async with db.execute("SELECT definition_json FROM workflows WHERE id = ?;", (workflow_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return WorkflowDefinition.model_validate_json(row[0])
        return None

    async def list_all(self) -> List[WorkflowDefinition]:
        await self.store.init_db()
        workflows = []
        async with aiosqlite.connect(self.store.db_path) as db:
            async with db.execute("SELECT definition_json FROM workflows ORDER BY updated_at DESC;") as cursor:
                async for row in cursor:
                    workflows.append(WorkflowDefinition.model_validate_json(row[0]))
        return workflows

    async def delete(self, workflow_id: str) -> bool:
        await self.store.init_db()
        async with aiosqlite.connect(self.store.db_path) as db:
            cur = await db.execute("DELETE FROM workflows WHERE id = ?;", (workflow_id,))
            await db.commit()
            return cur.rowcount > 0

    async def set_active(self, workflow_id: str, active: bool) -> bool:
        await self.store.init_db()
        async with aiosqlite.connect(self.store.db_path) as db:
            cur = await db.execute("UPDATE workflows SET active = ?, updated_at = ? WHERE id = ?;", (
                1 if active else 0,
                datetime.now(timezone.utc).isoformat(),
                workflow_id
            ))
            await db.commit()
            return cur.rowcount > 0


class ExecutionRepository:
    """Repository persisting workflow run records and node states."""

    def __init__(self, store: SQLiteWorkflowStore):
        self.store = store

    async def save(self, state: ExecutionState) -> None:
        await self.store.init_db()
        state_json = state.model_dump_json()

        async with aiosqlite.connect(self.store.db_path) as db:
            await db.execute("""
            INSERT INTO executions (
                id, workflow_id, workflow_version, status,
                trigger_data_json, variables_json, state_json,
                started_at, finished_at, duration_seconds, total_tokens, cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                state_json=excluded.state_json,
                finished_at=excluded.finished_at,
                duration_seconds=excluded.duration_seconds,
                total_tokens=excluded.total_tokens,
                cost_usd=excluded.cost_usd;
            """, (
                state.execution_id,
                state.workflow_id,
                state.workflow_version,
                state.status.value,
                json.dumps(state.trigger_data),
                json.dumps(state.variables),
                state_json,
                state.started_at,
                state.finished_at,
                state.total_duration,
                state.total_tokens,
                state.estimated_cost,
            ))
            await db.commit()

    async def get(self, execution_id: str) -> Optional[ExecutionState]:
        await self.store.init_db()
        async with aiosqlite.connect(self.store.db_path) as db:
            async with db.execute("SELECT state_json FROM executions WHERE id = ?;", (execution_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return ExecutionState.model_validate_json(row[0])
        return None

    async def list_all(
        self,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        await self.store.init_db()
        query = "SELECT id, workflow_id, workflow_version, status, started_at, finished_at, duration_seconds, total_tokens, cost_usd FROM executions"
        params = []
        conditions = []
        if workflow_id:
            conditions.append("workflow_id = ?")
            params.append(workflow_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        records = []
        async with aiosqlite.connect(self.store.db_path) as db:
            async with db.execute(query, tuple(params)) as cursor:
                async for row in cursor:
                    records.append({
                        "id": row[0],
                        "workflow_id": row[1],
                        "workflow_version": row[2],
                        "status": row[3],
                        "started_at": row[4],
                        "finished_at": row[5],
                        "duration_seconds": row[6],
                        "total_tokens": row[7],
                        "cost_usd": row[8],
                    })
        return records


class CredentialRepository:
    """Repository storing secrets with masked visibility to frontend clients."""

    def __init__(self, store: SQLiteWorkflowStore):
        self.store = store

    def _mask_secret(self, secret: str) -> str:
        if len(secret) <= 8:
            return "***"
        return f"{secret[:3]}...{secret[-4:]}"

    async def save(self, cred_id: str, name: str, provider: str, secret: str) -> None:
        await self.store.init_db()
        now_str = datetime.now(timezone.utc).isoformat()
        masked = self._mask_secret(secret)

        async with aiosqlite.connect(self.store.db_path) as db:
            await db.execute("""
            INSERT INTO credentials (id, name, provider, masked_hint, secret_encrypted, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                provider=excluded.provider,
                masked_hint=excluded.masked_hint,
                secret_encrypted=excluded.secret_encrypted,
                updated_at=excluded.updated_at;
            """, (cred_id, name, provider, masked, secret, now_str, now_str))
            await db.commit()

    async def get_secret(self, cred_id: str) -> Optional[str]:
        await self.store.init_db()
        async with aiosqlite.connect(self.store.db_path) as db:
            async with db.execute("SELECT secret_encrypted FROM credentials WHERE id = ?;", (cred_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
        return None

    async def list_all(self) -> List[Dict[str, Any]]:
        await self.store.init_db()
        creds = []
        async with aiosqlite.connect(self.store.db_path) as db:
            async with db.execute("SELECT id, name, provider, masked_hint, created_at, updated_at FROM credentials ORDER BY name ASC;") as cursor:
                async for row in cursor:
                    creds.append({
                        "id": row[0],
                        "name": row[1],
                        "provider": row[2],
                        "masked_hint": row[3],
                        "created_at": row[4],
                        "updated_at": row[5],
                    })
        return creds

    async def delete(self, cred_id: str) -> bool:
        await self.store.init_db()
        async with aiosqlite.connect(self.store.db_path) as db:
            cur = await db.execute("DELETE FROM credentials WHERE id = ?;", (cred_id,))
            await db.commit()
            return cur.rowcount > 0


# Default global persistence instance
workflow_store = SQLiteWorkflowStore()
workflow_repository = WorkflowRepository(workflow_store)
execution_repository = ExecutionRepository(workflow_store)
credential_repository = CredentialRepository(workflow_store)
