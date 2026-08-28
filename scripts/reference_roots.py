"""Las raíces de la REFERENCIA — declaradas una vez, consultadas por los gates.

Gemelo de ``addons_roots.py``, que hace lo mismo para las nuestras y ya dejó
escrita la razón: *"cada gate con su copia de la ruta es exactamente la segunda
fuente de verdad que ``calibration-verified-numbers.md`` prohíbe, y su modo de
fallo es silencioso: un gate que apunta a una raíz vacía publica ``0
incumplidores`` y parece sano"*. Ese cero ya se pagó una vez
(:ref:`h-api-335`).

**Medido antes de escribir este módulo (2026-08-28):** nueve guiones de
``scripts/`` codificaban la ruta de ``odoo19c`` a mano, con diez ocurrencias
literales. Seis la envolvían en ``os.environ.get('ODOO19C', <literal>)`` y tres
ni eso. El árbol está **triplicado** en ``odoo-tools``
(``19.x/odoo-19.0/odoo-19.0/odoo-19.0/``) — artefacto de empaquetado, no
diseño, y por tanto candidato a aplanarse. El día que se aplane, diez sitios se
rompen; con este módulo, uno.

Los alias son los de ``docs: convencion-cita-referencia-odoo.rst``. El del
árbol es la RAÍZ (donde viven ``odoo/`` y ``addons/``); ``addons_de()`` da las
raíces de addon, que en 19c son **dos** porque el núcleo (``base``, ``web``…)
vive en ``odoo/addons/`` y no en ``addons/``.

Sobreescribible por entorno: ``ODOO19C=/otra/ruta python3 scripts/<gate>.py``.
"""
import os
import pathlib

#: La raíz del repo de referencia. Sólo-lectura por regla — ver
#: ``referencia-odoo-gobierna-las-decisiones.md``: ni ``checkout``, ni
#: ``add``, ni edición de archivo.
TOOLS_ROOT = pathlib.Path(os.environ.get('ODOO_TOOLS', '/home/user/odoo-tools'))
_TOOLS = TOOLS_ROOT

#: alias → raíz del árbol. La forma la fija la convención de cita, no este
#: archivo: si el repo de referencia se reorganiza, se corrige aquí y en ningún
#: otro sitio.
TREE_ROOTS = {
    'odoo19c': _TOOLS / '19.x' / 'odoo-19.0' / 'odoo-19.0' / 'odoo-19.0',
    'odoo19e': _TOOLS / '19.x' / 'odoo19-enterprise-main'
    / 'odoo19-enterprise-main' / 'odoo19-enterprise-main',
    'odoo18c': _TOOLS / '18.x' / 'odoo-18',
    'odoo18e': _TOOLS / '18.x' / 'odoo.enterprise',
}

#: Variable de entorno que sobreescribe cada alias, una por alias.
_ENV = {alias: alias.upper() for alias in TREE_ROOTS}


def tree(alias='odoo19c'):
    """La raíz del árbol del alias, con el entorno ganando sobre el default."""
    if alias not in TREE_ROOTS:
        raise KeyError(
            f'alias desconocido: {alias!r}. Los de la convención son '
            f'{sorted(TREE_ROOTS)}.'
        )
    return pathlib.Path(os.environ.get(_ENV[alias], str(TREE_ROOTS[alias])))


def addons_de(alias='odoo19c'):
    """Las raíces de addon del alias. 19c aporta dos; el resto, una.

    Los empaquetados sin alias de Enterprise 18 quedan fuera a propósito: son
    la misma población que ``odoo18e:`` y contarlos dos veces infla el universo
    (:ref:`h-api-76`).
    """
    raiz = tree(alias)
    if alias == 'odoo19c':
        return [raiz / 'addons', raiz / 'odoo' / 'addons']
    return [raiz / 'addons'] if (raiz / 'addons').is_dir() else [raiz]


def require(alias='odoo19c'):
    """La raíz, o un error ruidoso. NUNCA devuelve una ruta que no existe.

    El guard es el punto: un gate que recorre una raíz ausente encuentra cero
    archivos y publica ``0 incumplidores``. Ese verde no distingue *"no hay
    defectos"* de *"medí un directorio vacío"* — el sub-patrón D de
    ``metrica-decide-la-conclusion.md``.
    """
    raiz = tree(alias)
    if not raiz.is_dir():
        raise SystemExit(
            f'ERROR — la raíz de {alias} no está en {raiz}.\n'
            'NO se emite conteo: un 0 medido contra un directorio ausente '
            'sería un verde falso. Consultar odoo-tools o exportar '
            f'{_ENV[alias]}=<ruta>.'
        )
    return raiz


def _env_exports():
    """Las líneas ``export`` para usar los alias desde la shell."""
    for alias in sorted(TREE_ROOTS):
        yield f'export {_ENV[alias]}={tree(alias)}'


if __name__ == '__main__':
    import sys

    if '--env' in sys.argv:
        # eval "$(python3 scripts/reference_roots.py --env)"
        print('\n'.join(_env_exports()))
    else:
        for alias in sorted(TREE_ROOTS):
            raiz = tree(alias)
            marca = 'presente' if raiz.is_dir() else 'AUSENTE'
            print(f'{alias:9} {marca:9} {raiz}')
            for a in addons_de(alias):
                n = len(list(a.glob('*/__manifest__.py'))) if a.is_dir() else 0
                print(f'{"":9} {"":9}   addons: {n:4}  {a}')
