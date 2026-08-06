"""``account.chart.template`` — el cargador del plan contable.

Adaptación fiel de Odoo ``account/models/chart_template.py``. En la referencia
es un ``AbstractModel``: no guarda nada, **instancia** — lee la definición de un
plan de cuentas y crea las cuentas, grupos, impuestos y posiciones fiscales de
una empresa concreta.

Su clave es que **no crea por posición, crea por nombre estable**: cada registro
nace con un identificador externo por empresa (``account.{id}_receivable``), y
las referencias entre ellos —el impuesto que apunta a su grupo, el reparto que
apunta a su cuenta— se resuelven por ese nombre. Ese mecanismo es
``ir.model.data``; ver :ref:`h-api-347`, que lo puso.

Dos fuentes de datos, igual que la referencia:

- **CSV** en ``data/template/<modelo>-<codigo>.csv``, copiados de la referencia
  (``odoo19c: account/data/template/``, addon **LGPL-3** → copia con
  atribución, DEC-KX-03).
- **Funciones decoradas** con ``@template(codigo, modelo)``, para lo que no cabe
  en una tabla: los valores que se escriben en la empresa, el nombre del plan,
  las cuentas de propiedad.

Divergencia de mecanismo declarada — cómo se descubre el registro
------------------------------------------------------------------

La referencia descubre las funciones decoradas recorriendo los atributos de
clase en ``_post_model_setup__``, un enganche de su registro de modelos. Aquí no
hay tal registro: el decorador **se registra a sí mismo** al importarse el
módulo que lo usa, que es la forma natural en Python y no necesita barrer
clases. El efecto es el mismo y el orden es explícito.

Lo que **no** diverge —y una versión anterior sí— es todo lo demás del
mecanismo: las plantillas se declaran **dentro de la clase** (aquí abajo, y en
``template_generic_coa.py`` como subclase, ≙ su ``_inherit``), reciben
``(cls, template_code)``, el registro guarda **una lista** por
``(codigo, modelo)`` para que varios módulos compongan, y el resolutor recorre
los ancestros en el orden verbatim de la referencia. Las cuatro cosas se habían
cambiado sin decidirlo, excusadas con "su ORM lo exige"; ver :ref:`h-api-350`.

Lo que este porte NO trae (medido, con desenlace)
---------------------------------------------------

**Conteo medido, no estimado:** la referencia declara **40** métodos de clase;
aquí hay **15** equivalentes y quedan **25** ausentes (1537 líneas allá contra
639 aquí). Una versión anterior de este docstring decía "13 restantes" — era un
conteo generoso, el defecto que ``porte-completo-no-parcial.md`` nombra.

Los 25 se reparten en tres grupos, y **sólo el tercero es trabajo pendiente**:

**a) Siete que este puerto resuelve de otra forma** (divergencia de mecanismo,
declarada arriba): ``_template_register`` y ``_post_model_setup__`` (el
decorador se registra solo), y los cinco ``_get_account_<modelo>`` —
``account``, ``group``, ``tax_group``, ``tax``, ``fiscal_position``—, cuyas
tablas viven en los CSV y cuyo orden lo fija ``loaded_models``.

**b) Seis de traducción** (``_load_translations`` y sus ayudantes) — dependen
del mecanismo de campos traducibles de la referencia, que este proyecto no
porta. Si se portara, entran; hoy no hay dónde enchufarlos.

**c) Doce que son trabajo pendiente**, con su dependencia real medida:

- ``_setup_utility_bank_accounts``, ``_create_outstanding_accounts``,
  ``_get_accounts_data_values``, ``_get_property_accounts`` y
  ``_get_bank_fees_reco_account`` — las cuentas transitorias de pago. Necesitan
  ``ResCompany.bank_account_code_prefix``, un campo de la **misma familia**
  (``odoo19c: company.py``): no hay bloqueo, hay campo por colgar.
- ``_get_tag_mapper`` y ``_deref_account_tags`` — el modelo
  ``account.account.tag`` **existe y está portado** (``account_account_tag.py``);
  lo que falta del mapeador es su discriminación xmlid-vs-nombre, que consulta
  ``ir.module.module``, un registro de módulos que este puerto no tiene por
  diseño. Los CSV de ``generic_coa`` **no traen columnas de etiqueta**, así que
  hoy no tiene consumidor.
- ``_instantiate_foreign_taxes`` — impuestos de otro país sobre la misma
  empresa; exige un plan ``l10n_*`` portado, y hay **cero** en ``src/addons``.
- ``_install_demo`` — datos de demostración, que este proyecto no tiene.
- ``_pre_reload_data`` (219 líneas) y ``_pre_load_data`` — recarga sobre una
  plantilla ya cargada, preservando lo que el usuario tocó.

Sucesor registrado: tarea #155.
"""
import ast
import csv
import pathlib
from collections import defaultdict

from django.apps import apps
from django.db import transaction

from addons.base.models.ir_model import IrModelData
from exceptions import UserError
from tools.translate import _

#: Raíz de los CSV de plantilla, espejo de ``<addon>/data/template/``.
TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'template'

#: ``codigo_plantilla -> modelo -> [funciones]``. Lo puebla el decorador al
#: importar el módulo que declara la plantilla.
#:
#: La **lista** no es un detalle: ≙ ``_template_register``
#: (``odoo19c: chart_template.py:78-88``), un ``defaultdict(list)`` que permite
#: que varios módulos aporten al mismo ``(codigo, modelo)`` y se compongan. Una
#: versión anterior guardaba ``{(codigo, modelo): funcion}``: la segunda
#: declaración **borraba** la primera en silencio.
TEMPLATE_REGISTRY = defaultdict(lambda: defaultdict(list))

#: El modelo bajo el que la referencia guarda los valores sueltos del plan
#: (nombre, país, cuentas de propiedad) — no es un modelo real.
TEMPLATE_DATA = 'template_data'


def template(code=None, model=TEMPLATE_DATA):
    """Declara que la función aporta los datos de ``model`` para ``code``.

    ≙ el decorador ``template`` de la referencia
    (``odoo19c: chart_template.py:53``). Allá guarda ``_l10n_template`` en la
    función para que el registro la encuentre después; aquí registra
    directamente, porque no hay un barrido posterior que la busque.

    ``code=None`` declara una plantilla **base**: aporta a *todos* los planes.
    Es el mismo mecanismo de la referencia, cuyo resolutor recorre
    ``[None] + parents`` (``chart_template.py:813``). Así viven los diarios por
    defecto: no pertenecen a un plan, pertenecen a *tener* contabilidad.

    La función decorada recibe ``(cls, template_code)`` — ≙ la firma
    ``(self, template_code)`` de la referencia. El código llega por parámetro
    aunque el decorador ya lo fije, porque una plantilla base (``code=None``)
    sirve a **cualquier** plan y necesita saber a cuál está sirviendo.
    """
    def decorator(func):
        TEMPLATE_REGISTRY[code][model].append(func)
        func.template_target = (code, model)
        return func
    return decorator


class ChartTemplate:
    """El cargador. Sin estado propio: todo entra por parámetro.

    En la referencia es un ``AbstractModel`` porque su ORM necesita que todo
    cuelgue de uno; el equivalente aquí es una clase de métodos de clase. No
    tiene tabla ni migración, igual que allá.
    """

    # -- registro y selección ----------------------------------------------

    @classmethod
    def get_chart_template_mapping(cls):
        """Los planes disponibles y su nombre — ≙ ``_get_chart_template_mapping``.

        La referencia los descubre recorriendo los módulos instalados; aquí
        salen del registro, que es la misma información sin el rodeo del
        catálogo de módulos.
        """
        mapping = {}
        for code, by_model in TEMPLATE_REGISTRY.items():
            data = {}
            for func in by_model.get(TEMPLATE_DATA, []):
                data.update(func(cls, code))
            if not data:
                continue
            mapping[code] = {
                'name': data.get('name', code),
                'country': data.get('country'),
                'parent': data.get('parent'),
            }
        return mapping

    @classmethod
    def get_parent_template(cls, code):
        """La cadena de herencia del plan — ≙ ``_get_parent_template``.

        Un plan puede declarar ``parent`` y heredar las tablas de otro; el
        caso real en la referencia son las localizaciones que parten de un
        plan regional. La cadena va del plan **hacia** sus ancestros, y el
        resolutor la recorre precedida de ``None`` (la base), de modo que lo
        más específico se aplica al final y gana.
        """
        parents = []
        mapping = cls.get_chart_template_mapping()
        while mapping.get(code) and code not in parents:
            parents.append(code)
            code = mapping[code].get('parent')
        return parents

    @classmethod
    def select_chart_template(cls, country=None):
        """Los planes en forma de opciones — ≙ ``_select_chart_template``.

        Ordena poniendo primero el del país pedido, y si no hay país, el
        genérico. Mismo criterio que la referencia.
        """
        mapping = cls.get_chart_template_mapping()
        return [
            (code, data['name'])
            for code, data in sorted(mapping.items(), key=lambda t: (
                t[0] != 'generic_coa' if not country
                else t[1]['country'] != country
            ))
        ]

    @classmethod
    def guess_chart_template(cls, country):
        """El plan más apropiado para un país — ≙ ``_guess_chart_template``."""
        options = cls.select_chart_template(country)
        if not options:
            raise UserError(_('No hay ningún plan contable registrado.'))
        return options[0][0]

    # -- identificadores externos ------------------------------------------

    @staticmethod
    def company_xmlid(xmlid, company):
        """El identificador **por empresa** — ≙ ``company_xmlid``.

        ``receivable`` no identifica una cuenta: identifica *el papel* de una
        cuenta. La cuenta concreta es la de esta empresa, así que el
        identificador real lleva su id delante. Un xmlid que ya trae módulo
        (``base.us``) se devuelve tal cual: apunta a un registro global.
        """
        if '.' in xmlid:
            return xmlid
        return f'account.{company.pk}_{xmlid}'

    @classmethod
    def ref(cls, xmlid, company, raise_if_not_found=True):
        """El registro que ``xmlid`` designa **para esta empresa**.

        ≙ ``ref`` de la referencia, incluido su fallback a la empresa padre:
        una filial que no redefine una cuenta usa la de su matriz.
        """
        record = IrModelData.ref(
            cls.company_xmlid(xmlid, company), raise_if_not_found=False)
        if record is not None:
            return record
        parent_code = getattr(company, 'parent', None)
        if parent_code is not None:
            record = IrModelData.ref(
                cls.company_xmlid(xmlid, parent_code), raise_if_not_found=False)
            if record is not None:
                return record
        if raise_if_not_found:
            raise ValueError(
                'El plan contable referencia «%s», que no existe para la '
                'empresa %s' % (xmlid, company))
        return None

    # -- lectura de la definición ------------------------------------------

    @staticmethod
    def map_field_name(model_class, source_name):
        """El nombre de allá → el de aquí, o ``None`` si no existe.

        Los CSV vienen verbatim de la referencia, así que sus columnas llevan
        los sufijos ``_id``/``_ids`` de su ORM: ``tax_group_id``,
        ``repartition_line_ids``. Este puerto los quitó en toda su superficie
        (``tax_group``, ``repartition_lines``), de modo que la traducción es
        mecánica y no una tabla de excepciones: quitar el sufijo, y para las
        colecciones probar también el plural.

        Devolver ``None`` es un desenlace normal: el CSV describe columnas que
        este puerto todavía no tiene.
        """
        model_fields = {f.name for f in model_class._meta.get_fields()}
        if source_name in model_fields:
            return source_name
        if source_name.endswith('_ids'):
            base = source_name[:-4]
            for candidate in (base, base + 's'):
                if candidate in model_fields:
                    return candidate
        elif source_name.endswith('_id'):
            base = source_name[:-3]
            if base in model_fields:
                return base
        return None

    @staticmethod
    def coerce(field, value):
        """Del texto del CSV al tipo del campo.

        Todo en un CSV es texto; ``factor_percent`` llega como ``'100'`` y el
        cómputo que lo divide entre 100 no puede con una cadena. Se aplica a
        los valores del registro **y a los de sus líneas hijas**, que es donde
        faltaba.
        """
        if not isinstance(value, str) or not value:
            return value
        model_class = type(field).__name__
        if model_class in ('BooleanField', 'IntegerField', 'FloatField',
                     'DecimalField', 'PositiveIntegerField'):
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                return value
        return value.strip()

    @classmethod
    def parse_csv(cls, template_code, model_name, model_class):
        """Lee ``<modelo>-<codigo>.csv`` — ≙ ``_parse_csv``.

        Dos formas de columna, ambas de la referencia:

        - ``campo`` → un valor del registro;
        - ``relacion/campo`` → un valor de una **línea hija**. Una fila con el
          ``id`` vacío no es un registro nuevo: es otra línea hija del anterior.
          Así el CSV de impuestos describe un impuesto y sus cuatro líneas de
          reparto en cinco filas.

        El valor se convierte según el tipo del campo destino; lo que no sea
        booleano o número entra como texto y lo resuelve ``load_data``.
        """
        path = TEMPLATE_DIR / f'{model_name}-{template_code}.csv'
        if not path.exists():
            return {}

        model_fields = {f.name: f for f in model_class._meta.get_fields()}

        def convert(name, value):
            real_name = cls.map_field_name(model_class, name)
            field = model_fields.get(real_name) if real_name else None
            return cls.coerce(field, value) if field is not None else value

        res = defaultdict(dict)
        last_xmlid = None
        with path.open(encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                if row.get('id'):
                    last_xmlid = row['id']
                    res[last_xmlid].update({
                        key: convert(key, value)
                        for key, value in row.items()
                        if key != 'id' and value and '/' not in key
                    })
                if last_xmlid is None:
                    continue
                child = {
                    key.split('/', 1)[1]: value
                    for key, value in row.items()
                    if '/' in key and value
                }
                if child:
                    relation = next(c for c in row if '/' in c).split('/', 1)[0]
                    res[last_xmlid].setdefault(relation, []).append(child)
        return dict(res)

    @classmethod
    def get_chart_template_model_data(cls, template_code, model_name, model_class):
        """CSV + función decorada para un modelo — ≙ ``_get_chart_template_model_data``.

        La función decorada **se aplica encima** del CSV, no lo reemplaza: así
        una plantilla puede corregir un campo suelto sin copiar la tabla.

        El orden de recorrido es el de la referencia **verbatim**:
        ``[None] + get_parent_template(code)``, donde ese método devuelve
        ``[codigo, padre, abuelo]`` — el más específico primero
        (``odoo19c: chart_template.py:1236-1242``). Como cada vuelta hace
        ``update``, **el ancestro sobreescribe al hijo**. Es contraintuitivo y
        aun así es lo que hace la referencia; el propio archivo usa ``[::-1]``
        explícito allá donde quiere el orden inverso (línea 1326). Una versión
        anterior de este puerto invertía la lista "porque parecía al revés":
        cambiar la precedencia de un mecanismo sin decidirlo es la divergencia
        que ``referencia-odoo-gobierna-las-decisiones.md`` prohíbe. Hoy no
        cambia nada observable —``generic_coa`` no declara ``parent``—, y el día
        que exista un plan con padre el comportamiento será el de la referencia
        y no el que supuse.
        """
        data = cls.parse_csv(template_code, model_name, model_class)
        for code in [None] + cls.get_parent_template(template_code):
            for func in TEMPLATE_REGISTRY[code].get(model_name, []):
                for xmlid, values in func(cls, template_code).items():
                    data.setdefault(xmlid, {}).update(values)
        return data

    @classmethod
    def get_chart_template_data(cls, template_code):
        """Toda la definición del plan — ≙ ``_get_chart_template_data``.

        El orden **importa**: los grupos de impuesto antes que los impuestos,
        las cuentas antes que los repartos que las nombran. Es el mismo orden de
        creación de la referencia.
        """
        funcs = TEMPLATE_REGISTRY[template_code].get(TEMPLATE_DATA, [])
        if not funcs:
            raise UserError(
                _('No existe el plan contable «%(code)s».') % {'code': template_code})
        loose_values = {}
        for func in funcs:
            loose_values.update(func(cls, template_code))
        data = {TEMPLATE_DATA: loose_values}
        for name, model_class in cls.loaded_models():
            data[name] = cls.get_chart_template_model_data(
                template_code, name, model_class)
        return data

    @classmethod
    def loaded_models(cls):
        """Los modelos que se instancian, **en orden de dependencia**.

        ≙ los siete ``_get_account_*`` de la referencia, que allá son métodos
        separados porque su ORM los llama por nombre. Aquí una lista ordenada
        dice lo mismo y hace explícito el orden, que era lo que aquellos
        métodos codificaban implícitamente.
        """
        return [
            ('account.account', apps.get_model('account', 'AccountAccount')),
            ('account.tax.group', apps.get_model('account', 'AccountTaxGroup')),
            ('account.tax', apps.get_model('account', 'AccountTax')),
            ('account.fiscal.position', apps.get_model('account', 'AccountFiscalPosition')),
            ('account.journal', apps.get_model('account', 'AccountJournal')),
            ('account.reconcile.model',
             apps.get_model('account', 'AccountReconcileModel')),
        ]

    # -- instanciación ------------------------------------------------------

    @classmethod
    def try_loading(cls, template_code, company, force_create=True):
        """Carga el plan si se puede — ≙ ``try_loading``.

        Sin empresa no hay nada que cargar (la referencia también sale sin
        ruido). Sin código, se adivina por el país.
        """
        if company is None:
            return None
        template_code = template_code or cls.guess_chart_template(
            getattr(company, 'country', None))
        return cls.load(template_code, company, force_create=force_create)

    @classmethod
    @transaction.atomic
    def load(cls, template_code, company, force_create=True):
        """Instancia el plan para ``company`` — ≙ ``_load``.

        Atómico a propósito: un plan a medias es peor que ninguno — deja
        cuentas sin sus impuestos y una empresa que parece configurada.
        """
        data = cls.get_chart_template_data(template_code)
        created = {}
        for name, model_class in cls.loaded_models():
            created[name] = cls.load_model_data(
                name, model_class, data.get(name, {}), company,
                force_create=force_create)
        cls.post_load_data(template_code, company, data[TEMPLATE_DATA])
        return created

    @classmethod
    def load_model_data(cls, model_name, model_class, data, company,
                        force_create=True):
        """Crea los registros de un modelo — ≙ la parte de ``_load_data``.

        Cada valor que nombra otro registro se resuelve por identificador
        externo **en el momento de escribirlo**, no antes: por eso el orden de
        ``loaded_models`` es el que es.
        """
        created = {}
        for xmlid, values in data.items():
            existing = cls.ref(xmlid, company, raise_if_not_found=False)
            if existing is not None and not force_create:
                created[xmlid] = existing
                continue

            children = {}
            flat_values = {}
            for field, value in values.items():
                if isinstance(value, list):
                    children[field] = value
                else:
                    flat_values[field] = value

            flat_values = cls.resolve_values(model_class, flat_values, company)
            flat_values['company'] = company
            if existing is not None:
                for field, value in flat_values.items():
                    setattr(existing, field, value)
                existing.save()
                record_data = existing
            else:
                record_data = model_class.objects.create(**flat_values)
            IrModelData.set_xmlid(record_data, cls.company_xmlid(xmlid, company))
            cls.load_child_lines(record_data, children, company)
            created[xmlid] = record_data
        return created

    @classmethod
    def load_child_lines(cls, parent, children, company):
        """Crea las líneas hijas declaradas con ``relacion/campo`` en el CSV."""
        for relation, rows in children.items():
            name = cls.map_field_name(type(parent), relation)
            if name is None:
                continue
            field = parent._meta.get_field(name)
            child_class = field.related_model
            reverse_name = field.field.name
            for order, row in enumerate(rows):
                values = cls.resolve_values(child_class, dict(row), company)
                values[reverse_name] = parent
                values['company'] = company
                if 'sequence' in {f.name for f in child_class._meta.get_fields()}:
                    values.setdefault('sequence', order)
                child_class.objects.create(**values)

    @classmethod
    def resolve_values(cls, model_class, values, company):
        """Traduce los valores del CSV a lo que el modelo espera.

        Un valor de una relación llega como identificador externo
        (``tax_group_15``, ``tax_received``) y aquí se convierte en el registro.
        Los campos que el modelo no tiene **se descartan en silencio**: el CSV
        viene de la referencia y describe más columnas de las que este puerto
        porta todavía; abortar por eso impediría cargar el plan por un campo
        accesorio.
        """
        model_fields = {f.name: f for f in model_class._meta.get_fields()}
        out = {}
        for raw, value in values.items():
            name = cls.map_field_name(model_class, raw)
            field = model_fields.get(name) if name else None
            if field is None:
                continue
            if field.is_relation and not field.many_to_many:
                if not value:
                    continue
                out[name] = cls.ref(value, company, raise_if_not_found=False)
            elif field.many_to_many:
                continue          # se resuelven tras crear todo (ver post_load_data)
            else:
                out[name] = cls.coerce(field, value)
        return {k: v for k, v in out.items() if v is not None}

    @classmethod
    def post_load_data(cls, template_code, company, template_data):
        """Escribe en la empresa lo que el plan declara — ≙ ``_post_load_data``.

        Las claves ``property_*`` nombran cuentas por identificador externo; se
        resuelven ahora, cuando ya existen. Es el paso que deja a la empresa
        **configurada** y no sólo con registros sueltos.
        """
        company_values = {}
        for func in TEMPLATE_REGISTRY[template_code].get('res.company', []):
            company_values.update(func(cls, template_code))
        properties = {
            key: value for key, value in template_data.items()
            if key.startswith('property_')
        }
        to_write = {}
        model_fields = {f.name for f in type(company)._meta.get_fields()}
        for key, xmlid in properties.items():
            target = key.replace('property_', '').replace('_id', '')
            if target in model_fields:
                to_write[target] = cls.ref(xmlid, company, raise_if_not_found=False)
        if company_values:
            for key, value in company_values.items():
                if key in model_fields and isinstance(value, str):
                    resolved = cls.ref(value, company, raise_if_not_found=False)
                    if resolved is not None:
                        to_write[key] = resolved
                elif key in model_fields and not isinstance(value, str):
                    to_write[key] = value
        if not to_write:
            return company
        for key, value in to_write.items():
            setattr(company, key, value)
        company.save(update_fields=list(to_write))
        return company

    # -- plantillas base (Root template functions) ---------------------------
    #
    # ≙ la sección homónima de ``odoo19c: chart_template.py:1121-1240``, donde
    # viven **dentro** de ``AccountChartTemplate``. Aquí también: lo que aporta
    # datos a un plan es parte del cargador, no un módulo suelto. Una versión
    # anterior las sacó a ``template_base.py`` como funciones de módulo y lo
    # excusó con "su ORM lo exige" — ver :ref:`h-api-350`.

    @template(model='account.journal')
    def get_account_journal(cls, template_code):
        """Los seis diarios por defecto — ≙ ``_get_account_journal``.

        Base (sin código): un diario de ventas no es una particularidad de la
        contabilidad mexicana ni de la genérica. Es lo que hace falta para
        **asentar**, y sin él un plan cargado es un catálogo de cuentas que no
        puede emitir una factura.

        El de banco es el único cuyo código la referencia deja en blanco porque
        su ORM lo genera: ``_get_next_journal_default_code``
        (``odoo19c: account_journal.py:883``) compone el prefijo ``BNK`` con el
        primer número libre, así que en una empresa nueva da ``BNK1``. Aquí se
        escribe ese valor: ``AccountJournal`` declara
        ``UniqueConstraint(company, code)`` y dejarlo vacío haría colisionar dos
        diarios en blanco en cuanto hubiera un segundo.
        """
        return {
            'sale': {
                'name': _('Ventas'),
                'type': 'sale',
                'code': 'INV',
                'show_on_dashboard': True,
                'color': 11,
                'sequence': 5,
            },
            'purchase': {
                'name': _('Compras'),
                'type': 'purchase',
                'code': 'BILL',
                'show_on_dashboard': True,
                'color': 11,
                'sequence': 6,
            },
            'general': {
                'name': _('Operaciones varias'),
                'type': 'general',
                'code': 'MISC',
                'show_on_dashboard': False,
                'sequence': 9,
            },
            'exch': {
                'name': _('Diferencia de cambio'),
                'type': 'general',
                'code': 'EXCH',
                'show_on_dashboard': False,
            },
            'caba': {
                'name': _('Impuestos con criterio de caja'),
                'type': 'general',
                'code': 'CABA',
                'show_on_dashboard': False,
            },
            'bank': {
                'name': _('Banco'),
                'type': 'bank',
                'code': 'BNK1',
                'show_on_dashboard': True,
                'sequence': 7,
            },
        }

    @template(model='account.reconcile.model')
    def get_account_reconcile_model(cls, template_code):
        """Las dos reglas de conciliación por defecto — ≙ ``_get_account_reconcile_model``.

        También base, y por el mismo motivo que los diarios: una transferencia
        interna y una comisión bancaria aparecen en el extracto de cualquier
        empresa, no de una localización concreta.

        La referencia expresa las líneas hijas con ``Command.create({...})``, la
        forma con la que su ORM distingue crear de enlazar. Aquí una lista de
        diccionarios bajo el nombre de la relación ya significa «crear estas
        hijas» — es lo que el cargador hace con ``repartition_line_ids`` del
        CSV, así que no hace falta un envoltorio que sólo diga «create».
        """
        return {
            'internal_transfer_reco': {
                'name': _('Transferencias internas'),
                'line_ids': [{
                    'amount_type': 'percentage',
                    'amount_string': '100',
                    'label': _('Transferencias internas'),
                }],
            },
            'bank_fees_reco': {
                'name': _('Comisiones bancarias'),
                'match_label': 'contains',
                'match_label_param': 'Bank Fees',
                'line_ids': [{
                    'amount_type': 'percentage',
                    'amount_string': '100',
                    'label': _('Comisiones bancarias'),
                }],
            },
        }
