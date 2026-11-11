"""Bounded module-loading stages using existing Django mechanisms.

Corresponds to pinned Odoo19Community modules/loading.py::load_data. An
explicit database alias replaces the reference Environment database binding.
This stage neither commits nor marks a module installed: the caller owns
schema readiness, registry setup, transaction, hooks and finalization.

``load_modules`` is that caller for the addons of ``INSTALLED_APPS``: the
per-module step of the reference ``load_module_graph`` over a migrated
database (designs/module-install-cycle.md).
"""

import logging
import traceback

from django.apps import apps
from django.core.management import call_command
from django.db import connections, router, transaction
from django.db.transaction import TransactionManagementError

from modules.module import installed_addon_names
from modules.module_graph import ModuleGraph
from orm.environments import Environment
from orm.registry import Registry
from orm.utils import SUPERUSER_ID
from tools.convert import convert_file

_logger = logging.getLogger(__name__)


def reset_modules_state(using):
    """Persist failure recovery after the failed installation has rolled back.

    Odoo opens an independent committing cursor. Django callers must instead
    exit their failed transaction before invoking this explicit-alias stage.
    Refuse nesting so recovery cannot silently disappear in a caller rollback.
    """
    if not isinstance(using, str) or not using:
        raise ValueError('A database alias is required for module recovery')
    database = connections[using]
    if database.in_atomic_block or not database.get_autocommit():
        raise TransactionManagementError(
            'Module recovery requires an independent transaction'
        )
    with transaction.atomic(using=using):
        with database.cursor() as cursor:
            if 'ir_module_module' not in database.introspection.table_names(
                cursor
            ):
                _logger.info(
                    'skipping reset_modules_state, ir_module_module table does'
                    ' not exist'
                )
                return
            cursor.execute(
                "UPDATE ir_module_module SET state='installed' "
                "WHERE state IN ('to remove', 'to upgrade')"
            )
            cursor.execute(
                "UPDATE ir_module_module SET state='uninstalled' "
                "WHERE state='to install'"
            )
    _logger.warning('Transient module states were reset')


def _check_module_names(cr, module_names):
    """Warn about unknown requests in the catalogue bound to ``cr``.

    Like the pinned loader, this validates names without changing the input,
    module states or transaction boundaries. ``all`` is a request wildcard.
    """
    names = set(module_names)
    names.discard('all')
    if names:
        cr.execute(
            'SELECT count(id) FROM ir_module_module WHERE name = ANY(%s)',
            (list(names),),
        )
        row = cr.fetchone()
        assert row is not None
        if row[0] != len(names):
            cr.execute('SELECT name FROM ir_module_module')
            incorrect_names = names.difference(name for name, in cr.fetchall())
            _logger.warning(
                'invalid module names, ignored: %s', ', '.join(incorrect_names)
            )


def load_data(idref, mode, kind, package, *, using):
    """Import ordered manifest files and return whether any were encountered.

    Duplicates are warned about and imported again, as in the reference.
    The current manifest resolver can omit empty lists; missing keys are
    treated as empty. Conversion failures propagate to the caller transaction.
    """
    if not isinstance(using, str) or not using:
        raise ValueError('A database alias is required for module data')
    # Reject unknown aliases even when the manifest is empty.
    connections[using]
    keys = ('init_xml', 'data') if kind == 'data' else ('demo',)
    files = set()
    for key in keys:
        filenames = package.manifest.get(key, ())
        if key == 'init_xml' and filenames:
            _logger.warning(
                "module %s: key 'init_xml' is deprecated in Odoo 19.",
                package.name,
            )
        for filename in filenames:
            if filename in files:
                _logger.warning(
                    'File %s is imported twice in module %s %s',
                    filename,
                    package.name,
                    kind,
                )
            files.add(filename)
            _logger.info('loading %s/%s', package.name, filename)
            convert_file(
                package.name,
                filename,
                idref,
                mode,
                noupdate=kind == 'demo',
                using=using,
            )
    return bool(files)


def load_demo(env, package, idref, mode):
    """Load optional demo under a caller-owned transaction and elevated scope.

    Django atomic supplies the reference savepoint; Environment must be entered
    to activate its context overrides. The existing Django-label resolver is
    the equivalent of the reference optional ir.demo_failure model lookup.
    """
    if not (package.manifest.get('demo') or package.manifest.get('demo_xml')):
        return True
    using = env.cr.alias
    if not connections[using].in_atomic_block:
        raise TransactionManagementError(
            'Demo loading requires a caller transaction'
        )
    try:
        failure = env['base.IrDemoFailure']
    except KeyError:
        failure = None
    if failure is not None and router.db_for_write(failure) != using:
        raise ValueError(
            'Demo reporting context must match the selected database alias'
        )
    _logger.info('Module %s: loading demo', package.name)
    try:
        with transaction.atomic(using=using):
            with env(su=True, context={**env.context, 'install_demo': True}):
                load_data(idref, mode, 'demo', package, using=using)
        return True
    except Exception:
        # Demo errors are optional in the pinned contract. Roll back demo
        # data first; errors in the reporting path below must still propagate.
        error = traceback.format_exc()
        _logger.warning(
            'Module %s demo data failed to install, '
            'installed without demo data',
            package.name,
            exc_info=True,
        )
        configuration_step = env.ref(
            'base.demo_failure_todo', raise_if_not_found=False
        )
        if configuration_step is not None and failure is not None:
            module = failure._meta.get_field('module').remote_field.model
            if (
                not module.objects.using(using)
                .filter(pk=package.id, name=package.name)
                .exists()
            ):
                raise ValueError(
                    'Demo package identity does not match the selected'
                    ' catalogue'
                )
            configuration_step_database = getattr(
                getattr(configuration_step, '_state', None), 'db', None
            )
            if (
                isinstance(configuration_step_database, str)
                and configuration_step_database != using
            ):
                raise ValueError(
                    'Demo todo alias does not match the selected database'
                )
            with transaction.atomic(using=using):
                configuration_step.state = 'open'
                configuration_step.save(using=using, update_fields=['state'])
                failure.objects.using(using).create(
                    module_id=package.id, error=error
                )
        return False


def load_modules(using):
    """Install or update the addons of ``INSTALLED_APPS`` on ``using``.

    Adapts the per-module step of Odoo Community 19 ``load_module_graph``
    (``odoo/modules/loading.py:186-260``, LGPL-3): in graph order, each
    module gets ``init_models`` with the module in context, which reflects
    its models and gives them their ``model_<name>`` xmlid, then
    ``load_data`` of its manifest ``data`` files, and ends ``installed``. A
    module not yet installed loads in ``init`` mode and an installed one in
    ``update`` mode, as the reference does for install and upgrade.

    The catalog is refreshed first by ``update_module_list``, the reference
    ``update_list``, whose ``create_categories`` gives each module its
    category. Declared divergence: installing here is being in
    ``INSTALLED_APPS`` with the schema migrated, so every listed addon is
    installed; installation on request stays with TASK-API-0382.

    Each module runs in its own transaction, as the reference commits after
    a module loads and leaves a failing one rolled back: a data file that
    fails halfway leaves none of that module's rows behind.
    """
    call_command('update_module_list', database=using, verbosity=0)
    IrModule = apps.get_model('base', 'IrModule')
    rows = {row.name: row for row in IrModule.objects.using(using)}
    graph = ModuleGraph.from_database(
        installed_addon_names(), using=using, mode='update')
    registry = Registry(using)
    with Environment(using, SUPERUSER_ID, {}) as environment:
        for package in graph:
            row = rows[package.name]
            install = row.state != IrModule.STATE_INSTALLED
            model_names = [
                name for name, model in registry.models.items()
                if getattr(getattr(model, '_meta', None), 'app_label',
                           None) == package.name
            ]
            with transaction.atomic(using=using):
                with connections[using].cursor() as cursor:
                    registry.init_models(
                        cursor, model_names, {'module': package.name},
                        install)
                load_data({}, 'init' if install else 'update', 'data',
                          package, using=using)
                if install:
                    row.state = IrModule.STATE_INSTALLED
                    row.save(using=using,
                             update_fields=['state', 'write_date'])
                environment.flush_all()
