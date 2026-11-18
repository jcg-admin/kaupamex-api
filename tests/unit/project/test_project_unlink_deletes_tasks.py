"""``project.project.unlink`` borra las tareas; la FK no las arrastra.

La tarea guarda ``project_id`` sin ``ondelete`` (``odoo19c: addons/project/
models/project_task.py:192-193``): ``set null``. Quien borra las tareas es
el ``unlink`` del proyecto, incluidas las archivadas, y antes las
configuraciones de acciones embebidas (``odoo19c: addons/project/models/
project_project.py:704-716``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
project-unlink-deletes-tasks.md``.

*Métrica:* filas de ``project_task`` y de la configuración tras borrar.
*Ciega a:* subtareas y recurrencia, que nuestra tarea no declara.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models.ir_actions import IrActionsActWindow
from addons.base.models.res_users_settings import ResUsersSettings
from addons.project.models import Project, ProjectTask
from addons.web.models.res_users_settings_embedded_action import (
    ResUsersSettingsEmbeddedAction,
)
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


def _project(name):
    return Project.create({'name': name})


def _task(project, name, active=True):
    return ProjectTask.objects.create(project=project, name=name,
                                      active=active)


def test_unlink_deletes_active_and_archived_tasks():
    project = _project('Proyecto con tareas')
    task_ids = [_task(project, 'Activa').pk,
                _task(project, 'Archivada', active=False).pk]
    project.unlink()
    assert not Project.objects.filter(pk=project.pk).exists()
    assert not ProjectTask.objects.filter(pk__in=task_ids).exists()


def _embedded_config(project):
    user = get_user_model().objects.create_user(
        login=f'embedded-{project.pk}', password=None, name='u')
    action = IrActionsActWindow.objects.create(
        name='Tareas embebidas', res_model='project.Project')
    return ResUsersSettingsEmbeddedAction.objects.create(
        user_setting_id=ResUsersSettings._find_or_create_for_user(user),
        action_id_id=action.pk, res_model='project.project',
        res_id=project.pk)


def test_unlink_deletes_the_embedded_action_configs_of_the_project():
    project = _project('Proyecto con configuración')
    other = _project('Otro proyecto')
    own = _embedded_config(project)
    kept = _embedded_config(other)
    project.unlink()
    assert not ResUsersSettingsEmbeddedAction.objects.filter(
        pk=own.pk).exists()
    assert ResUsersSettingsEmbeddedAction.objects.filter(pk=kept.pk).exists()


def test_a_raw_row_delete_leaves_the_task_without_project():
    project = _project('Proyecto borrado por fila')
    task = _task(project, 'Huérfana')
    Project.objects.filter(pk=project.pk).delete()
    task.refresh_from_db()
    assert task.project_id is None
