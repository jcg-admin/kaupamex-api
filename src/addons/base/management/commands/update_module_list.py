"""Puebla el catálogo técnico leyendo los ``__manifest__.py`` del árbol.

Adaptado de ``ir.module.module.update_list`` (Odoo Community, LGPL-3) —
atribución y aviso preservados (DEC-KX-03).

**Qué conserva del original.** El recorrido: por cada manifest encontrado,
mapear con la función pura ``values_from_manifest`` (el
``get_values_from_terp`` de la referencia), crear o actualizar la fila, y
reconciliar sus dependencias. Y el contador de salida ``[actualizados,
añadidos]``.

**En qué diverge, y por qué.** El ``state`` no lo escribe un instalador —aquí
no hay— sino que **se deriva** de ``INSTALLED_APPS``: el addon cargado está
``installed``; el que está en disco y no en la lista, ``uninstalled``; el que
declara ``installable: False``, ``uninstallable``. Es la diferencia entre
registrar un hecho y pretender gobernarlo: el comando **describe** el árbol, no
lo instala.

Uso::

    python manage.py update_module_list           # aplica
    python manage.py update_module_list --dry-run # sólo reporta
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from addons.authz.declaration import (
    MANIFEST_FILE, read_manifest, values_from_manifest,
)
from addons.base.models import IrModule, IrModuleDependency

ADDONS_ROOT = os.path.join(settings.BASE_DIR, 'addons')


def installed_addon_names():
    """Nombres de addon que ``INSTALLED_APPS`` carga.

    Se derivan de la lista efectiva de Django, no del texto del settings: es el
    hecho de qué está cargado, no lo que un archivo dice.
    """
    return {
        app.rsplit('.', 1)[-1]
        for app in settings.INSTALLED_APPS
        if app.startswith('addons.')
    }


class Command(BaseCommand):
    help = 'Actualiza el catálogo técnico de addons desde sus __manifest__.py.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Reporta lo que haría sin escribir en la base.',
        )

    def handle(self, *args, **options):
        dry_run  = options['dry_run']
        installed = installed_addon_names()
        stored    = {module.name: module for module in IrModule.objects.all()}

        updated = added = 0
        without_manifest = []

        for addon in sorted(os.listdir(ADDONS_ROOT)):
            addon_dir = os.path.join(ADDONS_ROOT, addon)
            if not os.path.isdir(addon_dir) or addon.startswith('__'):
                continue

            manifest = read_manifest(addon_dir)
            if manifest is None:
                without_manifest.append(addon)
                continue

            values = values_from_manifest(manifest)
            depends = values.pop('depends')
            values.pop('installable')
            values['state'] = self._derive_state(addon, manifest, installed)

            row = stored.get(addon)
            if row is None:
                added += 1
                if not dry_run:
                    row = IrModule.objects.create(name=addon, **values)
            else:
                changed = {k: v for k, v in values.items()
                           if getattr(row, k) != v}
                if changed:
                    updated += 1
                    if not dry_run:
                        for key, value in changed.items():
                            setattr(row, key, value)
                        row.save(update_fields=[*changed, 'updated_at'])

            if not dry_run and row is not None:
                self._sync_dependencies(row, depends)

        self._report(added, updated, without_manifest, dry_run)
        return None

    def _derive_state(self, addon, manifest, installed):
        """El estado se deriva del árbol; no hay instalador que lo escriba."""
        if manifest.get('installable', True) is False:
            return IrModule.STATE_UNINSTALLABLE
        return (IrModule.STATE_INSTALLED if addon in installed
                else IrModule.STATE_UNINSTALLED)

    @transaction.atomic
    def _sync_dependencies(self, module, depends):
        """Deja las aristas del manifest, ni una más.

        Las que sobran se retiran: una dependencia que el manifest dejó de
        declarar y sobrevive en la tabla es el mismo defecto que H-API-106
        registró en el catálogo comercial.
        """
        declared = set(depends)
        existing = set(module.dependencies.values_list('name', flat=True))
        for name in sorted(declared - existing):
            IrModuleDependency.objects.create(module=module, name=name)
        if existing - declared:
            module.dependencies.filter(name__in=existing - declared).delete()

    def _report(self, added, updated, without_manifest, dry_run):
        prefix = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Catálogo técnico: {added} añadidos, {updated} actualizados.'
        ))
        if without_manifest:
            self.stdout.write(self.style.WARNING(
                f'{len(without_manifest)} addon(s) sin {MANIFEST_FILE} — no entran '
                f'al catálogo:'
            ))
            self.stdout.write('  ' + ', '.join(without_manifest))
