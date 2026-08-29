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


#: Los alias de Community declaran DOS raíces de addon; los de Enterprise, una.
#: No es simetría estética: en Community, ``odoo/addons`` es donde vive
#: ``base`` —el addon del que depende todo el porte— más los ``test_*`` del
#: propio framework. Solapamiento con ``addons/``: **0** en los dos.
#:
#: 18c declaraba UNA sola hasta 2026-08-28, y por eso ``base`` de 18 fue
#: invisible en toda medición de ese alias. No fue una decisión: 19c ya tenía
#: las dos y a 18c se le olvidó la segunda. Medido al corregirlo: 18c pasa de
#: 621 a 649 addons; los 28 que entran son ``base`` y 27 ``test_*``.
_DOS_RAICES = ('odoo19c', 'odoo18c')


def addons_de(alias='odoo19c'):
    """Las raíces de addon del alias. Community aporta dos; Enterprise, una.

    Los empaquetados sin alias de Enterprise 18 quedan fuera a propósito: son
    la misma población que ``odoo18e:`` y contarlos dos veces infla el universo
    (:ref:`h-api-76`).

    Y ``19.x/odoo19-enterprise-main/odoo19pro-main/`` tampoco es un alias, por
    la misma razón y con la medición hecha: comparte **715** addons con
    ``odoo19e`` sobre 716 propios, así que sumarlos casi duplica el universo.
    No son el mismo árbol empaquetado distinto —39 de 40 addons comunes
    difieren en contenido— sino dos cortes, y ``odoo19e`` es el posterior: en
    esos 40 hay **102** archivos que sólo están en él contra **7** que sólo
    están en ``pro``, y aporta 20 addons enteros de más (``hr_recruitment_ai``,
    ``l10n_br_edi_fiscal_reform``…) contra 1.
    """
    raiz = tree(alias)
    if alias in _DOS_RAICES:
        return [raiz / 'addons', raiz / 'odoo' / 'addons']
    return [raiz / 'addons'] if (raiz / 'addons').is_dir() else [raiz]


#: Addons cuyo nombre AQUI no es el de la referencia. Sin este mapa un gate no
#: encuentra la contraparte y publica ``0 pares``, que se lee igual que un porte
#: completo — el sub-patron D de ``metrica-decide-la-conclusion.md``.
#:
#: Cada entrada se verifico por SOLAPE DE ARCHIVOS, no por parecido de nombre:
#: un homonimo no es una contraparte. Comunes medidos: ldap 5 · oauth 6 ·
#: passkey 7 · password_policy 2 · signup 7 · timeout 9 · totp 7 · totp_mail 5.
#:
#: NO estan aqui, y no por olvido: ``authz``, ``authz_audit`` y ``authz_reauth``
#: no tienen contraparte de ningun nombre; ``helpdesk`` y ``sale_subscription``
#: viven en Enterprise 19 (otra raiz, otra licencia); ``auto_backup`` adapta
#: ``odoo18c: app_auto_backup``, que es otra version. Ninguno es un renombre:
#: son fuentes distintas, y forzarlos aqui mediria otra poblacion. Condicion de
#: cierre en la tarea #82.
ADDON_ALIAS = {
    'authz_ldap': 'auth_ldap',
    'authz_oauth': 'auth_oauth',
    'authz_passkey': 'auth_passkey',
    'authz_password_policy': 'auth_password_policy',
    'authz_signup': 'auth_signup',
    'authz_timeout': 'auth_timeout',
    'authz_totp': 'auth_totp',
    'authz_totp_mail': 'auth_totp_mail',
}


def addon_root(addon, alias='odoo19c'):
    """Raiz de un addon en la referencia, que NO tiene una sola forma.

    Community reparte sus addons en DOS raices —``addons/`` y
    ``odoo/addons/``— y ``base``, el addon del que depende el arranque, vive en
    la segunda. Un gate que probara solo la primera dejaba ``base`` fuera del
    alcance medido: 49 pares de archivo invisibles, todos con contraparte aqui,
    y sin nada que lo delatara porque un addon sin pares emite ``0 hallazgos``.

    Devuelve el candidato de la primera raiz aunque no exista, para que quien
    llama pueda decidir con ``.is_dir()`` en vez de recibir ``None``.
    """
    name = ADDON_ALIAS.get(addon, addon)
    raices = addons_de(alias)
    for root in raices:
        candidate = root / name
        if candidate.is_dir():
            return candidate
    return raices[0] / name


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
