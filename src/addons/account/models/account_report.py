"""``account.report`` y sus cuatro satélites — el **árbol declarativo** de un
reporte contable (Odoo ``account``).

Adaptación de Odoo ``addons/account/models/account_report.py``
(odoo-tools@622ddc2a, odoo19c:, LGPL-3) — atribución y aviso de licencia
preservados (DEC-KX-03).

Cinco modelos, una jerarquía: un ``AccountReport`` tiene ``lines`` y
``columns``; cada línea tiene ``expressions``; una expresión puede recibir
valores externos (``AccountReportExternalValue``) que no salen del libro
mayor sino que se cargan a mano (ajustes de cierre, valores de declaración).

Qué es y qué NO es este porte
==============================

Lo que se porta es la **declaración** del reporte: su forma, sus columnas,
sus líneas jerárquicas, y la fórmula de cada expresión **como dato**. Eso es
lo que la Ola A pide (modelo + migración), y es lo que hace que un reporte
sea configurable en vez de estar cableado en Python.

Lo que **no** se porta en este pase es el **motor de evaluación**: los seis
engines que la referencia implementa para resolver una fórmula contra el
libro mayor (``domain``, ``tax_tags``, ``aggregation``, ``account_codes``,
``external``, ``custom``), sus tres regex de parsing
(``ACCOUNT_CODES_ENGINE_TERM_REGEX``, ``AGGREGATION_ENGINE_FORMULA_REGEX``,
``DOMAIN_REGEX``) y el arrastre entre periodos (*carryover*). Son ~700 de las
967 líneas del archivo de referencia y consultan
``account.move.line`` — es un subsistema de cálculo, no de esquema.

El campo ``engine`` se porta con sus **seis** valores fieles precisamente
para que la declaración no mienta: un reporte sembrado con
``engine='account_codes'`` describe correctamente cómo debe calcularse,
aunque el evaluador todavía no exista. Lo contrario —recortar el enum a lo
implementado— fabricaría una forma que la referencia no tiene y obligaría a
migrar los datos al añadir el motor.

**Lo que este archivo no cierra:** el motor de evaluación. Registrado como
la tarea #136; hasta que exista, un ``AccountReport`` es una plantilla
almacenada, no un reporte ejecutable.

Divergencias declaradas (DEC-KX-03)
====================================

1. **Los ``compute`` de herencia no se portan como recálculo automático.**
   Casi todos los ``filter_*`` de la referencia se calculan con
   ``_compute_report_option_filter(...)``: heredan el valor del
   ``root_report`` o del reporte-sección padre, y sólo si no hay padre toman
   el default. Aquí se portan como **columnas con default**, y la herencia
   se expone en ``AccountReport.resolver_opcion()`` — un método explícito.
   Mismo criterio que ``account_reconcile_model.py`` (divergencia 4): una
   dependencia que cruza a otra fila no se recalcula en ``save()``, porque
   el padre puede no existir todavía cuando se guarda el hijo.

2. **``chart_template`` es ``Char``, no ``Selection``.** En la referencia su
   ``selection`` es un *callable* que consulta
   ``account.chart.template._select_chart_template()`` en tiempo de
   ejecución (``odoo19c: account_report.py:65``). Un ``choices`` de Django se
   congela en la migración, así que un enum aquí fabricaría un catálogo
   cerrado donde la referencia tiene uno abierto. Se valida contra el
   catálogo real cuando ``account.chart.template`` se porte (T-A12).

3. **Los cuatro ``*_formula`` de ``AccountReportLine`` no se portan.** Son
   ``store=False`` con ``inverse=`` (``odoo19c: account_report.py:391-396``):
   azúcar de formulario que escribe ``expression_ids`` y no persiste nada. Un
   campo no almacenado no tiene columna que portar; el equivalente es crear
   la expresión directamente.

4. **Los ``related`` de ``AccountReportExternalValue`` no se portan como
   columna.** ``target_report_line``, ``target_report_expression_label`` y
   ``report_country`` son ``related=`` de la referencia — proyecciones de un
   join, no dato propio. Se navegan por la FK.
"""
import fields
import models

# odoo19c: account_report.py:11-20 — FIGURE_TYPE_SELECTION_VALUES.
FIGURE_TYPES = [
    ('monetary', 'Monetario'),
    ('percentage', 'Porcentaje'),
    ('integer', 'Entero'),
    ('float', 'Decimal'),
    ('date', 'Fecha'),
    ('datetime', 'Fecha y hora'),
    ('boolean', 'Booleano'),
    ('string', 'Texto'),
]

# odoo19c: account_report.py:74 — availability_condition.
AVAILABILITY_CONDITIONS = [
    ('country', 'Coincide el país'),
    ('coa', 'Coincide el plan de cuentas'),
    ('always', 'Siempre'),
]

# odoo19c: account_report.py:81 — integer_rounding.
INTEGER_ROUNDINGS = [
    ('HALF-UP', 'Al más cercano'),
    ('UP', 'Hacia arriba'),
    ('DOWN', 'Hacia abajo'),
]

# odoo19c: account_report.py:89-98 — default_opening_date_filter.
OPENING_DATE_FILTERS = [
    ('this_year', 'Este año'),
    ('this_quarter', 'Este trimestre'),
    ('this_month', 'Este mes'),
    ('today', 'Hoy'),
    ('previous_month', 'Mes anterior'),
    ('previous_quarter', 'Trimestre anterior'),
    ('previous_year', 'Año anterior'),
    ('this_return_period', 'Este periodo de declaración'),
    ('previous_return_period', 'Periodo de declaración anterior'),
]

# odoo19c: account_report.py:107-111 — currency_translation.
CURRENCY_TRANSLATIONS = [
    ('current', 'Tipo de cambio más reciente a la fecha del reporte'),
    ('cta', 'Usar CTA'),
]

# odoo19c: account_report.py:121-124 — filter_multi_company.
MULTI_COMPANY_FILTERS = [
    ('selector', 'Selector de empresa'),
    ('tax_units', 'Unidades fiscales'),
]

# odoo19c: account_report.py:148 y :174 — filter_hide_0_lines / filter_hierarchy.
TRISTATE_FILTERS = [
    ('by_default', 'Activo por defecto'),
    ('optional', 'Opcional'),
    ('never', 'Nunca'),
]

# odoo19c: account_report.py:180 — filter_account_type.
ACCOUNT_TYPE_FILTERS = [
    ('both', 'Por pagar y por cobrar'),
    ('payable', 'Por pagar'),
    ('receivable', 'Por cobrar'),
    ('disabled', 'Desactivado'),
]

# odoo19c: account_report.py:589-596 — engine. Los seis, aunque el evaluador
# no exista todavía (ver "Qué es y qué NO es este porte").
EXPRESSION_ENGINES = [
    ('domain', 'Dominio Odoo'),
    ('tax_tags', 'Etiquetas de impuesto'),
    ('aggregation', 'Agregación de otras fórmulas'),
    ('account_codes', 'Prefijo de códigos de cuenta'),
    ('external', 'Valor externo'),
    ('custom', 'Función Python a medida'),
]

# odoo19c: account_report.py:602-611 — date_scope.
DATE_SCOPES = [
    ('from_beginning', 'Desde el inicio absoluto'),
    ('from_fiscalyear', 'Desde el inicio del ejercicio fiscal'),
    ('to_beginning_of_fiscalyear', 'Al inicio del ejercicio fiscal'),
    ('to_beginning_of_period', 'Al inicio del periodo'),
    ('strict_range', 'Estrictamente en las fechas dadas'),
    ('previous_return_period', 'Del periodo de declaración anterior'),
]

# odoo19c: account_report.py:396 — horizontal_split_side.
HORIZONTAL_SPLIT_SIDES = [
    ('left', 'Izquierda'),
    ('right', 'Derecha'),
]


class AccountReport(models.Model):
    """``account.report`` — la declaración de un reporte contable."""

    name = fields.Char(
        max_length=255,
        help_text='Nombre del reporte (Odoo name, requerido, traducible).',
    )
    sequence = fields.Integer(
        default=0, help_text='Orden de presentación (Odoo sequence).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Reporte disponible; desactivar lo archiva sin borrarlo '
                  '(Odoo active).',
    )
    root_report = fields.Many2one(
        'account.AccountReport', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='variants',
        help_text='Reporte del que este es una variante — la variante '
                  'hereda sus opciones (Odoo root_report_id).',
    )
    section_reports = fields.Many2many(
        'account.AccountReport', blank=True,
        symmetrical=False, related_name='section_main_reports',
        db_table='account_report_section_rel',
        help_text='Sub-reportes que componen este reporte compuesto (Odoo '
                  'section_report_ids, relación account_report_section_rel). '
                  'symmetrical=False porque la relación es dirigida: la '
                  'referencia declara los dos sentidos como campos distintos '
                  'con column1/column2 invertidos (odoo19c: '
                  'account_report.py:58-59), y un M2M reflexivo de Django es '
                  'simétrico por defecto — dejarlo así fundiría "contiene" '
                  'con "está contenido en".',
    )
    use_sections = fields.Boolean(
        default=False,
        help_text='Reporte compuesto por secciones navegables e imprimibles '
                  'a la vez (Odoo use_sections).',
    )
    chart_template = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Plan de cuentas al que aplica. Texto libre, no enum: en '
                  'la referencia el catálogo lo construye '
                  'account.chart.template en tiempo de ejecución (Odoo '
                  'chart_template; ver divergencia 2).',
    )
    country = fields.Many2one(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='account_reports',
        help_text='País cuya normativa describe el reporte (Odoo country_id).',
    )
    only_tax_exigible = fields.Boolean(
        default=False,
        help_text='Sólo considera apuntes con impuesto exigible (Odoo '
                  'only_tax_exigible).',
    )
    availability_condition = fields.Selection(
        max_length=8, choices=AVAILABILITY_CONDITIONS,
        blank=True, default='',
        help_text='Cuándo se ofrece el reporte al usuario (Odoo '
                  'availability_condition).',
    )
    load_more_limit = fields.Integer(
        default=0,
        help_text='Filas por página antes de "cargar más"; 0 = sin límite '
                  '(Odoo load_more_limit).',
    )
    search_bar = fields.Boolean(
        default=False,
        help_text='Muestra barra de búsqueda sobre el reporte (Odoo '
                  'search_bar).',
    )
    prefix_groups_threshold = fields.Integer(
        default=4000,
        help_text='Número de líneas a partir del cual se agrupa por prefijo '
                  'de código de cuenta (Odoo prefix_groups_threshold).',
    )
    integer_rounding = fields.Selection(
        max_length=8, choices=INTEGER_ROUNDINGS, blank=True, default='',
        help_text='Redondeo a entero al presentar importes (Odoo '
                  'integer_rounding).',
    )
    allow_foreign_vat = fields.Boolean(
        default=False,
        help_text='Admite posiciones fiscales con IVA extranjero (Odoo '
                  'allow_foreign_vat).',
    )
    default_opening_date_filter = fields.Selection(
        max_length=24, choices=OPENING_DATE_FILTERS, default='previous_month',
        help_text='Periodo preseleccionado al abrir el reporte (Odoo '
                  'default_opening_date_filter).',
    )
    currency_translation = fields.Selection(
        max_length=8, choices=CURRENCY_TRANSLATIONS, default='cta',
        help_text='Cómo se convierten importes en otra divisa (Odoo '
                  'currency_translation).',
    )

    # --- Filtros: qué menús ofrece el reporte -------------------------------
    # odoo19c: account_report.py:118-199. En la referencia casi todos son
    # compute con herencia del root_report; aquí son columnas con default y
    # la herencia se resuelve en resolver_opcion() (divergencia 1).
    filter_multi_company = fields.Selection(
        max_length=16, choices=MULTI_COMPANY_FILTERS, default='selector',
        help_text='Cómo se eligen las empresas incluidas (Odoo '
                  'filter_multi_company).',
    )
    filter_date_range = fields.Boolean(
        default=True, help_text='Ofrece rango de fechas (Odoo filter_date_range).',
    )
    filter_show_draft = fields.Boolean(
        default=False,
        help_text='Ofrece incluir asientos borrador (Odoo filter_show_draft).',
    )
    filter_unreconciled = fields.Boolean(
        default=False,
        help_text='Ofrece filtrar sólo apuntes no conciliados (Odoo '
                  'filter_unreconciled).',
    )
    filter_unfold_all = fields.Boolean(
        default=False,
        help_text='Ofrece desplegar todas las líneas (Odoo filter_unfold_all).',
    )
    filter_hide_0_lines = fields.Selection(
        max_length=12, choices=TRISTATE_FILTERS, default='optional',
        help_text='Ocultar líneas en cero (Odoo filter_hide_0_lines).',
    )
    filter_period_comparison = fields.Boolean(
        default=True,
        help_text='Ofrece comparar contra otro periodo (Odoo '
                  'filter_period_comparison).',
    )
    filter_growth_comparison = fields.Boolean(
        default=True,
        help_text='Ofrece la columna de crecimiento (Odoo '
                  'filter_growth_comparison).',
    )
    filter_journals = fields.Boolean(
        default=False, help_text='Ofrece filtrar por diario (Odoo filter_journals).',
    )
    filter_analytic = fields.Boolean(
        default=False,
        help_text='Ofrece filtrar por cuenta analítica (Odoo filter_analytic).',
    )
    filter_hierarchy = fields.Selection(
        max_length=12, choices=TRISTATE_FILTERS, default='optional',
        help_text='Agrupar por grupos de cuentas (Odoo filter_hierarchy).',
    )
    filter_account_type = fields.Selection(
        max_length=12, choices=ACCOUNT_TYPE_FILTERS, default='disabled',
        help_text='Filtro por tipo de cuenta (Odoo filter_account_type).',
    )
    filter_partner = fields.Boolean(
        default=False, help_text='Ofrece filtrar por contacto (Odoo filter_partner).',
    )
    filter_aml_ir_filters = fields.Boolean(
        default=False,
        help_text='Ofrece los filtros favoritos del usuario sobre apuntes '
                  '(Odoo filter_aml_ir_filters).',
    )
    filter_budgets = fields.Boolean(
        default=False, help_text='Ofrece comparar contra presupuesto (Odoo '
                                 'filter_budgets).',
    )

    class Meta:
        db_table = 'account_report'
        ordering = ['sequence', 'id']

    def resolver_opcion(self, nombre):
        """Valor efectivo de una opción, siguiendo la herencia de la referencia.

        La referencia calcula cada ``filter_*`` con
        ``_compute_report_option_filter`` (``odoo19c:
        account_report.py:200-215``): una variante hereda del ``root_report``,
        y una sección del reporte que la contiene. Aquí es un método porque
        la cadena cruza a otras filas — recalcularlo en ``save()`` leería un
        padre que puede no existir todavía (divergencia 1).
        """
        propio = getattr(self, nombre)
        if propio not in (None, '', False):
            return propio
        if self.root_report_id is not None:
            return self.root_report.resolver_opcion(nombre)
        principal = self.section_main_reports.first()
        if principal is not None:
            return principal.resolver_opcion(nombre)
        return propio


class AccountReportLine(models.Model):
    """``account.report.line`` — una fila jerárquica del reporte."""

    name = fields.Char(
        max_length=255,
        help_text='Etiqueta de la línea (Odoo name, requerido, traducible).',
    )
    report = fields.Many2one(
        'account.AccountReport', on_delete=models.CASCADE,
        related_name='lines',
        help_text='Reporte al que pertenece la línea (Odoo report_id).',
    )
    parent = fields.Many2one(
        'account.AccountReportLine', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='children',
        help_text='Línea padre en la jerarquía (Odoo parent_id).',
    )
    hierarchy_level = fields.Integer(
        default=0,
        help_text='Profundidad en la jerarquía; la referencia la deriva del '
                  'padre (Odoo hierarchy_level).',
    )
    sequence = fields.Integer(
        default=0, help_text='Orden dentro del reporte (Odoo sequence).',
    )
    code = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Identificador único de la línea dentro del reporte; lo '
                  'usan las fórmulas de agregación para referirse a ella '
                  '(Odoo code).',
    )
    groupby = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Campos de account.move.line, separados por coma, por los '
                  'que se subdivide la línea (Odoo groupby).',
    )
    user_groupby = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Agrupación elegida por el usuario, que sustituye a '
                  'groupby (Odoo user_groupby).',
    )
    foldable = fields.Boolean(
        default=False,
        help_text='La línea nace plegada y muestra botón de despliegue (Odoo '
                  'foldable).',
    )
    print_on_new_page = fields.Boolean(
        default=False,
        help_text='Esta línea y las siguientes se imprimen en página nueva '
                  '(Odoo print_on_new_page).',
    )
    action = fields.Many2one(
        'base.IrActionsActions', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='account_report_lines',
        help_text='Acción a ejecutar al pulsar la línea; si está puesta, la '
                  'línea es un enlace (Odoo action_id).',
    )
    hide_if_zero = fields.Boolean(
        default=False,
        help_text='Oculta la línea y sus hijas cuando todas sus columnas son '
                  'cero (Odoo hide_if_zero).',
    )
    horizontal_split_side = fields.Selection(
        max_length=8, choices=HORIZONTAL_SPLIT_SIDES, blank=True, default='',
        help_text='Lado en un reporte partido horizontalmente, p. ej. un '
                  'balance activo/pasivo (Odoo horizontal_split_side).',
    )

    class Meta:
        db_table = 'account_report_line'
        ordering = ['sequence', 'id']
        constraints = [
            # odoo19c: account_report.py:398-400 — _code_uniq.
            models.UniqueConstraint(
                fields=['report', 'code'],
                name='unique_account_report_line_code',
            ),
        ]


class AccountReportExpression(models.Model):
    """``account.report.expression`` — cómo se calcula una columna de una línea."""

    report_line = fields.Many2one(
        'account.AccountReportLine', on_delete=models.CASCADE,
        related_name='expressions',
        help_text='Línea a la que pertenece la expresión (Odoo '
                  'report_line_id).',
    )
    label = fields.Char(
        max_length=64,
        help_text='Etiqueta que empareja la expresión con una columna del '
                  'reporte (Odoo label, requerido).',
    )
    engine = fields.Selection(
        max_length=16, choices=EXPRESSION_ENGINES,
        help_text='Motor que resuelve la fórmula. Se declaran los seis de la '
                  'referencia aunque el evaluador aún no exista — recortar el '
                  'enum haría que la declaración mintiera (Odoo engine).',
    )
    formula = fields.Char(
        max_length=1024,
        help_text='Fórmula, interpretada según engine (Odoo formula, '
                  'requerido).',
    )
    subformula = fields.Char(
        max_length=1024, blank=True, default='',
        help_text='Modificador de la fórmula, p. ej. el signo o el ámbito '
                  '(Odoo subformula).',
    )
    date_scope = fields.Selection(
        max_length=32, choices=DATE_SCOPES, default='strict_range',
        help_text='Ventana temporal sobre la que se evalúa (Odoo date_scope).',
    )
    figure_type = fields.Selection(
        max_length=12, choices=FIGURE_TYPES, blank=True, default='',
        help_text='Cómo se presenta el resultado (Odoo figure_type).',
    )
    green_on_positive = fields.Boolean(
        default=True,
        help_text='Un crecimiento positivo se pinta en verde; falso invierte '
                  'el criterio, p. ej. en gastos (Odoo green_on_positive).',
    )
    blank_if_zero = fields.Boolean(
        default=False,
        help_text='Deja la celda vacía en vez de mostrar 0 (Odoo '
                  'blank_if_zero).',
    )
    auditable = fields.Boolean(
        default=False,
        help_text='El valor se puede auditar hasta sus apuntes de origen '
                  '(Odoo auditable).',
    )
    carryover_target = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Destino del arrastre entre periodos, en la forma '
                  'codigo_linea.etiqueta (Odoo carryover_target).',
    )

    class Meta:
        db_table = 'account_report_expression'
        ordering = ['id']
        constraints = [
            # odoo19c: account_report.py:630-633 — _line_label_uniq.
            models.UniqueConstraint(
                fields=['report_line', 'label'],
                name='unique_account_report_expression_label',
            ),
        ]


class AccountReportColumn(models.Model):
    """``account.report.column`` — una columna del reporte."""

    name = fields.Char(
        max_length=255,
        help_text='Encabezado de la columna (Odoo name, requerido, '
                  'traducible).',
    )
    expression_label = fields.Char(
        max_length=64,
        help_text='Etiqueta que empareja la columna con la expresión de cada '
                  'línea (Odoo expression_label, requerido).',
    )
    sequence = fields.Integer(
        default=0, help_text='Orden de la columna (Odoo sequence).',
    )
    report = fields.Many2one(
        'account.AccountReport', on_delete=models.CASCADE,
        related_name='columns',
        help_text='Reporte al que pertenece la columna (Odoo report_id).',
    )
    sortable = fields.Boolean(
        default=False,
        help_text='El usuario puede ordenar por esta columna (Odoo sortable).',
    )
    figure_type = fields.Selection(
        max_length=12, choices=FIGURE_TYPES, default='monetary',
        help_text='Cómo se presentan los valores de la columna (Odoo '
                  'figure_type).',
    )
    blank_if_zero = fields.Boolean(
        default=False,
        help_text='Deja la celda vacía en vez de mostrar 0 (Odoo '
                  'blank_if_zero).',
    )
    custom_audit_action = fields.Many2one(
        'base.IrActionsActWindow', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='account_report_columns',
        help_text='Acción de auditoría a medida al pulsar una celda (Odoo '
                  'custom_audit_action_id).',
    )

    class Meta:
        db_table = 'account_report_column'
        ordering = ['sequence', 'id']


class AccountReportExternalValue(models.Model):
    """``account.report.external.value`` — un valor que no sale del libro mayor.

    Ajustes de cierre, cifras de una declaración presentada, o el arrastre de
    un periodo anterior: cantidades que el contador introduce contra una
    expresión concreta y que el motor ``external`` suma al resultado.
    """

    name = fields.Char(
        max_length=255,
        help_text='Descripción del valor (Odoo name, requerido).',
    )
    value = fields.Float(
        default=0.0,
        help_text='Importe numérico. ``Float``, no ``Monetary``, fiel a la '
                  'referencia (odoo19c: account_report.py:952): el valor no '
                  'lleva divisa propia — la toma del reporte que lo consume.',
    )
    text_value = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Valor textual, cuando la expresión no es numérica (Odoo '
                  'text_value).',
    )
    date = fields.Date(
        help_text='Fecha a la que aplica el valor (Odoo date, requerido).',
    )
    target_report_expression = fields.Many2one(
        'account.AccountReportExpression', on_delete=models.CASCADE,
        related_name='external_values',
        help_text='Expresión a la que se suma este valor (Odoo '
                  'target_report_expression_id).',
    )
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE,
        related_name='account_report_external_values',
        help_text='Empresa dueña del valor (Odoo company_id, requerido).',
    )
    carryover_origin_expression_label = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Etiqueta de la expresión de la que proviene el arrastre '
                  '(Odoo carryover_origin_expression_label).',
    )
    carryover_origin_report_line = fields.Many2one(
        'account.AccountReportLine', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='carryover_external_values',
        help_text='Línea de la que proviene el arrastre (Odoo '
                  'carryover_origin_report_line_id).',
    )

    class Meta:
        db_table = 'account_report_external_value'
        ordering = ['date', 'id']
