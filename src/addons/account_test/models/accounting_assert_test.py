r"""``accounting.assert.test`` — pruebas manuales de consistencia contable.

Adaptación de ``addons/account_test/models/accounting_assert_test.py`` +
``addons/account_test/report/report_account_test.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``,
LGPL-3 — atribución y aviso de licencia preservados, DEC-KX-03).

Qué hace la referencia
=======================

Un modelo simple (``accounting.assert.test``: ``name``/``desc``/``code_exec``/
``active``/``sequence``) guarda consultas SQL+Python escritas por un
administrador. Al pedir el reporte (menú *Reporting → Accounting Tests*),
``report.account_test.report_accounttest._execute_code`` evalúa
``code_exec`` con ``safe_eval(..., mode="exec")`` contra un contexto acotado
(``cr``, ``uid``, el helper ``reconciled_inv()``, y las variables de salida
``result``/``column_order``), y formatea el resultado para el PDF QWeb.

Nueve símbolos en los dos archivos de la referencia; los nueve se portan
==========================================================================

Conteo (``grep -cE "^    [a-z_]+ *= *fields\.|^    def " models/
accounting_assert_test.py`` → 5; ``grep -cE "^    def |^        def "
report/report_account_test.py`` → 4 — incluye las dos closures anidadas):

===================================  =====  =========================================
Símbolo (archivo)                     Tipo   Destino en este archivo
===================================  =====  =========================================
``name``/``desc``/``code_exec``/
``active``/``sequence`` (modelo)      campo  Campos de ``AccountingAssertTest`` (abajo)
``_execute_code``                     método ``execute_code()`` (módulo, función libre)
``_get_report_values``                método ``AccountingAssertTest.run()`` +
                                              ``controllers/views.py`` (sin QWeb/PDF,
                                              ver la sección "Report → controlador")
``reconciled_inv()`` (closure)         función ``reconciled_inv()`` (módulo)
``order_columns()`` (closure)          función ``order_columns()`` (módulo)
===================================  =====  =========================================

``report`` → ``controllers`` + método de modelo (mapeo declarado)
======================================================================

La referencia hospeda el motor de ejecución en un ``report.*``
``AbstractModel`` porque su único consumidor es el botón *Imprimir* del
cliente web (QWeb → PDF). Esta plataforma no tiene motor QWeb/PDF (ver
``docs: source/backend/adr/`` — sin ADR de reporting PDF), así que el mapeo
fiel es: el **motor** (``_execute_code``) vive como función libre + método de
instancia (``run()``), y la **superficie** (``_get_report_values``, que en la
referencia arma el contexto para la plantilla) se convierte en un endpoint
DRF (``controllers/views.py::AccountingAssertTestViewSet.run``) que devuelve
JSON en vez de renderizar HTML→PDF. El layout de directorios pedido para
este porte es ``models/, controllers/, data/, security/`` — sin ``report/`` —
y este mapeo es la razón: la responsabilidad de "reporte" se reparte entre
el modelo (cálculo) y el controlador (superficie HTTP), como en el resto de
addons de este árbol (p. ej. ``account_debit_note``, cuyo docstring aplica el
mismo criterio para wizards sin vista QWeb).

``report/report_account_test_templates.xml`` (plantilla QWeb del PDF) y el
``<record model="ir.actions.report">`` de
``report/accounting_assert_test_reports.xml`` **NO tienen equivalente**: son
artefactos del cliente web de Odoo — mismo criterio que las vistas XML de
``account_debit_note`` (ver su docstring, "views/ ... NO se portan"). La
*capacidad* de negocio que declaran (ejecutar la prueba y ver su resultado)
sí se porta íntegra, como el endpoint ``run`` del ViewSet.

``security/ir.model.access.csv`` — colapsado a UNA capacidad (divergencia declarada)
==========================================================================================

La referencia da dos niveles: ``base.group_system`` (admin de sistema) con
``perm_read=1, perm_unlink=1`` (nunca ``write``/``create`` — ni el admin
puede editar/crear desde la UI, sólo ver y borrar) y
``account.group_account_manager`` con sólo ``perm_read=1``. Este ORM no
tiene grupos jerárquicos; se colapsa a UNA capacidad DEC-11
(``finance.diagnostics``, ``is_sensitive=True`` — ver
``security/authz_catalog.py``) que gobierna ``list``/``retrieve``/``run``/
``destroy`` por igual. La asimetría lectura-amplia vs. borrado-restringido de
la referencia no se replica (fuera de alcance: requeriría un segundo nivel de
capacidad que el catálogo DEC-11 no modela hoy para este dominio) — declarado
aquí, no omitido en silencio.
"""
from django.db import connection

import fields
from addons.account.models.account_move import AccountMove
from addons.base.models import TimeStampedModel
from addons.account_test.tools.safe_eval_exec import safe_eval
from tools.translate import _

#: ≙ ``CODE_EXEC_DEFAULT`` de la referencia — el valor por defecto del campo
#: ``code_exec`` para una prueba nueva, verbatim (dato, no símbolo de
#: comportamiento).
CODE_EXEC_DEFAULT = '''\
res = []
cr.execute("select id, code from account_journal")
for record in cr.dictfetchall():
    res.append(record['code'])
result = res
'''

#: Códigos de ``account.account_type`` que la referencia trata como
#: payable/receivable (``odoo19c: account_account.py:44-68``) — usados por
#: ``reconciled_inv()`` para el mismo filtro que la referencia expresa vía
#: ``a.account_type in ('asset_receivable','liability_payable')``.
_RECEIVABLE_PAYABLE_TYPES = ('asset_receivable', 'liability_payable')


class AccountingAssertTest(TimeStampedModel):
    """``accounting.assert.test`` — una prueba de consistencia guardada."""

    name = fields.Char(
        max_length=255,
        help_text='Nombre de la prueba (Odoo name, required, translate).',
    )
    desc = fields.Text(
        blank=True, default='',
        help_text='Descripción de la prueba (Odoo desc, translate).',
    )
    code_exec = fields.Text(
        default=CODE_EXEC_DEFAULT,
        help_text='Código Python/SQL a ejecutar — DEBE fijar la variable '
                  '`result` (lista/dict) y opcionalmente `column_order` '
                  '(Odoo code_exec, required).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Archivada sin borrar (Odoo active).',
    )
    sequence = fields.Integer(
        default=10,
        help_text='Orden de presentación (Odoo sequence).',
    )

    class Meta:
        db_table = 'account_test_accounting_assert_test'
        ordering = ['sequence', 'id']
        verbose_name = 'Prueba de consistencia contable'
        verbose_name_plural = 'Pruebas de consistencia contable'

    def __str__(self) -> str:
        return self.name

    def run(self):
        """≙ el tramo de ``_get_report_values`` que invoca
        ``execute_code`` sobre ESTE registro.

        :return: tupla ``(passed, lines)`` — ver ``execute_code()``.
        """
        return execute_code(self.code_exec)


class _CursorLike:
    """Envoltorio mínimo sobre un cursor de ``django.db.connection`` — el
    ``cr`` (cursor psycopg2) que la referencia expone al código de prueba.

    Sólo cubre lo que ``code_exec`` de los 6 registros semilla usa:
    ``execute(sql, params=None)`` y ``dictfetchall()`` (≙
    ``odoo19c: sql_db.py::Cursor.dictfetchall``, el mismo nombre — no es un
    método nativo de psycopg/Django, cada quien lo define igual).
    """

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        self._cursor.execute(sql, params)

    def dictfetchall(self):
        columns = [col[0] for col in self._cursor.description]
        return [dict(zip(columns, row)) for row in self._cursor.fetchall()]


def reconciled_inv():
    """≙ la closure ``reconciled_inv()`` de ``_execute_code`` — *"devuelve la
    lista de facturas marcadas como reconciled = True"*.

    Divergencia declarada: la referencia lee ``account.move.reconciled``
    (booleano). Ese campo está **DEFERIDO** en este árbol —
    ``account/models/account_move_line.py`` (propio docstring): *"
    amount_residual / reconciled (booleano derivado) quedan DEFERIDOS:
    dependen de amount_currency multi-moneda que este modelo no porta
    todavía"* — y ``account.move`` tampoco lo tiene. Tocar ``account`` para
    agregarlo está fuera de este alcance ("no tocar ningún otro addon").

    Sustituto construido con lo que SÍ existe: ``account.move.line.
    full_reconcile`` (FK a ``account.AccountFullReconcile``, no-nulo cuando
    el apunte quedó totalmente conciliado — el mismo evento que el booleano
    ``reconciled`` de la referencia representa, sólo que aquí se lee de la
    relación en vez de un campo derivado). Se filtran las líneas cuya cuenta
    es payable/receivable, igual que la referencia filtra
    ``a.account_type in (...)`` en ``account_test_05``.
    """
    return list(
        AccountMove.objects
        .filter(
            line_ids__account__account_type__in=_RECEIVABLE_PAYABLE_TYPES,
            line_ids__full_reconcile__isnull=False,
        )
        .values_list('id', flat=True)
        .distinct()
    )


def order_columns(item, cols=None):
    """≙ ``order_columns()`` — muestra un dict como lista de tuplas
    ``(campo, valor)`` en el orden de ``cols`` (o el orden natural del dict
    si no se especifica). Función pura, sin dependencia de esquema."""
    if cols is None:
        cols = list(item)
    return [(col, item.get(col)) for col in cols if col in item]


#: ≙ el mensaje de éxito por defecto que la referencia inserta cuando
#: ``result`` queda vacío (``odoo19c: report_account_test.py:53``).
SUCCESS_MESSAGE = 'La prueba se aprobó exitosamente'


def execute_code(code_exec):
    """≙ ``_execute_code`` — ejecuta el código guardado y devuelve el
    veredicto + las líneas de resultado, formateadas para presentación.

    La referencia señaliza éxito/fallo con el CONTENIDO de una única lista
    (``result`` vacío → un mensaje fijo de éxito; no-vacío → las filas del
    fallo). Aquí se separa en dos valores —``passed``/``lines``— para que el
    contrato DRF (``AccountingAssertTestRunResultSerializer``) no dependa de
    comparar el mensaje traducido como si fuera un sentinel: la traducción
    (``tools.translate._`` = ``gettext_lazy``) cambia con el locale, así que
    comparar contra el string sería frágil. El VEREDICTO es el mismo que
    calcula la referencia (``result`` vacío ⇒ éxito); sólo cambia CÓMO se
    lo comunica al llamador.

    :param code_exec: el texto de ``AccountingAssertTest.code_exec``.
    :return: tupla ``(passed: bool, lines: list[str])``. ``lines`` es
        ``[SUCCESS_MESSAGE]`` cuando ``passed`` es ``True`` — mismo texto que
        la referencia mostraría en el PDF.
    """
    with connection.cursor() as cursor:
        context = {
            'cr': _CursorLike(cursor),
            'reconciled_inv': reconciled_inv,
            'result': None,
            'column_order': None,
            '_': _,
        }
        safe_eval(code_exec, context, mode='exec')
        result = context['result']
        column_order = context.get('column_order')

    if not isinstance(result, (tuple, list, set)):
        result = [result]
    if not result:
        return True, [str(_(SUCCESS_MESSAGE))]

    def _format(item):
        if isinstance(item, dict):
            return ', '.join(
                '%s: %s' % tup for tup in order_columns(item, column_order)
            )
        # Divergencia declarada: la referencia devuelve `item` tal cual
        # (incluso listas anidadas — algunos registros semilla hacen
        # `result.append(cr.dictfetchall())`, ver `data/
        # accounting_assert_tests.py`), porque su consumidor es una
        # plantilla QWeb que coacciona a texto implícitamente. Aquí el
        # consumidor es JSON (`AccountingAssertTestRunResultSerializer.
        # result` = lista de `str`), así que se coacciona explícitamente.
        return str(item)
    return False, [_format(rec) for rec in result]
