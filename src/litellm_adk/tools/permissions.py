"""Tool permission classifications."""

from enum import Enum


class ToolPermission(str, Enum):
    """Permissions for tool capabilities and access levels."""

    READ = "read"
    WRITE = "write"
    EXTERNAL = "external"
    DANGEROUS = "dangerous"
