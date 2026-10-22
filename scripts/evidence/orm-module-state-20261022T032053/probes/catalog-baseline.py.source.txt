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

**El recorrido usa las raíces canónicas, no una constante propia.** Los addons
viven en **dos** raíces —``src/addons`` (sólo ``base``) y ``<repo>/addons`` (los
90 de comunidad)— y ``modules.module.ADDONS_PATHS`` es quien las declara. Este
comando tuvo una constante propia (``BASE_DIR / 'addons'``) que resolvía sólo a
la primera: registraba **1** módulo de 94 y lo reportaba como éxito, mientras la
línea siguiente publicaba **94** desde otro instrumento. Ver :ref:`h-api-649`.

``auto_install``: la referencia instala, aquí se verifica
----------------------------------------------------------

La referencia corre el punto fijo de ``auto_install`` dentro de
``initialize()`` (``odoo19c: odoo/modules/db.py:91-124``) y marca
``state='to install'`` en ``ir_module_module``: **instala**. Aquí no hay
instalador que obedecer esa marca, así que el mismo cálculo se usa para lo
único que tiene sentido en un árbol con ``INSTALLED_APPS`` explícito —
**verificar**: ¿qué addon declara ``auto_install``, tiene todas sus
dependencias requeridas presentes, y sin embargo NO está en la lista?

Es la respuesta a un hueco real (:ref:`h-api-410`): ``ModuleGraph.
auto_installable`` estaba portado, era fiel, y no lo llamaba nadie. El
mecanismo no estaba pendiente de cablear — estaba **estructuralmente
huérfano**, porque su consumidor en la referencia es un instalador que este
árbol no tiene ni va a tener. Darle el consumidor que sí aplica es lo que
convierte un porte muerto en uno vivo.

Sin esto, un addon puente añadido al árbol con ``auto_install: True`` y
olvidado en ``INSTALLED_APPS`` queda invisible: no falla nada, simplemente sus
extensiones nunca se cuelgan. Es el modo de fallo de :ref:`h-api-364`, donde
cinco métodos de ``account_qr_code_sepa`` no se instalaron nunca y sólo lo
vieron sus tests.

Uso::

    python manage.py update_module_list           # aplica
    python manage.py update_module_list --dry-run # sólo reporta
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from addons.authz.declaration import (
    MANIFEST_FILE, read_manifest, values_from_manifest,
)
from addons.base.models import IrModule, IrModuleDependency
from modules import ModuleGraph
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
            '--dry-run', action='store_true',
            help='Reporta lo que haría sin escribir en la base.',
        )

    def handle(self, *args, **options):
        dry_run  = options['dry_run']
        installed = installed_addon_names()
        stored    = {module.name: module for module in IrModule.objects.all()}

        updated = added = 0
        without_manifest = []

        for addon in get_modules():
            addon_dir = get_module_path(addon)
            if addon_dir is None:
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
        self._report_auto_install_gaps(installed)
        return None

    def _report_auto_install_gaps(self, installed):
        """Addons que ``auto_install`` reclama y ``INSTALLED_APPS`` no tiene.

        Único llamador de ``ModuleGraph.auto_installable`` en el árbol. El
        cálculo es el de la referencia; el uso, no: allí marca para instalar,
        aquí sólo reporta la incoherencia entre lo que el manifest declara y lo
        que la lista carga.

        **El denominador va junto al conteo, y no es el que parece.** El
        chequeo sólo puede ver addons **con manifest**: sin
        ``__manifest__.py`` no hay dónde declarar ``auto_install``, así que un
        addon sin él es invisible para este cálculo aunque esté cargado. Un
        ``0 pendientes`` sobre el total de ``INSTALLED_APPS`` sería el
        denominador oculto que ``hallazgo-abierto-genera-sucesor.md`` describe:
        un instrumento ciego y uno correcto publican la misma cifra.
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
            f'dependencias presentes y NO están en INSTALLED_APPS ({alcance}):'
        ))
        for name in missing:
            depends = ', '.join(graph[name].depends) or '—'
            self.stdout.write(f'  {name}  (depends: {depends})')

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
