"""Manifest data stage using the existing Django converter.

Corresponds to pinned Odoo19Community modules/loading.py::load_data. An
explicit database alias replaces the reference Environment database binding.
This stage neither commits nor marks a module installed: the caller owns
schema readiness, registry setup, transaction, hooks and finalization.
"""
import logging

from django.db import connections

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
