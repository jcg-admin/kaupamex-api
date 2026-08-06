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
aquí hay **28** y quedan **20** ausentes (1537 líneas allá contra 894 aquí). Lo
mide ``scripts/check_porte_completo.py``, no la memoria.

Los 20 se reparten en tres grupos, y **sólo el tercero es trabajo pendiente**:

**a) Ocho que este puerto resuelve de otra forma** (divergencia de mecanismo,
declarada arriba): ``_template_register`` y ``_post_model_setup__`` (el
decorador se registra solo), los cinco ``_get_account_<modelo>`` — ``account``,
``group``, ``tax_group``, ``tax``, ``fiscal_position``—, cuyas tablas viven en
los CSV y cuyo orden lo fija ``loaded_models``, y ``_load_data``, repartido
entre ``load_model_data`` y ``load_child_lines``.

**b) Seis de traducción** (``_load_translations`` y sus ayudantes) — dependen
del mecanismo de campos traducibles de la referencia, que este proyecto no
porta. Si se portara, entran; hoy no hay dónde enchufarlos.

**c) Seis que son trabajo pendiente**, con su dependencia real medida:

- ``_get_tag_mapper`` y ``_deref_account_tags`` — resuelven las etiquetas de
  **impuesto** (``repartition_line_ids/tag_ids``, con su delimitador y su signo),
  no las de cuenta. Lo que falta del mapeador es su discriminación
  xmlid-vs-nombre, que consulta ``ir.module.module``, un registro de módulos que
  este puerto no tiene por diseño. **Las etiquetas de cuenta ya no dependen de
  ellos**: la columna ``tag_ids`` del CSV la resuelve ``resolve_many_to_many``
  y las tres maestras las siembra ``migrations/0012_seed_account_tags.py``.
- ``_instantiate_foreign_taxes`` — impuestos de otro país sobre la misma
  empresa; exige un plan ``l10n_*`` portado, y hay **cero** en ``src/addons``.
- ``_install_demo`` — datos de demostración, que este proyecto no tiene.
- ``_pre_reload_data`` (219 líneas) y ``_pre_load_data`` — recarga sobre una
  plantilla ya cargada, preservando lo que el usuario tocó.

**Cerrado en este pase:** las cinco cuentas de utilidad del banco
(``_setup_utility_bank_accounts``, ``_create_outstanding_accounts``,
``_get_accounts_data_values``, ``_get_property_accounts`` y
``_get_bank_fees_reco_account``). Lo que las bloqueaba —los prefijos de código
en ``res.company``— era un campo de la misma familia, no una incapacidad.

Sucesor registrado: tarea #155.
"""
import ast
import csv
import pathlib
import re
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

#: Separador de la columna ``tag_ids`` de una línea de reparto — ≙
#: ``TAX_TAG_DELIMITER`` (``odoo19c: chart_template.py:33``). Es ``||`` y no
#: la coma porque el nombre de una etiqueta fiscal la contiene con frecuencia
#: («Base imponible, operaciones exentas»).
TAX_TAG_DELIMITER = '||'

#: Los tres campos de reparto que pueden traer etiquetas — ≙ la tupla de
#: ``_deref_account_tags`` (``odoo19c: chart_template.py:1297``).
REPARTITION_FIELDS = (
    'repartition_line_ids',
    'invoice_repartition_line_ids',
    'refund_repartition_line_ids',
)


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

        ≙ ``TEMPLATE_MODELS`` (``odoo19c: chart_template.py:23-31``,
        ``odoo-tools@622ddc2a``) y los siete ``_get_account_*`` que lo leen.
        Allá son métodos separados porque su ORM los llama por nombre; aquí una
        lista ordenada dice lo mismo y hace explícito el orden, que era lo que
        aquellos métodos codificaban implícitamente.

        **Los siete, no seis:** ``account.group`` abre la lista igual que en la
        referencia. El plan genérico no trae CSV de grupos —los cuatro que
        existen son cuentas, posiciones fiscales, grupos de impuesto e
        impuestos—, pero una localización sí, y sin esta entrada su columna
        no tendría dónde aterrizar. Es el mismo modo de fallo que
        :ref:`h-api-352`: un archivo de datos que el cargador no sabe leer.

        **El orden coincide con el efectivo de la referencia, no con su
        tupla.** ``TEMPLATE_MODELS`` lista ``account.fiscal.position`` *antes*
        de los impuestos, pero ``_pre_load_data`` la **mueve al final** antes
        de cargar (``odoo19c: chart_template.py:526-528``: ``for model in
        ('account.fiscal.position', 'account.reconcile.model'): data[model] =
        data.pop(model)``). Aquí ese orden ya está en la lista, que es donde se
        lee. Quien compare las dos tuplas verá una diferencia que no existe en
        ejecución.
        """
        return [
            ('account.group', apps.get_model('account', 'AccountGroup')),
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
        cls.skip_existing_account_groups(data, company)
        cls.normalize_account_codes(data)
        cls.deref_account_tags(template_code, data.get('account.tax', {}),
                               company)
        created = {}
        for name, model_class in cls.loaded_models():
            created[name] = cls.load_model_data(
                name, model_class, data.get(name, {}), company,
                force_create=force_create)
        cls.post_load_data(template_code, company, data[TEMPLATE_DATA])
        cls.setup_utility_bank_accounts(
            template_code, company, data[TEMPLATE_DATA])
        cls.wire_bank_fees_account(company)
        return created

    @classmethod
    def skip_existing_account_groups(cls, data, company):
        """No re-crea los grupos si ya hay — ≙ el guard de ``_pre_reload_data``.

        ≙ ``odoo19c: chart_template.py:308-312``, que vive dentro de
        ``_pre_reload_data`` y por tanto **sólo corre al recargar** un plan
        sobre una empresa que ya lo tiene (``chart_template.py:233-234``: se
        llama bajo ``if reload_template``). Aquí corre siempre, y el efecto es
        el mismo: si no hay grupos el guard no hace nada, y si los hay es
        porque una carga previa los creó — que es exactamente el caso de
        recarga que la referencia contempla.

        Los grupos son la estructura del plan, no su contenido: volver a
        instanciarlos sobre una empresa que ya los tiene duplicaría el árbol de
        agrupación.

        El dominio de la referencia es asimétrico y se conserva: una empresa
        **hija** cuenta los grupos de **todas** las empresas —comparte los de su
        raíz—, mientras que una raíz cuenta sólo los suyos.
        """
        groups = apps.get_model('account', 'AccountGroup').objects
        existing = (groups.all() if company.parent is not None
                    else groups.filter(company=company))
        if existing.exists():
            data.pop('account.group', None)

    @classmethod
    def normalize_account_codes(cls, data):
        """Lleva cada ``code`` al ancho del plan — ≙ la parte de ``_pre_load_data``.

        ≙ ``odoo19c: chart_template.py:520-523``. El CSV del plan genérico
        mezcla anchos —43 códigos de 4 dígitos y 3 de 6— y la referencia los
        rellena con ceros a la derecha hasta ``code_digits`` **antes** de
        escribirlos: ``1010`` se almacena como ``101000``.

        No es cosmético. El ``code`` es la clave por la que ``AccountGroup``
        casa su rango de prefijos y por la que
        ``AccountAccount.get_closest_parent_account`` ordena para heredar tipo
        y etiquetas: comparar ``'1010'`` con ``'101401'`` como cadenas de
        distinto ancho da un orden que la referencia nunca produce. Y sin la
        normalización el plan quedaba internamente inconsistente — las cuentas
        que este mismo módulo **genera** (``resolve_account_code``) ya salían a
        6 dígitos mientras las **cargadas** se quedaban en 4.

        Un código más largo que ``code_digits`` se deja intacto: el formato
        rellena, no trunca.
        """
        code_digits = int(data.get(TEMPLATE_DATA, {}).get('code_digits', 6))
        accounts = data.get('account.account', {})
        for xmlid, values in accounts.items():
            if 'code' in values:
                accounts[xmlid]['code'] = f'{values["code"]:<0{code_digits}}'

    @classmethod
    def get_tag_mapper(cls, country, company):
        """Resuelve nombres de etiqueta fiscal a registros — ≙ ``_get_tag_mapper``.

        ≙ ``odoo19c: chart_template.py:1244``. Devuelve un invocable porque la
        consulta de etiquetas del país se hace **una vez** y se reutiliza para
        cada línea de reparto del plan.

        La discriminación que hace la referencia es sutil y se conserva: un
        valor con la forma ``modulo.nombre`` puede ser un **identificador
        externo** o el nombre de una etiqueta que casualmente lleva un punto.
        Se decide preguntando si el prefijo nombra un módulo instalado — allá a
        ``ir.module.module``, aquí al registro de aplicaciones de Django, que
        responde exactamente lo mismo (``apps.is_installed('addons.account')``
        → ``True``; ``'addons.inexistente'`` → ``False``).

        Un nombre que no casa ninguna etiqueta **no aborta la carga**: se
        descarta, igual que la rama ``ignore_missing_tags`` de la referencia.
        El plan viene de allá y cita etiquetas de localizaciones que este
        puerto todavía no siembra; abortar por una accesoria impediría cargar
        el plan entero. Es el mismo criterio que ``resolve_values``.
        """
        AccountAccountTag = apps.get_model('account', 'AccountAccountTag')
        by_name = {
            tag.name: tag
            for tag in AccountAccountTag.objects.filter(
                applicability='taxes', country=country)
        }

        def mapping_getter(*names):
            out = []
            for name in names:
                match = re.fullmatch(r'(?P<module>\w+)\.\w+', name or '')
                if match and apps.is_installed(f"addons.{match.group('module')}"):
                    tag = cls.ref(name, company, raise_if_not_found=False)
                    if tag is not None:
                        out.append(tag)
                    continue
                tag = by_name.get(re.sub(r'\s+', ' ', (name or '').strip()))
                if tag is not None:
                    out.append(tag)
            return out

        return mapping_getter

    @classmethod
    def deref_account_tags(cls, template_code, tax_data, company):
        """Cambia los nombres de etiqueta por sus registros — ≙ ``_deref_account_tags``.

        ≙ ``odoo19c: chart_template.py:1294``. Recorre los tres campos de
        reparto de cada impuesto y, donde la columna ``tag_ids`` llegó como
        cadena, la parte por ``TAX_TAG_DELIMITER`` y la sustituye por los
        registros que el mapeador resuelve.

        La referencia envuelve el resultado en ``Command.set(...)`` porque su
        ORM distingue enlazar de crear; aquí una lista de registros bajo el
        nombre de la relación ya significa enlazar, así que el envoltorio
        sobra — el mismo criterio que ``get_account_reconcile_model`` aplica a
        sus líneas hijas.
        """
        country = cls.get_chart_template_mapping().get(
            template_code, {}).get('country')
        mapper = cls.get_tag_mapper(country, company)
        for tax_values in tax_data.values():
            for field_name in REPARTITION_FIELDS:
                for row in tax_values.get(field_name, []):
                    tags = row.get('tag_ids') if isinstance(row, dict) else None
                    if isinstance(tags, str) and tags:
                        row['tag_ids'] = mapper(*tags.split(TAX_TAG_DELIMITER))

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

            many_to_many = cls.resolve_many_to_many(
                model_class, flat_values, company)
            flat_values = cls.resolve_values(model_class, flat_values, company)
            flat_values['company'] = company
            if existing is not None:
                for field, value in flat_values.items():
                    setattr(existing, field, value)
                existing.save()
                record_data = existing
            else:
                record_data = model_class.objects.create(**flat_values)
            for name, records in many_to_many.items():
                getattr(record_data, name).set(records)
            IrModelData.set_xmlid(record_data, cls.company_xmlid(xmlid, company))
            cls.load_child_lines(record_data, children, company)
            created[xmlid] = record_data
        return created

    @classmethod
    def load_child_lines(cls, parent, children, company):
        """Crea las líneas hijas declaradas con ``relacion/campo`` en el CSV.

        Una hija puede traer sus **propios** M2M —el caso real es el
        ``tag_ids`` de una línea de reparto— y valen las mismas dos reglas que
        para el padre: no se pueden pasar al ``create`` porque la tabla
        intermedia necesita la fila, y se resuelven después de crearla.

        Hasta este pase la hija pasaba sólo por ``resolve_values``, que **omite
        los M2M por diseño** (los atiende ``resolve_many_to_many``): el
        ``tag_ids`` de una línea de reparto se descartaba en silencio. Es
        :ref:`h-api-352` un nivel más abajo — la columna existía, el cargador
        no sabía leerla.
        """
        for relation, rows in children.items():
            name = cls.map_field_name(type(parent), relation)
            if name is None:
                continue
            field = parent._meta.get_field(name)
            child_class = field.related_model
            reverse_name = field.field.name
            for order, row in enumerate(rows):
                row = dict(row)
                many_to_many = cls.split_prepared_many_to_many(child_class, row)
                many_to_many.update(
                    cls.resolve_many_to_many(child_class, row, company))
                values = cls.resolve_values(child_class, row, company)
                values[reverse_name] = parent
                values['company'] = company
                if 'sequence' in {f.name for f in child_class._meta.get_fields()}:
                    values.setdefault('sequence', order)
                child = child_class.objects.create(**values)
                for m2m_name, records in many_to_many.items():
                    getattr(child, m2m_name).set(records)

    @classmethod
    def split_prepared_many_to_many(cls, model_class, row):
        """Extrae de ``row`` los M2M que ya llegan resueltos a registros.

        ``deref_account_tags`` sustituye la cadena del CSV por una lista de
        registros **antes** de cargar, así que cuando la fila llega aquí su
        ``tag_ids`` ya no es texto que ``resolve_many_to_many`` sepa partir.
        Se sacan aparte para aplicarlos igual, tras crear la fila.
        """
        model_fields = {f.name: f for f in model_class._meta.get_fields()}
        out = {}
        for raw in list(row):
            name = cls.map_field_name(model_class, raw)
            field = model_fields.get(name) if name else None
            if field is not None and field.many_to_many and isinstance(
                    row[raw], list):
                out[name] = row.pop(raw)
        return out

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
                continue          # los aplica resolve_many_to_many, tras crear
            else:
                out[name] = cls.coerce(field, value)
        return {k: v for k, v in out.items() if v is not None}

    @classmethod
    def resolve_many_to_many(cls, model_class, values, company):
        """Los valores M2M del CSV, ya resueltos a registros.

        Van aparte porque una relación de muchos-a-muchos no se puede escribir
        en el ``create``: necesita la fila creada para poblar su tabla
        intermedia. ``load_model_data`` los aplica justo después.

        La columna admite **varios** identificadores separados por coma, que es
        la convención de CSV de la referencia; hoy el plan genérico usa uno por
        fila (medido: 13 filas, un identificador cada una).

        Un identificador que no resuelve se descarta en silencio, por el mismo
        motivo que el resto del cargador: el CSV viene de la referencia y cita
        registros que este puerto todavía no siembra. Lo que **no** se descarta
        es la columna entera — ese era el defecto (:ref:`h-api-352`).
        """
        model_fields = {f.name: f for f in model_class._meta.get_fields()}
        out = {}
        for raw, value in values.items():
            name = cls.map_field_name(model_class, raw)
            field = model_fields.get(name) if name else None
            if field is None or not field.many_to_many or not value:
                continue
            records = [
                cls.ref(token.strip(), company, raise_if_not_found=False)
                for token in str(value).split(',') if token.strip()
            ]
            records = [record for record in records if record is not None]
            if records:
                out[name] = records
        return out

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
                if key not in model_fields:
                    continue
                if not type(company)._meta.get_field(key).is_relation:
                    # Escalar: se escribe tal cual. Es el caso de los tres
                    # prefijos de código, que son cadenas y no identificadores.
                    to_write[key] = value
                elif isinstance(value, str):
                    resolved = cls.ref(value, company, raise_if_not_found=False)
                    if resolved is not None:
                        to_write[key] = resolved
                else:
                    to_write[key] = value
        if not to_write:
            return company
        for key, value in to_write.items():
            setattr(company, key, value)
        company.save(update_fields=list(to_write))
        return company

    # -- cuentas de utilidad del banco --------------------------------------

    @classmethod
    def get_accounts_data_values(cls, company, template_data,
                                 bank_prefix='', code_digits=0):
        """Las seis cuentas de utilidad y cómo se piden — ≙ ``_get_accounts_data_values``.

        Cada una se declara por **prefijo**, no por código: el plan dice bajo
        qué familia va y ``AccountAccount.search_new_account_code`` busca el
        primer hueco. Las dos de descuento por pronto pago son la excepción —
        la referencia les fija código literal (``999998``/``999997``).

        Las dos de diferencia de efectivo llevan ``account_tag_investing``,
        igual que la referencia (``odoo19c: chart_template.py:873,880``). La
        etiqueta la siembra ``account: migrations/0012_seed_account_tags.py``;
        si faltara, ``resolve_many_to_many`` la descarta y la cuenta se crea
        sin ella — nunca aborta la carga del plan por una etiqueta.
        """
        bank_prefix = bank_prefix or company.bank_account_code_prefix or ''
        code_digits = code_digits or int(template_data.get('code_digits', 6))
        return {
            'account_journal_suspense_account': {
                'name': _('Cuenta transitoria de banco'),
                'prefix': bank_prefix,
                'code_digits': code_digits,
                'account_type': 'asset_current',
            },
            'account_journal_early_pay_discount_loss_account': {
                'name': _('Pérdida por descuento por pronto pago'),
                'code': '999998',
                'account_type': 'expense',
            },
            'account_journal_early_pay_discount_gain_account': {
                'name': _('Ganancia por descuento por pronto pago'),
                'code': '999997',
                'account_type': 'income_other',
            },
            'default_cash_difference_income_account': {
                'name': _('Sobrante de efectivo'),
                'prefix': '999',
                'code_digits': code_digits,
                'account_type': 'income_other',
                'tags': 'account.account_tag_investing',
            },
            'default_cash_difference_expense_account': {
                'name': _('Faltante de efectivo'),
                'prefix': '999',
                'code_digits': code_digits,
                'account_type': 'expense',
                'tags': 'account.account_tag_investing',
            },
            'transfer_account': {
                'name': _('Transferencia de liquidez'),
                'prefix': company.transfer_account_code_prefix or '',
                'code_digits': code_digits,
                'account_type': 'asset_current',
                'reconcile': True,
            },
        }

    @classmethod
    def resolve_account_code(cls, values, company, cache):
        """``prefix`` + ``code_digits`` → un ``code`` libre.

        ≙ el bloque de ``odoo19c: account_account.py:1025-1030``. El código de
        arranque se compone rellenando el prefijo con ceros hasta un dígito
        menos del ancho y cerrando con un ``1``: prefijo ``1014`` y 6 dígitos
        dan ``101401``. Si el prefijo ya es igual o más largo que el ancho, se
        usa tal cual.
        """
        values = dict(values)
        if 'prefix' not in values:
            return values
        prefix = values.pop('prefix') or ''
        digits = values.pop('code_digits')
        start_code = (prefix.ljust(digits - 1, '0') + '1'
                      if len(prefix) < digits else prefix)
        values['code'] = apps.get_model(
            'account', 'AccountAccount').search_new_account_code(
                start_code, company, cache)
        cache.add(values['code'])
        return values

    @classmethod
    def setup_utility_bank_accounts(cls, template_code, company, template_data):
        """Crea las cuentas que el banco necesita — ≙ ``_setup_utility_bank_accounts``.

        Transitoria, diferencias de efectivo, descuentos por pronto pago y
        transferencia de liquidez. Sin ellas un diario de banco no puede
        registrar un cobro que aún no se identifica ni un arqueo que no cuadra.

        Una empresa **hija** no crea las suyas: toma las de su raíz, igual que
        la referencia (``company.parent_ids[0]``). Y lo que la empresa ya tenga
        puesto no se toca.
        """
        bank_prefix = company.bank_account_code_prefix or ''
        code_digits = int(template_data.get('code_digits', 6))
        accounts_data = cls.get_accounts_data_values(
            company, template_data, bank_prefix=bank_prefix,
            code_digits=code_digits)
        for field_name in list(accounts_data):
            if getattr(company, field_name, None):
                del accounts_data[field_name]
        if not accounts_data:
            return

        to_write = {}
        if company.parent is not None:
            root = company.parent.root_id
            for field_name in accounts_data:
                to_write[field_name] = getattr(root, field_name, None)
        else:
            account_model = apps.get_model('account', 'AccountAccount')
            cache = set()
            resolved = {
                xmlid: cls.resolve_account_code(values, company, cache)
                for xmlid, values in accounts_data.items()
            }
            to_write = cls.load_model_data(
                'account.account', account_model, resolved, company,
                force_create=False)
            cls.create_outstanding_accounts(company, bank_prefix, code_digits)

        written = [name for name, account in to_write.items()
                   if account is not None]
        for field_name in written:
            setattr(company, field_name, to_write[field_name])
        if written:
            company.save(update_fields=written)

    @classmethod
    def create_outstanding_accounts(cls, company, bank_prefix, code_digits):
        """Cobros y pagos pendientes — ≙ ``_create_outstanding_accounts``.

        Las dos cuentas donde vive un pago que ya se registró y todavía no se
        concilió con el extracto. No se apuntan en la empresa: la referencia
        las deja sólo con identificador externo, y el comentario que lo dice
        —"No fields on company"— es la razón de que este método esté separado
        del anterior.
        """
        cache = set()
        outstanding = {
            'account_journal_payment_debit_account': {
                'name': _('Cobros pendientes'),
                'prefix': bank_prefix,
                'code_digits': code_digits,
                'account_type': 'asset_current',
                'reconcile': True,
            },
            'account_journal_payment_credit_account': {
                'name': _('Pagos pendientes'),
                'prefix': bank_prefix,
                'code_digits': code_digits,
                'account_type': 'asset_current',
                'reconcile': True,
            },
        }
        account_model = apps.get_model('account', 'AccountAccount')
        cls.load_model_data(
            'account.account', account_model,
            {xmlid: cls.resolve_account_code(values, company, cache)
             for xmlid, values in outstanding.items()},
            company, force_create=False)

    @classmethod
    def wire_bank_fees_account(cls, company):
        """Apunta las dos reglas de conciliación a su cuenta — ≙ el cierre de ``_load``.

        La referencia lo hace en ``chart_template.py:785-792``: la regla de
        transferencia interna apunta a ``transfer_account`` de la empresa, y la
        de comisiones a la que devuelve ``get_bank_fees_reco_account``. Sin
        este paso las dos reglas nacen sin cuenta y no pueden asentar nada —
        que es la forma de :ref:`h-api-346`: un método correcto al que nadie
        llama.
        """
        transfer = cls.ref('internal_transfer_reco', company,
                           raise_if_not_found=False)
        if transfer is not None and company.transfer_account is not None:
            transfer.line_ids.update(account=company.transfer_account)

        bank_fees = cls.ref('bank_fees_reco', company, raise_if_not_found=False)
        if bank_fees is not None:
            account = cls.get_bank_fees_reco_account(company)
            if account is not None:
                bank_fees.line_ids.update(account=account)

    @classmethod
    def get_property_accounts(cls, additional_properties):
        """Qué modelo consume cada cuenta de propiedad — ≙ ``_get_property_accounts``.

        En la referencia estas claves se guardan como *properties* por modelo;
        aquí son campos de la empresa, así que el mapa sirve para saber a quién
        pertenece cada una, no para escribirla.
        """
        return {
            **additional_properties,
            'property_account_receivable_id': 'res.partner',
            'property_account_payable_id': 'res.partner',
            'property_stock_journal': 'product.category',
        }

    @classmethod
    def get_bank_fees_reco_account(cls, company):
        """La cuenta donde cae una comisión bancaria — ≙ ``_get_bank_fees_reco_account``.

        Preferimos una cuenta que se llame así; si no la hay, la primera de
        gasto. Es lo que la regla de conciliación de comisiones necesita para
        tener dónde asentar.
        """
        account_model = apps.get_model('account', 'AccountAccount')
        return (account_model.objects.filter(
                    company=company, name__icontains='Bank Fees').first()
                or account_model.objects.filter(
                    company=company, name__icontains='comisiones').first()
                or account_model.objects.filter(
                    company=company, account_type='expense').first())

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
