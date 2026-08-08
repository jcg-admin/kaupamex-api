"""``mx`` — el plan contable mínimo para México.

Adaptación de ``odoo19c: l10n_mx/models/template_mx.py`` (addon ``l10n_mx``,
``odoo-tools@622ddc2aa5``), licencia **LGPL-3** — copia con atribución,
DEC-KX-03. En la referencia es un ``_inherit`` de ``account.chart.template``
con cuatro métodos decorados y un quinto que sobreescribe
``_get_accounts_data_values``; aquí es una **subclase** del cargador, mismo
criterio que ``template_generic_coa.py``: lo que allá es ``_inherit`` sobre
una clase de Python (no un modelo ORM) es aquí subclase con los mismos
métodos, porque el decorador ``@template`` se registra a sí mismo al
importarse — no hay barrido de clases que dependa de la herencia.

Las tablas del plan —140 cuentas, 5 posiciones fiscales, 1079 grupos, 138
impuestos, 14 grupos de impuesto; **1376 filas** en total— viven en
``account/data/template/<modelo>-mx.csv``, copiadas verbatim de la
referencia. Medición completa del addon en
``docs: gestion/pm/api/iniciativas/integrar-cfdi-mexico-nativo/
analisis-medicion-l10n-mx-bloque-0.rst``. Este módulo aporta lo que **no**
cabe en una tabla: el nombre del plan, los diarios base, y lo que el plan
escribe en la empresa.

Los cinco métodos de la referencia
====================================

- ``_get_mx_template_data`` → :func:`get_mx_template_data`.
- ``_get_mx_res_company`` → :func:`get_mx_res_company`.
- ``_get_mx_account_journal`` → :func:`get_mx_account_journal`.
- ``_get_mx_account_account`` → :func:`get_mx_account_account`.
- ``_get_accounts_data_values`` (override, **no** decorado con
  ``@template``) → :func:`add_mx_cash_difference_accounts`.

El quinto y su punto de extensión
-----------------------------------

Una versión anterior de este archivo lo declaraba bloqueado: ``TEMPLATE_REGISTRY``
compone **datos** por ``(código, modelo)``, y no había forma de que una
localización sobreescribiera un **método** del cargador —
``setup_utility_bank_accounts`` invoca ``cls.get_accounts_data_values(...)``
con ``cls == ChartTemplate``, así que declararlo en esta subclase no lo
enganchaba.

La medición era correcta y la conclusión —diferirlo— no: el punto de extensión
faltaba, y construirlo es lo que la regla ``porte-completo-no-parcial`` pide
cuando el stack no trae un mecanismo que la referencia sí usa. Se construyó
como ``ACCOUNTS_DATA_OVERRIDES`` + ``@accounts_data_override``
(``account/models/chart_template.py``), con la forma que la referencia tiene y
no la que resultaba cómoda: **una lista global de ajustes auto-guardados**, no
un registro por código de plan — porque en la referencia el ``_inherit`` se
instala para toda carga y la guarda por país vive **dentro** del método.

Sin ese ajuste, una empresa mexicana recibía las dos cuentas **genéricas** de
sobrante/faltante de efectivo, sin el código (``403.01.01`` / ``601.84.02``)
ni el nombre que el catálogo del SAT exige.
"""
from addons.account.models.chart_template import (
    ChartTemplate,
    accounts_data_override,
    template,
)
from tools.translate import _


class MxChartTemplate(ChartTemplate):
    """≙ el ``_inherit = "account.chart.template"`` de la referencia."""

    @template('mx')
    def get_mx_template_data(cls, template_code):
        """Los valores sueltos del plan — ≙ ``_get_mx_template_data``.

        ``code_digits: '9'`` no es un capricho: los códigos del CSV mexicano
        llevan puntos separadores (``102.01.01``) y miden exactamente 9
        caracteres — a diferencia del plan genérico, que usa dígitos puros a
        6 posiciones. ``normalize_account_codes`` rellena hasta este ancho.

        **Un valor de la referencia no se porta:**
        ``display_invoice_amount_total_words`` (booleano, importe en letras
        en la factura) — no tiene mecanismo de aterrizaje: no es un campo
        ``property_*`` ni lo lee ninguna función de este cargador
        (``grep -rn "amount_total_words" account/ l10n_mx/`` → 0). Es una
        bandera de la capa de reporte de factura, que este bloque no porta.
        """
        return {
            'code_digits': '9',
            'property_account_receivable_id': 'cuenta105_01',
            'property_account_payable_id': 'cuenta201_01',
            'property_stock_valuation_account_id': 'cuenta115_01',
            'property_cash_basis_base_account_id': 'cuenta801_01_99',
        }

    @template('mx', 'res.company')
    def get_mx_res_company(cls, template_code):
        """Lo que el plan escribe en la empresa — ≙ ``_get_mx_res_company``.

        La referencia escribe aquí **21** claves bajo
        ``{self.env.company.id: {...}}`` (indexado por empresa, idioma de un
        ORM multi-registro). Este puerto no tiene ese indexado —
        ``post_load_data`` ya recibe la empresa como parámetro— así que el
        dict es plano, mismo criterio que
        ``template_generic_coa.get_generic_coa_res_company``.

        De esas 21, **10 tienen campo donde aterrizar** en este árbol — las
        que siguen — y se portan.

        La décima es ``account_fiscal_country``, que hasta hoy figuraba entre
        las ausentes: se portó junto con el catálogo de países
        (:ref:`h-api-360`). No es cosmética — es la que hace que el plan
        mexicano deje a la empresa **con México como país fiscal**, y de ahí
        depende que :func:`add_mx_cash_difference_accounts` reconozca a esa
        empresa como mexicana. El valor ``'base.mx'`` es el identificador
        externo que siembra ``base/0017``.

        Las otras 11 (``anglo_saxon_accounting``,
        ``account_default_pos_receivable_account_id``,
        ``income_currency_exchange_account_id``,
        ``expense_currency_exchange_account_id``,
        ``deferred_expense_account_id``,
        ``tax_cash_basis_journal_id``, ``expense_account_id``,
        ``income_account_id``, ``account_cash_basis_base_account_id``,
        ``account_stock_journal_id``, ``account_stock_valuation_id``) no
        tienen columna en ``ResCompany`` a HEAD — ``post_load_data``
        las descarta en silencio por diseño, mismo mecanismo que
        ``template_generic_coa.py`` ya documenta: entran solas cuando su
        campo llegue. Las cierra la tarea **#137** (mapeo del Bloque 1 campo
        por campo), que es su sucesor real: a diferencia del país fiscal,
        ninguna de las 11 es una FK simple con un fallback de una línea —
        todas nombran cuentas o diarios cuyo eje sigue en decisión.

        **Nombres de clave sin sufijo** ``_id``: a diferencia de
        :func:`get_mx_account_journal` y :func:`get_mx_account_account`, el
        camino ``res.company`` de ``post_load_data`` compara contra el
        **nombre exacto** del campo (``key not in model_fields``, un
        ``set``) — no pasa por ``map_field_name``. Escribir
        ``account_sale_tax_id`` en vez de ``account_sale_tax`` haría que la
        clave nunca calzara y se descartara igual que las 12 sin campo.
        """
        return {
            'account_fiscal_country': 'base.mx',
            'bank_account_code_prefix': '102.01.0',
            'cash_account_code_prefix': '101.01.0',
            'transfer_account_code_prefix': '102.01.01',
            'account_journal_early_pay_discount_loss_account': 'cuenta402_01',
            'account_journal_early_pay_discount_gain_account': 'cuenta503_01',
            'account_sale_tax': 'tax12',
            'account_purchase_tax': 'tax14',
            'l10n_mx_income_return_discount_account': 'cuenta402_01',
            'l10n_mx_income_re_invoicing_account': 'cuenta402_04',
        }

    @template('mx', 'account.journal')
    def get_mx_account_journal(cls, template_code):
        """Los dos diarios propios del plan mexicano — ≙ ``_get_mx_account_journal``.

        DIVERGENCIA DECLARADA — ``'cash'`` lleva ``code`` explícito. La
        referencia lo deja en blanco porque su ORM genera el código de un
        diario tipo ``cash``/``bank`` sin código
        (``_get_next_journal_default_code``); este cargador no tiene ese
        mecanismo — sólo lo suple a mano para ``'bank'`` en
        ``account: models/chart_template.py`` (comentario de
        ``get_account_journal``: *"Aquí se escribe ese valor"*). Se aplica el
        mismo criterio aquí: sin código explícito, ``AccountJournal.code``
        (``max_length=12``, sin ``blank=True``) quedaría vacío y colisionaría
        con la restricción ``unique_journal_code_company`` en cuanto
        existiera un segundo diario sin código para la misma empresa.
        """
        return {
            'cbmx': {
                'type': 'general',
                'name': 'Pagado efectivamente',
                'code': 'CBMX',
                'default_account_id': 'cuenta118_01',
                'show_on_dashboard': True,
            },
            'cash': {
                'name': 'Efectivo',
                'type': 'cash',
                'code': 'CASH',
            },
        }

    @template('mx', 'account.account')
    def get_mx_account_account(cls, template_code):
        """Ajustes a una cuenta ya creada por el CSV — ≙ ``_get_mx_account_account``.

        ``cuenta115_01`` es la cuenta de valuación de inventario
        (``property_stock_valuation_account_id`` en
        :func:`get_mx_template_data`); la referencia le cuelga además sus
        cuentas de gasto y variación de inventario.

        Ninguna de las dos tiene columna en ``AccountAccount`` a HEAD
        (``grep -n "account_stock_expense\\|account_stock_variation"
        src/addons/account/models/account_account.py`` → 0 — la valuación de
        inventario contable no está en el alcance de este bloque). Se portan
        verbatim porque el mecanismo las descarta en silencio sin abortar la
        carga (``resolve_values``, mismo criterio que una columna de CSV sin
        destino) — no porque tengan dónde aterrizar hoy.
        """
        return {
            'cuenta115_01': {
                'account_stock_expense_id': 'cuenta505_01',
                'account_stock_variation_id': 'cuenta501_02',
            },
        }


@accounts_data_override
def add_mx_cash_difference_accounts(cls, company, accounts_data, template_data):
    """Las dos cuentas de diferencia de efectivo del SAT — ≙ el override de
    ``_get_accounts_data_values`` (``odoo19c: l10n_mx/models/template_mx.py:64-77``).

    La referencia no ata esto al plan ``mx`` sino al **país fiscal de la
    empresa**, y la guarda vive dentro del método. Se porta con la misma
    forma: un ajuste global auto-guardado, no una entrada del registro por
    código de plan. Ver ``ACCOUNTS_DATA_OVERRIDES``.

    Los códigos son literales del catálogo del SAT —``403.01.01`` para el
    sobrante, ``601.84.02`` para el faltante— y por eso **reemplazan** la
    entrada completa en vez de fusionarse con ella: la genérica se declara por
    ``prefix``, y dejar el prefijo junto al código haría que
    ``resolve_account_code`` buscara un hueco libre ignorando el código que el
    SAT exige.

    DIVERGENCIA HEREDADA, no introducida: al reemplazar la entrada se pierde
    ``tags: account.account_tag_investing``, que la genérica sí lleva
    (``account: chart_template.py``). Ocurre igual en la referencia —su
    ``accounts_data.update({...})`` reemplaza el valor entero— y se porta así
    a propósito: cambiarlo aquí divergiría del comportamiento de la fuente sin
    una decisión que lo respalde.
    """
    if getattr(company.account_fiscal_country, 'code', None) != 'MX':
        return
    accounts_data.update({
        'default_cash_difference_income_account': {
            'name': _('Otros ingresos'),
            'code': '403.01.01',
        },
        'default_cash_difference_expense_account': {
            'name': _('Pérdida por diferencia de efectivo'),
            'code': '601.84.02',
        },
    })
