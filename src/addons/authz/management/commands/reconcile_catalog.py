"""Reconcilia el catálogo sembrado en DB contra lo que declaran los addons.

**Qué resuelve (SOL-100 punto 2).** ``check_catalog_declaration.py`` verifica
que las declaraciones sean coherentes **entre sí**; este comando verifica que
la **DB** coincida con ellas. Son problemas distintos y el segundo sólo se ve
en runtime.

El caso que lo motiva es H-API-106 en su forma exacta: el addon ``orders`` se
retiró (``api@77bd1f0``) y su fila ``authz_module`` siguió viva en toda base
ya sembrada, con cuatro aristas ``depends`` apuntando a ella. Ningún comando
lo notaba porque la siembra sólo **añade**: ``get_or_create`` nunca retira lo
que dejó de declararse.

**Tres divergencias que reporta:**

1. **Sembrado sin declarar** — la fila existe en DB y ningún addon la declara.
   Es deuda: se puede suscribir un módulo que ya no significa nada.
2. **Declarado sin sembrar** — falta correr ``seed_authz``. No es deuda, es un
   despliegue a medias.
3. **Metadata divergente** — la fila existe pero su ``name`` /
   ``is_application`` / ``category`` / ``depends`` no coincide con lo
   declarado. Suele ser edición manual en la consola L0.

**Por qué ``--prune`` es opt-in y con freno.** Retirar un ``Module`` no es
inocuo: ``Capability.module`` es ``PROTECT`` y ``CompanyModuleSubscription``
apunta a él. Una company puede estar **pagando** por un módulo cuya declaración
alguien borró; borrar la fila destruiría ese registro. Por eso el comando
**reporta por defecto**, y ``--prune`` se niega a tocar cualquier módulo con
suscripciones.

Uso::

    python manage.py reconcile_catalog            # reporte, exit 0
    python manage.py reconcile_catalog --strict   # exit 1 si hay divergencias
    python manage.py reconcile_catalog --prune    # retira lo no declarado (con freno)
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from addons.authz.declaration import discover
from addons.authz.models import Capability, Module
from addons.company.models import CompanyModuleSubscription


class Command(BaseCommand):
    help = 'Compara el catálogo sembrado en DB contra lo declarado por los addons.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict', action='store_true',
            help='Sale con código 1 si hay cualquier divergencia (para CI).',
        )
        parser.add_argument(
            '--prune', action='store_true',
            help='Retira de la DB los módulos y capacidades que nadie declara. '
                 'Se niega a tocar módulos con suscripciones vivas.',
        )

    def handle(self, *args, **options):
        specs_modules, specs_caps = discover()

        db_modules = {m.code: m for m in Module.objects.prefetch_related('depends')}
        db_caps = {c.code: c for c in Capability.objects.all()}

        modulos_stale = sorted(set(db_modules) - set(specs_modules))
        modulos_faltantes = sorted(set(specs_modules) - set(db_modules))
        caps_stale = sorted(set(db_caps) - set(specs_caps))
        caps_faltantes = sorted(set(specs_caps) - set(db_caps))
        divergentes = self._metadata_divergente(specs_modules, db_modules)

        self._reportar('Módulos sembrados que nadie declara', modulos_stale)
        self._reportar('Módulos declarados sin sembrar (falta seed_authz)',
                       modulos_faltantes)
        self._reportar('Capacidades sembradas que nadie declara', caps_stale)
        self._reportar('Capacidades declaradas sin sembrar', caps_faltantes)
        self._reportar('Metadata divergente entre DB y declaración', divergentes)

        total = (len(modulos_stale) + len(modulos_faltantes) + len(caps_stale)
                 + len(caps_faltantes) + len(divergentes))

        if options['prune']:
            self._prune(modulos_stale, caps_stale, db_modules, db_caps)

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                f'Catálogo reconciliado: {len(specs_modules)} módulos y '
                f'{len(specs_caps)} capacidades coinciden con la declaración.'
            ))
            return

        self.stdout.write(self.style.WARNING(f'{total} divergencia(s).'))
        if options['strict'] and not options['prune']:
            raise CommandError(
                'Catálogo divergente. Correr seed_authz si faltan filas, o '
                'reconcile_catalog --prune si sobran.'
            )

    def _metadata_divergente(self, specs, db_modules):
        """Filas cuya metadata no coincide con lo declarado por su addon."""
        salida = []
        for code, spec in specs.items():
            fila = db_modules.get(code)
            if fila is None:
                continue
            diffs = []
            if fila.name != spec.name:
                diffs.append(f'name {fila.name!r}≠{spec.name!r}')
            if fila.is_application != spec.is_application:
                diffs.append(
                    f'is_application {fila.is_application}≠{spec.is_application}')
            if fila.category != spec.category:
                diffs.append(f'category {fila.category!r}≠{spec.category!r}')
            depends_db = set(fila.depends.values_list('code', flat=True))
            if depends_db != set(spec.depends):
                diffs.append(
                    f'depends {sorted(depends_db)}≠{sorted(spec.depends)}')
            if diffs:
                salida.append(f'{code}: ' + ' · '.join(diffs))
        return salida

    @transaction.atomic
    def _prune(self, modulos_stale, caps_stale, db_modules, db_caps):
        """Retira lo no declarado, protegiendo lo que una company contrató.

        El orden importa: las capacidades primero, porque ``Capability.module``
        es ``PROTECT`` y una capacidad viva impediría retirar su módulo.
        """
        for code in caps_stale:
            db_caps[code].delete()
        if caps_stale:
            self.stdout.write(f'Retiradas {len(caps_stale)} capacidad(es).')

        con_suscripcion = set(
            CompanyModuleSubscription.objects
            .filter(module__code__in=modulos_stale)
            .values_list('module__code', flat=True)
        )
        retirados = 0
        for code in modulos_stale:
            if code in con_suscripcion:
                self.stdout.write(self.style.WARNING(
                    f'  {code}: NO se retira — tiene suscripciones de company. '
                    f'Cancelarlas o volver a declararlo.'
                ))
                continue
            db_modules[code].delete()
            retirados += 1
        if retirados:
            self.stdout.write(f'Retirados {retirados} módulo(s).')

    def _reportar(self, titulo, elementos):
        if not elementos:
            return
        self.stdout.write(self.style.WARNING(f'{titulo} ({len(elementos)}):'))
        for elemento in elementos:
            self.stdout.write(f'  - {elemento}')
