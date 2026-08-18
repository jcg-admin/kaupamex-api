"""System checks del ORM — el gate de ``run_checks()`` antes de ``makemigrations``.

Cierra :ref:`h-api-584`: una migración puede quedar escrita en disco con un
``ForeignKey`` **irresoluble** (una cadena ``'app.Modelo'`` que ningún addon
instalado declara) sin que nada lo impida, y el error sólo aparece —tarde, con
otro traceback— al **aplicar** esa migración.

Django ya trae el detector: ``fields.E300``/``fields.E307`` son exactamente el
check para *"la referencia perezosa nunca se resolvió"* (medido, ver abajo).
Lo que faltaba en este árbol no era el detector — era que **corriera**.

Divergencia declarada de ubicación
-----------------------------------

Este archivo no porta ningún módulo de la referencia: ``$ODOO19C/odoo/orm/``
no tiene ``checks.py`` (listado, 2026-08-18) — es tooling propio, no un
mecanismo Odoo. Odoo valida el registro de modelos vía ``_auto_init``/el
setup del ORM al cargar addons; no tiene un registro **declarativo** de
checks equivalente al de Django (``django.core.checks``) del que portar un
símbolo. Declarado con esa razón en
``scripts/mirrored_roots_baseline.txt`` — el gate #334
(``check_mirrored_roots.py``) lo exige antes de que un archivo nuevo en una
raíz espejada quede "SIN CONTRAPARTE" sin más (H-API-578).

Por diseño debería vivir junto a los demás gates
(``scripts/check_system_checks.py``, hermano de ``check_urlconf.py``, que es
donde vivió en la rama ``feature/integrar-addons-faltantes-referencia``,
commits ``api@4c6e7e5``/``api@00e36b6``). Aterriza en ``src/orm/`` porque la
tarea #341 restringe los archivos escribibles a este; el archivo original de
``scripts/`` **no existe en esta rama** (ver ``Hallazgo H-API-677``, sección
"Estado heredado corregido") y no se recrea aquí por estar fuera del alcance
permitido. Consolidar ambos gates es la tarea #483.

Qué mide, y qué no
--------------------

*Métrica:* mensajes de nivel ``ERROR`` (40) o superior que devuelve
``django.core.checks.run_checks()`` sobre el registro de modelos poblado,
publicados junto a su denominador — ``len(apps.get_models())``. Un conteo sin
denominador no es un resultado (``hallazgo-abierto-genera-sucesor.md``): un
gate que valida 3 modelos y uno que valida 400 imprimirían el mismo ``OK``.

*Ciega a:* fallos de **runtime** dentro de un método (esto valida el cableado
declarativo — el registro de modelos y sus relaciones — no el cuerpo); a lo
que sólo aparece con la base de datos conectada (``databases=`` no se pasa: el
gate no depende de que PostgreSQL esté arriba); y a los ``WARNING``, que se
cuentan y se muestran pero **no** bloquean.

Nota de instrumento — ``fields.E307`` sólo existe en el registro GLOBAL. Leído
en ``django/core/checks/model_checks.py:225-226``: ``check_lazy_references``
ignora el ``app_configs`` que recibe y llama ``_check_lazy_references(apps)``
con el ``apps`` importado al top de ese módulo — siempre
``django.apps.apps``, nunca un registro aislado
(``django.test.utils.isolate_apps`` sustituye ``Options.default_apps``, no
ese import). Por eso un modelo con FK colgante creado dentro de
``isolate_apps`` dispara ``fields.E300`` (chequeo per-campo, sí ve el
registro que le corresponde a ese modelo) pero **nunca** ``fields.E307``
(chequeo global). ``dangling_fk_errors()`` filtra por el prefijo
``fields.E30`` precisamente para no depender de cuál de los dos dispara en
cada contexto — ver ``tests/unit/orm/test_checks_irresolvable_fk.py``.

Medido en este árbol (2026-08-18, ``feature/kaupamex-l0``): **327** modelos
registrados, **0** errores, **2** avisos (``fields.W342``, ajeno a este gate).

El hallazgo real detrás de H-API-584 — no es ``makemigrations`` en sí
-------------------------------------------------------------------------

``BaseCommand.execute()`` corre ``self.check()`` antes de ``self.handle()``
para todo comando con ``requires_system_checks`` no vacío — y
``makemigrations`` **no** lo sobreescribe: hereda ``"__all__"``
(``django/core/management/base.py:270``). Verificado en este árbol
(2026-08-18) invocando ``execute_from_command_line`` con un modelo real
apuntando a una cadena irresoluble: ``SystemCheckError`` se dispara ANTES de
escribir cualquier migración — la vía CLI (``python manage.py
makemigrations``) ya estaba protegida.

La brecha real es otra, y es más peligrosa porque es **silenciosa**:
``django.core.management.call_command()`` fija ``skip_checks=True`` por
defecto salvo que quien llama pase ``skip_checks=False`` explícitamente
(``django/core/management/__init__.py:192-193`` — literal:
``if "skip_checks" not in options: defaults["skip_checks"] = True``).
Verificado en este árbol (2026-08-18): la MISMA clase de modelo con la MISMA
FK irresoluble, invocada vía ``call_command('makemigrations', 'stock',
dry_run=True)`` en vez de la CLI, escribe el archivo de migración **sin
ningún error, sin excepción, sin aviso**.

Esto no es hipotético en este árbol: ``src/service/db.py`` ya invoca
``call_command('migrate', database=db_name, run_syncdb=True, ...)`` en tres
sitios (líneas 391, 415, 612) sin ``skip_checks=False`` — cualquier FK
irresoluble que entre por ahí se aplicaría en silencio contra una base real.
Repararlo queda fuera del alcance de este archivo (``db.py`` no está en el
set de archivos permitidos de la tarea #341); el sucesor es la tarea #484.

Uso
---

Antes de ``makemigrations`` en el procedimiento de porte, **siempre como
módulo** (``-m``), NUNCA como ruta de script::

    PYTHONPATH=src python3 -m orm.checks              # reporte + exit 1 si hay errores
    PYTHONPATH=src python3 -m orm.checks --quiet      # sólo el conteo

``python3 src/orm/checks.py`` (ruta directa) **falla siempre**, en cualquier
árbol — verificado en este pase: Python inserta el directorio del script
(``src/orm/``) al frente de ``sys.path`` antes de ejecutar una sola línea de
este módulo, y ``orm/types.py`` (mirror de ``odoo19c: odoo/orm/types.py``)
eclipsa entonces al ``types`` de la librería estándar. La cadena de imports de
``argparse`` (``re`` → ``enum`` → ``types``) revienta con
``ImportError: cannot import name 'GenericAlias'`` antes de llegar a
``_bootstrap_django()``. No es un defecto de este archivo — es la forma que
toma, aquí, la trampa genérica "un módulo de proyecto con el mismo nombre que
uno de la librería estándar" en cuanto su directorio entra a ``sys.path[0]``.

Para envolver una llamada programática a un comando de migración::

    from orm.checks import call_command_with_checks
    call_command_with_checks('migrate', database=db_name, run_syncdb=True)
"""
import argparse
import collections
import os
import sys

import django
from django.apps import apps
from django.core import checks as django_checks
from django.core.management import call_command as _django_call_command

# Importado al top del módulo, como el resto de `src/` — este archivo corre
# siempre bajo el intérprete del venv del proyecto (pytest, kaupamex-bin), a
# diferencia de los gates de `scripts/`, que corren bajo el `python3` del
# sistema y por eso necesitan re-lanzarse bajo el venv (ver la nota de
# ubicación en el docstring del módulo). No hace falta esa gimnasia aquí.


def _bootstrap_django():
    """Prepara ``sys.path`` + ``DJANGO_SETTINGS_MODULE`` para uso standalone.

    Sólo la llama :func:`main` (uso CLI). Idempotente: si ``django.setup()``
    ya corrió (pytest-django, otro llamador), ``apps.populate()`` retorna de
    inmediato (``ready`` ya es ``True``) — no repuebla ni reimporta modelos.
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src = os.path.join(root, 'src')
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.testing')
    django.setup()


class SystemCheckSummary:
    """Resultado de una corrida de ``run_checks()`` con su denominador.

    ``models_scanned`` es el denominador — cuántos modelos abarcó la corrida.
    Sin él, ``errors == []`` no distingue un árbol sano de un gate que no
    alcanzó a mirar nada.
    """

    def __init__(self, messages, models_scanned):
        self.messages = list(messages)
        self.models_scanned = models_scanned
        self.errors = [m for m in self.messages if m.level >= django_checks.ERROR]
        self.warnings = [
            m for m in self.messages
            if django_checks.WARNING <= m.level < django_checks.ERROR
        ]

    def dangling_fk_errors(self):
        """El subconjunto que es específicamente una FK irresoluble.

        ``fields.E300`` — el destino no existe en ningún addon instalado.
        ``fields.E307`` — la referencia perezosa nunca se resolvió (la misma
        causa, reportada desde el otro lado del mecanismo de resolución
        diferida). Ambos IDs cubren el caso que originó H-API-584/H-API-583.
        """
        return [m for m in self.errors if (m.id or '').startswith('fields.E30')]

    def render(self, quiet=False):
        """Texto del reporte, en el mismo formato que consumía el gate previo."""
        lines = []
        if not self.errors:
            lines.append(
                f'OK: system checks sin errores '
                f'({self.models_scanned} modelos registrados, '
                f'{len(self.warnings)} avisos)'
            )
            return '\n'.join(lines)

        by_id = collections.Counter(m.id or '(sin id)' for m in self.errors)
        lines.append(
            f'FAIL: {len(self.errors)} error(es) de system checks '
            f'(alcance medido: {self.models_scanned} modelos registrados)'
        )
        for ident, n in sorted(by_id.items()):
            lines.append(f'  {ident}: {n}')

        dangling = self.dangling_fk_errors()
        if dangling:
            lines.append('')
            lines.append(
                f'  {len(dangling)} de esos son FK irresolubles '
                f'(fields.E300/E307) — ver H-API-584.'
            )

        if not quiet:
            lines.append('')
            for m in self.errors:
                target = getattr(m, 'obj', None)
                lines.append(f'  [{m.id}] {target}: {m.msg}')

        return '\n'.join(lines)


def collect_system_check_summary(app_configs=None, tags=None,
                                  include_deployment_checks=False):
    """Corre ``checks.run_checks()`` y devuelve un :class:`SystemCheckSummary`.

    ``app_configs=None`` (el default) mide el registro **global**
    (``django.apps.apps``) — el mismo que usa ``manage.py check``. Se acepta
    un ``app_configs`` explícito para pruebas contra un registro aislado
    (``django.test.utils.isolate_apps``), aunque ese caso concreto es más
    directo probándolo contra ``Model.check()`` — ver
    ``tests/unit/orm/test_checks_irresolvable_fk.py``.
    """
    messages = django_checks.run_checks(
        app_configs=app_configs,
        tags=tags,
        include_deployment_checks=include_deployment_checks,
    )
    if app_configs is None:
        denominator = len(apps.get_models())
    else:
        denominator = sum(1 for ac in app_configs for _ in ac.get_models())
    return SystemCheckSummary(messages, denominator)


def run_checks_or_raise(app_configs=None, tags=None):
    """Corre los system checks y levanta ``SystemExit(1)`` si hay errores.

    Punto de entrada para invocarse explícitamente ANTES de
    ``makemigrations``/``migrate`` en cualquier procedimiento —CLI o
    programático— que no pase por el ``self.check()`` automático de
    ``BaseCommand.execute()`` (ver :func:`call_command_with_checks`, que es
    la forma recomendada de envolver una llamada programática).
    """
    summary = collect_system_check_summary(app_configs=app_configs, tags=tags)
    if summary.errors:
        print(summary.render(), file=sys.stderr)
        raise SystemExit(1)
    return summary


def call_command_with_checks(command_name, *args, _call_command=_django_call_command,
                              **options):
    """``call_command()`` que NO se salta los system checks por defecto.

    ``django.core.management.call_command()`` fija internamente
    ``skip_checks=True`` salvo que el llamador lo pase explícitamente
    (``django/core/management/__init__.py:192-193``, verificado en este
    árbol 2026-08-18) — así que cualquier ``call_command('makemigrations',
    ...)`` o ``call_command('migrate', ...)`` sin ese parámetro corre en
    silencio aunque el modelo tenga una FK irresoluble. Esta función invierte
    ese default: pasa ``skip_checks=False`` salvo que el llamador lo
    sobreescriba explícitamente.

    ``_call_command`` es un punto de inyección para pruebas (por defecto, el
    ``call_command`` real importado al top del módulo) — evita depender de
    parchear ``django.core.management.call_command`` en caliente, que un
    import perezoso tendría que resolver tarde para que el parche surtiera
    efecto (``no-lazy-imports.md`` lo prohíbe).
    """
    options.setdefault('skip_checks', False)
    return _call_command(command_name, *args, **options)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--quiet', action='store_true',
                     help='sólo el conteo, sin el detalle por mensaje')
    args = ap.parse_args(argv)

    _bootstrap_django()
    summary = collect_system_check_summary()
    print(summary.render(quiet=args.quiet),
          file=sys.stderr if summary.errors else sys.stdout)
    return 1 if summary.errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
