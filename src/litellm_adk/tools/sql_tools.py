import json
import logging
from enum import Enum
from typing import List, Dict, Any, Optional, Union
import sqlalchemy
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import sqlparse

logger = logging.getLogger("litellm_adk.tools.sql")

class DatabaseAccessLevel(Enum):
    """Industry-standard role-based access levels for database operations."""
    READ_ONLY = "read_only"   # DQL only (SELECT, SHOW, etc)
    READ_WRITE = "read_write" # DQL + DML (INSERT, UPDATE, DELETE)
    ADMIN = "admin"           # All operations including DDL (CREATE, DROP)

class SQLTools:
    """
    Manages database connection, schema introspection, and secure SQL execution.
    Designed to be used by NL2SQLAgent.
    """
    def __init__(self, db_url: str, schema_config: Optional[Dict[str, Any]] = None):
        """
        Initialize SQL Tools.
        
        Args:
            db_url: Database connection string (SQLAlchemy format).
            schema_config: Optional config to filter tables and set access levels.
                           {'include_tables': ['users'], 'access_level': DatabaseAccessLevel.READ_ONLY}
        """
        self.db_url = db_url
        self.engine = create_engine(db_url) # Synchronous engine (offloaded by Agent)
        self.schema_config = schema_config or {}
        
        # Enforce query restrictions at the driver level
        @sqlalchemy.event.listens_for(self.engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            # Resolve access level, defaulting to secure Read-Only
            access_level = self.schema_config.get("access_level", DatabaseAccessLevel.READ_ONLY)
            
            # Map access levels to safe prefixes
            if access_level == DatabaseAccessLevel.READ_ONLY:
                safe_prefixes = ("select", "explain", "describe", "show")
            elif access_level == DatabaseAccessLevel.READ_WRITE:
                safe_prefixes = ("select", "explain", "describe", "show", "insert", "update", "delete", "with")
            elif access_level == DatabaseAccessLevel.ADMIN:
                safe_prefixes = None # All queries allowed
            else:
                safe_prefixes = ("select", "explain", "describe", "show") # Fallback
            
            if safe_prefixes is not None:
                if not statement.lower().lstrip().startswith(safe_prefixes):
                    logger.error(f"Security Alert: Blocked unauthorized query type: {statement}")
                    raise Exception(f"Security Exception: Operation not allowed under {access_level.name} access level.")
                
        logger.warning(f"SQLTools: Query validation event listener attached. Ensure your database user is also restricted to appropriate permissions in production.")
        
    def get_table_names(self) -> List[str]:
        """Returns a list of all table names."""
        try:
            inspector = inspect(self.engine)
            all_tables = inspector.get_table_names()
            
            # Apply Config Filters
            include = self.schema_config.get('include_tables')
            exclude = self.schema_config.get('exclude_tables', [])
            
            if include:
                all_tables = [t for t in all_tables if t in include]
            
            return [t for t in all_tables if t not in exclude]
        except Exception as e:
            logger.error(f"Error fetching table names: {e}")
            return []

    def get_schema_summary(self, table_names: Optional[List[str]] = None) -> str:
        """
        Returns a simplified schema summary (DDL-like) for the LLM prompt.
        Args:
            table_names: specific list of tables to inspect. If None, checks ALL (filtered) tables.
        """
        try:
            inspector = inspect(self.engine)
            
            target_tables = table_names
            if not target_tables:
                target_tables = self.get_table_names()
            
            schema_str = []
            for table in target_tables:
                # Basic check to avoid errors if table doesn't exist
                if not inspector.has_table(table):
                     continue

                columns = inspector.get_columns(table)
                # Format: Table Name (col1: type, col2: type)
                col_defs = [f"{c['name']}: {c['type']}" for c in columns]
                schema_str.append(f"Table '{table}':\n  Columns: {', '.join(col_defs)}")
                
                # Add Foreign Keys if useful
                try:
                    fks = inspector.get_foreign_keys(table)
                    if fks:
                        fk_strs = [f"{fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}" for fk in fks]
                        schema_str.append(f"  Foreign Keys: {', '.join(fk_strs)}")
                except Exception:
                    pass
            
            return "\n\n".join(schema_str)
        except Exception as e:
            logger.error(f"Schema introspection failed: {e}")
            return "Error: Could not retrieve database schema."

    def execute_sql_tool(self, query: str) -> str:
        """
        The actual Tool function exposed to the LLM.
        Executes the query and returns JSON results or Error message.
        """
        query = query.strip()
        
        # Security is handled at the driver-level via the before_cursor_execute event listener.
        
        # 2. Execute
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                
                # Fetch results (limit to avoid token overflow)
                # We can't use LIMIT in SQL easily without parsing/rewriting, 
                # so we fetchmany.
                rows = result.fetchmany(100)
                keys = result.keys()
                
                data = [dict(zip(keys, row)) for row in rows]
                
                if not data:
                    return "Query executed successfully in 0.0s. No rows returned."
                
                # Convert to string (JSON is good for LLM)
                import json
                json_res = json.dumps(data, default=str, indent=2)
                
                # Smart Truncation: Hard limit on characters to protect Context Window
                start_marker = f"Query executed successfully. Returned {len(data)} rows.\n"
                if len(json_res) > 3000:
                    return start_marker + json_res[:3000] + "\n... (Result truncated. Please refine query with LIMIT or Aggregations)"
                
                return start_marker + json_res
                
        except SQLAlchemyError as e:
            # Return the specific DB error so the LLM can fix it
            return f"Database Error: {str(e.__cause__) or str(e)}"
        except Exception as e:
            return f"Execution Error: {str(e)}"
