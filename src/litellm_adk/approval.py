import os
import json
import sqlite3
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from .models import ApprovalRequest, ApprovalStatus, ApprovalAuditEntry
from .observability.logger import adk_logger

class BaseApprovalManager(ABC):
    """Abstract base class for managing tool call approvals."""
    
    @abstractmethod
    def create_request(self, id: str, session_id: str, tool_name: str, args: Dict[str, Any]) -> ApprovalRequest:
        pass
        
    @abstractmethod
    def get_request(self, id: str) -> Optional[ApprovalRequest]:
        pass

    @abstractmethod
    def submit_decision(self, id: str, status: ApprovalStatus, reviewer: str = "human", reason: Optional[str] = None, modified_args: Optional[Dict[str, Any]] = None):
        pass

    def get_effective_args(self, id: str, default_args: Dict[str, Any] = None) -> Dict[str, Any]:  # type: ignore
        """Returns modified args if present, otherwise original (or default)."""
        request = self.get_request(id)
        if not request:
            return default_args or {}
        return request.modified_args if request.modified_args is not None else request.original_args

class InMemoryApprovalManager(BaseApprovalManager):
    """Ephemeral, in-memory approval manager (useful for tests)."""
    def __init__(self):
        self._requests: Dict[str, ApprovalRequest] = {}
        
    def create_request(self, id: str, session_id: str, tool_name: str, args: Dict[str, Any]) -> ApprovalRequest:
        req = ApprovalRequest(id=id, session_id=session_id, tool_name=tool_name, original_args=args)
        self._requests[id] = req
        adk_logger.info(f"AUDIT - HITL: created on {id} by agent")
        return req
        
    def get_request(self, id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(id)
        
    def submit_decision(self, id: str, status: ApprovalStatus, reviewer: str = "human", reason: Optional[str] = None, modified_args: Optional[Dict[str, Any]] = None):
        req = self.get_request(id)
        if not req:
            raise ValueError(f"Approval request {id} not found.")
        req.status = status
        req.reviewer = reviewer
        req.reason = reason
        if modified_args:
            req.modified_args = modified_args
        adk_logger.info(f"AUDIT - HITL: {status.value} on {id} by {reviewer} (reason: {reason})")

class SQLiteApprovalManager(BaseApprovalManager):
    """
    Process-safe, SQLite-backed approval manager.
    Handles concurrent web workers safely.
    """
    def __init__(self, db_path: str = "approvals.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        # SQLite handles file locks at OS level. We use a short timeout to retry if locked.
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    tool_name TEXT,
                    original_args TEXT,
                    modified_args TEXT,
                    status TEXT,
                    requester TEXT,
                    reviewer TEXT,
                    reason TEXT,
                    created_at TEXT
                )
            ''')
            conn.commit()

    def create_request(self, id: str, session_id: str, tool_name: str, args: Dict[str, Any]) -> ApprovalRequest:
        req = ApprovalRequest(id=id, session_id=session_id, tool_name=tool_name, original_args=args)
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO approvals 
                (id, session_id, tool_name, original_args, status, requester, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                req.id, req.session_id, req.tool_name, 
                json.dumps(req.original_args), req.status.value, 
                req.requester, req.created_at.isoformat()
            ))
            conn.commit()
        adk_logger.info(f"AUDIT - HITL: created on {id} by agent")
        return req

    def get_request(self, id: str) -> Optional[ApprovalRequest]:
        with self._get_connection() as conn:
            cur = conn.execute('SELECT * FROM approvals WHERE id = ?', (id,))
            row = cur.fetchone()
            if not row:
                return None
            
            return ApprovalRequest(
                id=row['id'],
                session_id=row['session_id'],
                tool_name=row['tool_name'],
                original_args=json.loads(row['original_args']),
                modified_args=json.loads(row['modified_args']) if row['modified_args'] else None,
                status=ApprovalStatus(row['status']),
                requester=row['requester'],
                reviewer=row['reviewer'],
                reason=row['reason'],
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.utcnow()
            )

    def submit_decision(self, id: str, status: ApprovalStatus, reviewer: str = "human", reason: Optional[str] = None, modified_args: Optional[Dict[str, Any]] = None):
        with self._get_connection() as conn:
            cur = conn.execute('SELECT id FROM approvals WHERE id = ?', (id,))
            if not cur.fetchone():
                raise ValueError(f"Approval request {id} not found.")
                
            mod_args_str = json.dumps(modified_args) if modified_args else None
            conn.execute('''
                UPDATE approvals 
                SET status = ?, reviewer = ?, reason = ?, modified_args = ?
                WHERE id = ?
            ''', (status.value, reviewer, reason, mod_args_str, id))
            conn.commit()
            
        adk_logger.info(f"AUDIT - HITL: {status.value} on {id} by {reviewer} (reason: {reason})")

# Backward compatibility alias
ApprovalManager = SQLiteApprovalManager
