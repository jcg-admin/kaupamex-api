"""Refresca metadata del catálogo técnico en una base explícita.

Adaptado de Odoo Community 19 ir.module.module.update_list (LGPL-3).
La disponibilidad de código no instala módulos: conserva el estado existente,
registra nuevos módulos como no instalados y reconcilia sus dependencias.
Toda la actualización se confirma o revierte en la conexión seleccionada.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections, transaction

from addons.authz.declaration import (
    MANIFEST_FILE, read_manifest, values_from_manifest,
)
from addons.base.models import IrModule, IrModuleDependency
from modules import ModuleGraph
from modules.db import create_categories, validate_category_paths
from modules.module import ADDONS_PATHS, get_module_path, get_modules


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
            '--database', default=DEFAULT_DB_ALIAS,
            help='Alias registrado cuyo catálogo se actualizará.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Reporta lo que haría sin escribir en la base.',
        )

    def handle(self, *args, **options):
        using = options['database']
        if using not in connections:
            raise CommandError(f'Unknown database alias: {using}')
        with transaction.atomic(using=using):
            return self._refresh(using, options['dry_run'])

    def _refresh(self, using, dry_run):
        stored = {module.name: module for module in
                  IrModule.objects.using(using).select_for_update()}
        installed = {name for name, row in stored.items()
                     if row.state == IrModule.STATE_INSTALLED}

        updated = added = 0
        without_manifest = []
        manifests = {}

        for addon in get_modules():
            addon_dir = get_module_path(addon)
            if addon_dir is None:
                continue

            manifest = read_manifest(addon_dir)
            if manifest is None:
                without_manifest.append(addon)
                continue

            manifests[addon] = manifest

        paths = {name: row.category_path for name, row in stored.items()}
        paths.update({name: manifest.get('category', 'Uncategorized')
                      for name, manifest in manifests.items()})
        validate_category_paths(paths.values())

        for addon, manifest in manifests.items():

            values = values_from_manifest(manifest)
            depends = values.pop('depends')
            values.pop('installable')
            category_path = values.pop('category')
            values['category_path'] = category_path
            if not dry_run:
                with connections[using].cursor() as cursor:
                    values['category_id'] = create_categories(
                        cursor, category_path.split('/') if category_path else [],
                    )
            row = stored.get(addon)
            if row is None:
                values['state'] = (IrModule.STATE_UNINSTALLED
                                   if manifest.get('installable', True)
                                   else IrModule.STATE_UNINSTALLABLE)
                added += 1
                if not dry_run:
                    row = IrModule.objects.using(using).create(name=addon, **values)
            else:
                if row.state in {IrModule.STATE_UNINSTALLED, IrModule.STATE_UNINSTALLABLE}:
                    values['state'] = (IrModule.STATE_UNINSTALLED
                                       if manifest.get('installable', True)
                                       else IrModule.STATE_UNINSTALLABLE)
                changed = {k: v for k, v in values.items()
                           if getattr(row, k) != v}
                if changed:
                    updated += 1
                    if not dry_run:
                        for key, value in changed.items():
                            setattr(row, key, value)
                        row.save(using=using, update_fields=[*changed, 'updated_at'])

            if not dry_run and row is not None:
                self._sync_dependencies(row, depends, using=using)

        self._report(added, updated, without_manifest, dry_run)
        self._report_auto_install_gaps(installed)
        return None

    def _report_auto_install_gaps(self, installed):
        """Reporta candidatos usando el estado persistido de la base seleccionada.

        El alcance es el conjunto descubierto con manifiesto; el reporte no
        instala candidatos ni representa disponibilidad de clases Python.
        """
        modules = sorted(get_modules())
        graph = ModuleGraph()
        graph.extend(modules)
        visible = [name for name in modules if graph[name].manifest]
        missing = graph.auto_installable(installed)

        alcance = (f'alcance medido: {len(visible)} addon(s) con manifest '
                   f'de {len(modules)} en el árbol')

        if not missing:
            self.stdout.write(self.style.SUCCESS(
                f'auto_install coherente: 0 pendientes ({alcance}).'
            ))
            return

        self.stdout.write(self.style.WARNING(
            f'{len(missing)} addon(s) declaran auto_install, tienen sus '
            f'dependencias presentes y NO están instalados en esta base ({alcance}):'
        ))
        for name in missing:
            depends = ', '.join(graph[name].depends) or '—'
            self.stdout.write(f'  {name}  (depends: {depends})')

    def _sync_dependencies(self, module, depends, *, using):
        """Deja las aristas del manifest, ni una más.

        Las que sobran se retiran: una dependencia que el manifest dejó de
        declarar y sobrevive en la tabla es el mismo defecto que H-API-106
        registró en el catálogo comercial.
        """
        declared = set(depends)
        dependencies = IrModuleDependency.objects.using(using).filter(module_id=module.pk)
        existing = set(dependencies.values_list('name', flat=True))
        for name in sorted(declared - existing):
            IrModuleDependency.objects.using(using).create(module_id=module.pk, name=name)
        if existing - declared:
            dependencies.filter(name__in=existing - declared).delete()

    def _report(self, added, updated, without_manifest, dry_run):
        """El conteo va con su denominador — sin él, dos instrumentos mienten igual.

        ``h-api-649``: la salida decía ``1 añadidos`` y, dos líneas abajo,
        ``94 addon(s) … en el árbol``. Las dos cifras eran correctas y medían
        universos distintos; nada en el reporte lo delataba.
        """
        prefix = '[dry-run] ' if dry_run else ''
        alcance = ', '.join(str(root) for root in ADDONS_PATHS if root.is_dir())
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Catálogo técnico: {added} añadidos, {updated} actualizados '
            f'(alcance medido: {len(get_modules())} addon(s) en {alcance}).'
        ))
        if without_manifest:
            self.stdout.write(self.style.WARNING(
                f'{len(without_manifest)} addon(s) sin {MANIFEST_FILE} — no entran '
                f'al catálogo:'
            ))
            self.stdout.write('  ' + ', '.join(without_manifest))
