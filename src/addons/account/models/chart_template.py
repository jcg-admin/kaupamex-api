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

Divergencia de mecanismo declarada — el registro
--------------------------------------------------

La referencia descubre las funciones decoradas recorriendo los atributos de
clase en ``_post_model_setup__``, un enganche de su registro de modelos. Aquí no
hay tal registro: el decorador **se registra a sí mismo** al importarse el
módulo que lo usa, que es la forma natural en Python y no necesita barrer
clases. El efecto es el mismo y el orden es explícito.

Lo que este porte NO trae (medido, con desenlace)
---------------------------------------------------

De los 40 métodos de la referencia se portan los del camino de carga. Los 13
restantes tienen su razón nombrada:

- ``_install_demo`` — no hay datos de demostración en este proyecto.
- ``_pre_reload_data`` (219 líneas) — recarga sobre una plantilla **ya cargada**;
  aplica al reinstalar un módulo, que aquí no ocurre.
- ``_instantiate_foreign_taxes`` (174 líneas), ``_get_tag_mapper`` y
  ``_deref_account_tags`` — dependen de addons ``l10n_*``, de los que hay
  **cero** en este árbol.
- Los seis de traducción (``_load_translations`` y sus ayudantes) — dependen del
  mecanismo de campos traducibles de la referencia, que no se porta.
- ``_post_model_setup__`` — el enganche del registro (ver arriba).
- ``_setup_utility_bank_accounts`` y ``_create_outstanding_accounts`` —
  necesitan ``account.journal`` con prefijos de código de banco/caja, que este
  plan genérico no configura todavía.

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

#: ``(codigo_plantilla, modelo) -> funcion``. Lo puebla el decorador al importar
#: el módulo que declara la plantilla; ver la nota de divergencia del módulo.
TEMPLATE_REGISTRY = {}

#: El modelo bajo el que la referencia guarda los valores sueltos del plan
#: (nombre, país, cuentas de propiedad) — no es un modelo real.
TEMPLATE_DATA = 'template_data'


def template(code, model=TEMPLATE_DATA):
    """Declara que la función aporta los datos de ``model`` para ``code``.

    ≙ el decorador ``template`` de la referencia
    (``odoo19c: chart_template.py:54``). Allá guarda ``_l10n_template`` en la
    función para que el registro la encuentre después; aquí registra
    directamente, porque no hay un barrido posterior que la busque.
    """
    def decorator(func):
        TEMPLATE_REGISTRY[(code, model)] = func
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
        for (code, model), func in TEMPLATE_REGISTRY.items():
            if model != TEMPLATE_DATA:
                continue
            datos = func()
            mapping[code] = {
                'name': datos.get('name', code),
                'country': datos.get('country'),
            }
        return mapping

    @classmethod
    def select_chart_template(cls, country=None):
        """Los planes en forma de opciones — ≙ ``_select_chart_template``.

        Ordena poniendo primero el del país pedido, y si no hay país, el
        genérico. Mismo criterio que la referencia.
        """
        mapping = cls.get_chart_template_mapping()
        return [
            (code, datos['name'])
            for code, datos in sorted(mapping.items(), key=lambda t: (
                t[0] != 'generic_coa' if not country
                else t[1]['country'] != country
            ))
        ]

    @classmethod
    def guess_chart_template(cls, country):
        """El plan más apropiado para un país — ≙ ``_guess_chart_template``."""
        opciones = cls.select_chart_template(country)
        if not opciones:
            raise UserError(_('No hay ningún plan contable registrado.'))
        return opciones[0][0]

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
        padre = getattr(company, 'parent', None)
        if padre is not None:
            record = IrModelData.ref(
                cls.company_xmlid(xmlid, padre), raise_if_not_found=False)
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
        campos = {f.name for f in model_class._meta.get_fields()}
        if source_name in campos:
            return source_name
        if source_name.endswith('_ids'):
            base = source_name[:-4]
            for candidato in (base, base + 's'):
                if candidato in campos:
                    return candidato
        elif source_name.endswith('_id'):
            base = source_name[:-3]
            if base in campos:
                return base
        return None

    @staticmethod
    def coerce(campo, valor):
        """Del texto del CSV al tipo del campo.

        Todo en un CSV es texto; ``factor_percent`` llega como ``'100'`` y el
        cómputo que lo divide entre 100 no puede con una cadena. Se aplica a
        los valores del registro **y a los de sus líneas hijas**, que es donde
        faltaba.
        """
        if not isinstance(valor, str) or not valor:
            return valor
        clase = type(campo).__name__
        if clase in ('BooleanField', 'IntegerField', 'FloatField',
                     'DecimalField', 'PositiveIntegerField'):
            try:
                return ast.literal_eval(valor)
            except (ValueError, SyntaxError):
                return valor
        return valor.strip()

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
        ruta = TEMPLATE_DIR / f'{model_name}-{template_code}.csv'
        if not ruta.exists():
            return {}

        campos = {f.name: f for f in model_class._meta.get_fields()}

        def convertir(nombre, valor):
            real = cls.map_field_name(model_class, nombre)
            campo = campos.get(real) if real else None
            return cls.coerce(campo, valor) if campo is not None else valor

        res = defaultdict(dict)
        ultimo = None
        with ruta.open(encoding='utf-8') as fh:
            for fila in csv.DictReader(fh):
                if fila.get('id'):
                    ultimo = fila['id']
                    res[ultimo].update({
                        clave: convertir(clave, valor)
                        for clave, valor in fila.items()
                        if clave != 'id' and valor and '/' not in clave
                    })
                if ultimo is None:
                    continue
                hija = {
                    clave.split('/', 1)[1]: valor
                    for clave, valor in fila.items()
                    if '/' in clave and valor
                }
                if hija:
                    relacion = next(c for c in fila if '/' in c).split('/', 1)[0]
                    res[ultimo].setdefault(relacion, []).append(hija)
        return dict(res)

    @classmethod
    def get_chart_template_model_data(cls, template_code, model_name, model_class):
        """CSV + función decorada para un modelo — ≙ ``_get_chart_template_model_data``.

        La función decorada **se aplica encima** del CSV, no lo reemplaza: así
        una plantilla puede corregir un campo suelto sin copiar la tabla.
        """
        datos = cls.parse_csv(template_code, model_name, model_class)
        func = TEMPLATE_REGISTRY.get((template_code, model_name))
        if func is not None:
            for xmlid, valores in func().items():
                datos.setdefault(xmlid, {}).update(valores)
        return datos

    @classmethod
    def get_chart_template_data(cls, template_code):
        """Toda la definición del plan — ≙ ``_get_chart_template_data``.

        El orden **importa**: los grupos de impuesto antes que los impuestos,
        las cuentas antes que los repartos que las nombran. Es el mismo orden de
        creación de la referencia.
        """
        func = TEMPLATE_REGISTRY.get((template_code, TEMPLATE_DATA))
        if func is None:
            raise UserError(
                _('No existe el plan contable «%(code)s».') % {'code': template_code})
        datos = {TEMPLATE_DATA: func()}
        for nombre, clase in cls.loaded_models():
            datos[nombre] = cls.get_chart_template_model_data(
                template_code, nombre, clase)
        return datos

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
        datos = cls.get_chart_template_data(template_code)
        creados = {}
        for nombre, clase in cls.loaded_models():
            creados[nombre] = cls.load_model_data(
                nombre, clase, datos.get(nombre, {}), company,
                force_create=force_create)
        cls.post_load_data(template_code, company, datos[TEMPLATE_DATA])
        return creados

    @classmethod
    def load_model_data(cls, model_name, model_class, datos, company,
                        force_create=True):
        """Crea los registros de un modelo — ≙ la parte de ``_load_data``.

        Cada valor que nombra otro registro se resuelve por identificador
        externo **en el momento de escribirlo**, no antes: por eso el orden de
        ``loaded_models`` es el que es.
        """
        creados = {}
        for xmlid, valores in datos.items():
            existente = cls.ref(xmlid, company, raise_if_not_found=False)
            if existente is not None and not force_create:
                creados[xmlid] = existente
                continue

            hijas = {}
            planos = {}
            for campo, valor in valores.items():
                if isinstance(valor, list):
                    hijas[campo] = valor
                else:
                    planos[campo] = valor

            planos = cls.resolve_values(model_class, planos, company)
            planos['company'] = company
            if existente is not None:
                for campo, valor in planos.items():
                    setattr(existente, campo, valor)
                existente.save()
                registro = existente
            else:
                registro = model_class.objects.create(**planos)
            IrModelData.set_xmlid(registro, cls.company_xmlid(xmlid, company))
            cls.load_child_lines(registro, hijas, company)
            creados[xmlid] = registro
        return creados

    @classmethod
    def load_child_lines(cls, parent, hijas, company):
        """Crea las líneas hijas declaradas con ``relacion/campo`` en el CSV."""
        for relacion, filas in hijas.items():
            nombre = cls.map_field_name(type(parent), relacion)
            if nombre is None:
                continue
            campo = parent._meta.get_field(nombre)
            hija_class = campo.related_model
            nombre_inverso = campo.field.name
            for orden, fila in enumerate(filas):
                valores = cls.resolve_values(hija_class, dict(fila), company)
                valores[nombre_inverso] = parent
                valores['company'] = company
                if 'sequence' in {f.name for f in hija_class._meta.get_fields()}:
                    valores.setdefault('sequence', orden)
                hija_class.objects.create(**valores)

    @classmethod
    def resolve_values(cls, model_class, valores, company):
        """Traduce los valores del CSV a lo que el modelo espera.

        Un valor de una relación llega como identificador externo
        (``tax_group_15``, ``tax_received``) y aquí se convierte en el registro.
        Los campos que el modelo no tiene **se descartan en silencio**: el CSV
        viene de la referencia y describe más columnas de las que este puerto
        porta todavía; abortar por eso impediría cargar el plan por un campo
        accesorio.
        """
        campos = {f.name: f for f in model_class._meta.get_fields()}
        salida = {}
        for bruto, valor in valores.items():
            nombre = cls.map_field_name(model_class, bruto)
            campo = campos.get(nombre) if nombre else None
            if campo is None:
                continue
            if campo.is_relation and not campo.many_to_many:
                if not valor:
                    continue
                salida[nombre] = cls.ref(valor, company, raise_if_not_found=False)
            elif campo.many_to_many:
                continue          # se resuelven tras crear todo (ver post_load_data)
            else:
                salida[nombre] = cls.coerce(campo, valor)
        return {k: v for k, v in salida.items() if v is not None}

    @classmethod
    def post_load_data(cls, template_code, company, template_data):
        """Escribe en la empresa lo que el plan declara — ≙ ``_post_load_data``.

        Las claves ``property_*`` nombran cuentas por identificador externo; se
        resuelven ahora, cuando ya existen. Es el paso que deja a la empresa
        **configurada** y no sólo con registros sueltos.
        """
        valores_empresa = TEMPLATE_REGISTRY.get((template_code, 'res.company'))
        propiedades = {
            clave: valor for clave, valor in template_data.items()
            if clave.startswith('property_')
        }
        escribir = {}
        campos = {f.name for f in type(company)._meta.get_fields()}
        for clave, xmlid in propiedades.items():
            destino = clave.replace('property_', '').replace('_id', '')
            if destino in campos:
                escribir[destino] = cls.ref(xmlid, company, raise_if_not_found=False)
        if valores_empresa is not None:
            for clave, valor in valores_empresa().items():
                if clave in campos and isinstance(valor, str):
                    resuelto = cls.ref(valor, company, raise_if_not_found=False)
                    if resuelto is not None:
                        escribir[clave] = resuelto
                elif clave in campos and not isinstance(valor, str):
                    escribir[clave] = valor
        if not escribir:
            return company
        for clave, valor in escribir.items():
            setattr(company, clave, valor)
        company.save(update_fields=list(escribir))
        return company
