"""Manifest data stage using the existing Django converter.

Corresponds to pinned Odoo19Community modules/loading.py::load_data. An
explicit database alias replaces the reference Environment database binding.
This stage neither commits nor marks a module installed: the caller owns
schema readiness, registry setup, transaction, hooks and finalization.
"""
import logging
import traceback

from django.db import connections, router, transaction
from django.db.transaction import TransactionManagementError

from tools.convert import convert_file

_logger = logging.getLogger(__name__)


def load_data(idref, mode, kind, package, *, using):
    """Import ordered manifest files and return whether any were encountered.

    Duplicates are warned about and imported again, as in the reference.
    The current manifest resolver can omit empty lists; missing keys are
    treated as empty. Conversion failures propagate to the caller transaction.
    """
    if not isinstance(using, str) or not using:
        raise ValueError('A database alias is required for module data')
    connections[using]  # Reject unknown aliases even when the manifest is empty.
    keys = ('init_xml', 'data') if kind == 'data' else ('demo',)
    files = set()
    for key in keys:
        filenames = package.manifest.get(key, ())
        if key == 'init_xml' and filenames:
            _logger.warning("module %s: key 'init_xml' is deprecated in Odoo 19.",
                            package.name)
        for filename in filenames:
            if filename in files:
                _logger.warning('File %s is imported twice in module %s %s',
                                filename, package.name, kind)
            files.add(filename)
            _logger.info('loading %s/%s', package.name, filename)
            convert_file(package.name, filename, idref, mode,
                         noupdate=kind == 'demo', using=using)
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
        raise TransactionManagementError('Demo loading requires a caller transaction')
    try:
        failure = env['base.IrDemoFailure']
    except KeyError:
        failure = None
    if failure is not None and router.db_for_write(failure) != using:
        raise ValueError('Demo reporting context must match the selected database alias')
    try:
        with transaction.atomic(using=using):
            with env(su=True, context={**env.context, 'install_demo': True}):
                load_data(idref, mode, 'demo', package, using=using)
        return True
    except Exception:
        # Demo errors are optional in the pinned contract. Roll back demo
        # data first; errors in the reporting path below must still propagate.
        error = traceback.format_exc()
        _logger.warning('Module %s demo data failed to install', package.name,
                        exc_info=True)
        configuration_step = env.ref('base.demo_failure_todo', raise_if_not_found=False)
        if configuration_step is not None and failure is not None:
            module = failure._meta.get_field('module').remote_field.model
            if not module.objects.using(using).filter(
                    pk=package.id, name=package.name).exists():
                raise ValueError('Demo package identity does not match the selected catalogue')
            configuration_step_database = getattr(getattr(configuration_step, '_state', None), 'db', None)
            if isinstance(configuration_step_database, str) and configuration_step_database != using:
                raise ValueError('Demo todo alias does not match the selected database')
            with transaction.atomic(using=using):
                configuration_step.state = 'open'
                configuration_step.save(using=using, update_fields=['state'])
                failure.objects.using(using).create(module_id=package.id, error=error)
        return False
