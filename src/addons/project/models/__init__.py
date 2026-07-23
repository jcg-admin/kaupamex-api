"""Modelos del addon ``project`` (estructura Odoo: un archivo por modelo)."""
from .project_project import Project
from .project_task import ProjectTask
from .project_task_type import ProjectTaskType

__all__ = ['Project', 'ProjectTask', 'ProjectTaskType']
