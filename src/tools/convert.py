"""El cargador de archivos de datos — fiel a ``odoo/tools/convert.py`` (Odoo 19).

Adaptación de ``odoo19c: odoo/tools/convert.py`` (792 líneas, 24 símbolos).
Es la pieza que lee un ``<record>`` de un archivo de datos de addon y lo
convierte en un registro con su identificador externo: la mitad de arriba de
la cadena cuyo lado ORM es ``orm.models.RecordLoaderMixin`` y cuyo lado de
tabla es ``ir.model.data``.

Qué desbloquea
==============

Hasta la tarea **#115** este archivo no existía y su ausencia se declaraba como
bloqueo en ``ResPartner._load_records_create`` — *"el cargador de data XML — no
existe aquí; los datos iniciales los siembran las migraciones"*. Sembrar desde
una migración funciona para el arranque y **no** para lo que un archivo de
datos hace: reidentificar el registro entre actualizaciones del módulo,
respetar el ``noupdate`` que un usuario puso a mano, y borrar lo que el módulo
dejó de declarar.

LA DIVERGENCIA CENTRAL: el entorno es ambiente, no un objeto
============================================================

Toda la fuente pivota sobre ``self.env``: ``env[modelo]`` resuelve el modelo,
``env(user=…, context=…)`` deriva un entorno hijo, ``env.cr`` es el cursor y
``env.ref`` el resolutor. Aquí el entorno es **ambiente** —``contextvars`` en
``orm/environments.py``, la divergencia que ese módulo declara— así que:

.. list-table::
   :header-rows: 1

   * - La fuente
     - Aquí
   * - ``env[modelo]``
     - ``registry.model_by_name(modelo)``
   * - ``env(context=…)`` / ``model.with_context(…)``
     - ``with context_scope(**valores):``
   * - ``env(user=uid)``
     - ``with user_scope(uid):``
   * - ``env.context``
     - ``get_context()``
   * - ``env.cr.execute``
     - el cursor de ``connections[using]``
   * - ``env.ref(xmlid)``
     - ``IrModelData.ref(xmlid)``
   * - ``self.envs`` (pila de entornos)
     - pila de ``ExitStack``, que entra y sale de los mismos ámbitos

La pila **se conserva**, no se aplana: ``_tag_root`` empuja el entorno del nodo
antes de despachar y lo saca en el ``finally``, igual que allá. Lo que cambia
es qué se empuja — un ámbito en vez de un objeto—; el anidamiento y su orden
son los mismos.

Qué NO se porta en este tramo, medido y con sucesor
===================================================

- ``convert_csv_import`` — BLOQUEADO por ``BaseModel.load`` — el importador de
  filas de la fuente (``odoo19c: odoo/models.py``) no está portado aquí
  (medido: ``grep -rn "def load(" src/orm/models.py`` → 0). El símbolo se
  declara y levanta con el motivo; su cuerpo se porta cuando exista ``load``.
  Tarea **#132**.
- ``jingtrang`` — la validación RelaxNG "bonita" de la fuente es un
  **fallback de mensajes**, no de validación: si el paquete está, corre
  ``pyjing`` para dar un error más legible. No se declara como dependencia
  (la fuente tampoco: su import va en ``try/except ImportError``), y el camino
  sin él —volcar ``relaxng.error_log``— sí se porta.

El esquema RelaxNG viaja con el producto
========================================

``src/import_xml.rng`` es copia de ``odoo19c: odoo/import_xml.rng`` (296
líneas), addon ``base``, licencia declarada **LGPL-3** (medido sobre su
``__manifest__.py``): copia con atribución, según DEC-KX-03. Es la gramática
que decide qué etiquetas admite un archivo de datos, y validarla **antes** de
interpretarla es lo que convierte un archivo mal formado en un error con línea
en vez de en un registro a medias.
"""
import base64
import io
import logging
import os.path
import pprint
import re
import subprocess
import time
from contextlib import ExitStack
from datetime import datetime, timedelta

import models
from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, connections
from lxml import builder, etree

try:
    import jingtrang
except ImportError:
    # Igual que la fuente (``odoo19c: convert.py:22-25``): es un fallback de
    # MENSAJES, no de validación. Sin él el error se explica volcando el
    # ``error_log`` de RelaxNG, que es el camino que este árbol recorre.
    jingtrang = None

import release
from orm import registry
from orm.commands import Command
from orm.domains import to_q
from orm.environments import context_scope, get_context, sudo, user_scope
from orm.fields_reference import Reference
from orm.fields_textual import Html
from tools import config
from tools.misc import SKIPPED_ELEMENT_TYPES, file_open, file_path
from tools.safe_eval import safe_eval

__all__ = [
    'convert_file', 'convert_sql_import',
    'convert_csv_import', 'convert_xml_import',
]

_logger = logging.getLogger(__name__)


class ParseError(Exception):
    """≙ ``ParseError`` — el error del cargador, con archivo y línea."""


def _model_of(model_str):
    """``env[model_str]`` — la clase, o ``ValueError`` si no está registrada.

    La fuente levanta ``KeyError`` desde su registro; aquí el mensaje nombra el
    modelo porque un archivo de datos que apunta a un modelo inexistente es el
    error más común de un addon a medio portar, y el nombre es la mitad de la
    respuesta.

    **Resuelve las dos formas de nombrar un modelo**, igual que
    ``IrModelData._model_class``: el ``_name`` de la referencia
    (``res.partner``) por ``orm.registry``, y la etiqueta de Django
    (``base.ResPartner``) por ``apps.get_model``. Un modelo propio del L0 no
    declara ``_name`` y sólo se alcanza por su etiqueta; y la columna
    ``ir.model.data.model`` guarda **la etiqueta**, así que un ``<record>``
    escrito contra una fila ya existente la nombra así.
    """
    model = registry.model_by_name(model_str)
    if model is not None:
        return model
    try:
        return apps.get_model(model_str)
    except (LookupError, ValueError):
        raise ValueError(
            f'Modelo desconocido en archivo de datos: {model_str!r}') from None


def _search(model, domain, using=DEFAULT_DB_ALIAS):
    """``env[modelo].search(dominio)`` — el dominio compilado a ``Q``."""
    return model.objects.using(using).filter(to_q(domain, model))


def _get_eval_context(self, model_str):
    """≙ ``_get_eval_context`` (``odoo19c: convert.py:41-54``).

    El espacio de nombres con que se evalúa un ``eval=`` de un archivo de
    datos. Se porta entero; ``obj`` sale sólo cuando el nodo declara modelo,
    igual que la fuente.
    """
    context = dict(
        Command=Command,
        time=time,
        DateTime=datetime,
        datetime=datetime,
        timedelta=timedelta,
        relativedelta=relativedelta,
        version=release.major_version,
        ref=self.id_get,
        pytz=None,
    )
    if model_str:
        model = _model_of(model_str)
        context['obj'] = lambda ids: model.objects.using(self.using).filter(
            pk__in=ids if isinstance(ids, (list, tuple, set)) else [ids])
    return context


def _fix_multiple_roots(node):
    """≙ ``_fix_multiple_roots`` (``odoo19c: convert.py:56-72``).

    «Surround the children of the ``node`` element of an XML field with a
    single root "data" element, to prevent having a document with multiple
    roots once parsed separately.»
    """
    real_nodes = [x for x in node if not isinstance(x, SKIPPED_ELEMENT_TYPES)]
    if len(real_nodes) > 1:
        data_node = etree.Element('data')
        for child in node:
            data_node.append(child)
        node.append(data_node)


def _eval_xml(self, node, using=DEFAULT_DB_ALIAS):
    """≙ ``_eval_xml`` (``odoo19c: convert.py:74-202``).

    El valor de un ``<field>``/``<value>``, según su ``type``. Los tres canales
    de la fuente se portan en su orden: ``search=`` (busca y devuelve ids),
    ``eval=`` (evalúa en el contexto de arriba) y el literal, que se
    interpreta según ``type``.

    El ``_process`` interno resuelve las interpolaciones ``%(xmlid)d`` que un
    ``arch`` de vista usa para referirse a otro registro, y su comentario de la
    fuente sobre ``%%`` se conserva porque explica una compatibilidad, no una
    elección.
    """
    if node.tag in ('field', 'value'):
        node_type = node.get('type', 'char')
        f_model = node.get('model')
        if f_search := node.get('search'):
            f_use = node.get('use', 'id')
            f_name = node.get('name')
            context = _get_eval_context(self, f_model)
            domain = safe_eval(f_search, context)
            model = _model_of(f_model)
            rows = _search(model, domain, using=using)
            if f_use != 'id':
                ids = list(rows.values_list(f_use, flat=True))
            else:
                ids = list(rows.values_list('pk', flat=True))
            field = model._meta.get_field(f_name) if _has_field(model, f_name) else None
            if isinstance(field, models.ManyToManyField):
                return ids
            f_val = False
            if len(ids):
                f_val = ids[0]
                if isinstance(f_val, tuple):
                    f_val = f_val[0]
            return f_val
        if a_eval := node.get('eval'):
            context = _get_eval_context(self, f_model)
            try:
                return safe_eval(a_eval, context)
            except Exception:
                _logger.error('Could not eval(%s) for %s in %s',
                              a_eval, node.get('name'), get_context())
                raise

        def _process(text):
            matches = re.finditer(r'[^%]%\((.*?)\)[ds]', text)
            done = set()
            for match in matches:
                found = match.group()[1:]
                if found in done:
                    continue
                done.add(found)
                rec_id = match[1]
                xid = self.make_xml_id(rec_id)
                if (record_id := self.idref.get(xid)) is None:
                    record_id = self.idref[xid] = self.id_get(xid)
                text = text.replace(found, str(record_id))
            # Quite weird but it's for (somewhat) backward compatibility sake
            return text.replace('%%', '%')

        if node_type == 'xml':
            _fix_multiple_roots(node)
            return '<?xml version="1.0"?>\n' + _process(
                ''.join(etree.tostring(n, encoding='unicode') for n in node))
        if node_type == 'html':
            return _process(''.join(
                etree.tostring(n, method='html', encoding='unicode')
                for n in node))

        if node.get('file'):
            if node_type == 'base64':
                with file_open(node.get('file'), 'rb') as handle:
                    return base64.b64encode(handle.read())
            with file_open(node.get('file')) as handle:
                data = handle.read()
        else:
            data = node.text or ''

        match node_type:
            case 'file':
                path = data.strip()
                try:
                    file_path(os.path.join(self.module, path))
                except FileNotFoundError:
                    raise FileNotFoundError(
                        f'No such file or directory: {path!r} in {self.module}'
                    ) from None
                return '%s,%s' % (self.module, path)
            case 'char':
                return data
            case 'int':
                stripped = data.strip()
                if stripped == 'None':
                    return None
                return int(stripped)
            case 'float':
                return float(data.strip())
            case 'list':
                return [_eval_xml(self, n, using=using)
                        for n in node.iterchildren('value')]
            case 'tuple':
                return tuple(_eval_xml(self, n, using=using)
                             for n in node.iterchildren('value'))
            case 'base64':
                raise ValueError('base64 type is only compatible with file data')
            case unknown:
                raise ValueError(f'Unknown type {unknown!r}')

    elif node.tag == 'function':
        model_str = node.get('model')
        model = _model_of(model_str)
        method_name = node.get('name')
        # determine arguments
        args = []
        kwargs = {}

        if a_eval := node.get('eval'):
            context = _get_eval_context(self, model_str)
            args = list(safe_eval(a_eval, context))
        for child in node:
            if child.tag == 'value' and child.get('name'):
                kwargs[child.get('name')] = _eval_xml(self, child, using=using)
            else:
                args.append(_eval_xml(self, child, using=using))

        # merge current context with context in kwargs
        with ExitStack() as stack:
            if 'context' in kwargs:
                stack.enter_context(context_scope(**kwargs.pop('context')))
            method = getattr(model, method_name)
            if not _is_model_method(method):
                # La fuente saca el primer argumento como ids y rebrowsea; aquí
                # el equivalente es acotar el queryset y llamar sobre él.
                record_ids, *args = args
                records = model.objects.using(using).filter(
                    pk__in=record_ids if isinstance(record_ids, (list, tuple))
                    else [record_ids])
                method = getattr(records, method_name)
            result = method(*args, **kwargs)
        if isinstance(result, models.QuerySet):
            return list(result.values_list('pk', flat=True))
        return result

    elif node.tag == 'test':
        return node.text


def _has_field(model, name):
    """¿El modelo declara ese campo? — ≙ ``name in model._fields``."""
    if not name:
        return False
    try:
        model._meta.get_field(name)
    except Exception:                    # noqa: BLE001 — FieldDoesNotExist
        return False
    return True


def _is_model_method(method):
    """≙ ``getattr(method, '_api_model', False)`` — ¿va sin registros?

    Allá el decorador ``@api.model`` marca el método; aquí el equivalente es
    que sea un ``classmethod`` o ``staticmethod`` del modelo, que es lo que
    significa "no necesita un recordset".
    """
    return getattr(method, '_api_model', False) or isinstance(
        getattr(method, '__self__', None), type)


def str2bool(value):
    """≙ ``str2bool`` (``odoo19c: convert.py:205-206``)."""
    return value.lower() not in ('0', 'false', 'off')


def nodeattr2bool(node, attr, default=False):
    """≙ ``nodeattr2bool`` (``odoo19c: convert.py:208-213``)."""
    if not node.get(attr):
        return default
    val = node.get(attr).strip()
    if not val:
        return default
    return str2bool(val)


class XmlImport:
    """≙ ``xml_import`` (``odoo19c: convert.py:216-666``), sus 17 símbolos.

    El nombre pasa de ``xml_import`` a ``XmlImport`` por
    ``identificadores-en-ingles.md`` y PEP 8: la fuente usa ``snake_case`` para
    una clase, que es su convención histórica y no la de este árbol. Se declara
    el alias ``xml_import`` al pie para que una cita de la fuente resuelva.

    ``self.using`` es el alias de base sobre el que carga: allá va implícito en
    ``env.cr``, aquí es explícito porque el registro es el módulo (la misma
    divergencia que ``ormcache`` declara al meter ``using`` en su clave).
    """

    DATA_ROOTS = ['odoo', 'data', 'openerp', 'kaupamex']

    def __init__(self, module, idref, mode, noupdate=False, xml_filename='',
                 using=DEFAULT_DB_ALIAS):
        """≙ ``__init__`` (``:641-660``).

        ``self.envs`` de la fuente es aquí ``self._scopes``: una pila de
        ``ExitStack``, cada uno con los ámbitos del nodo que lo empujó. El
        primero fija ``lang=None``, como el de la fuente.
        """
        self.mode = mode
        self.module = module
        self.using = using
        self.idref = {} if idref is None else idref
        self._noupdate = [noupdate]
        self._sequences = []
        self._scopes = []
        self.xml_filename = xml_filename
        self._tags = {
            'record': self._tag_record,
            'delete': self._tag_delete,
            'function': self._tag_function,
            'menuitem': self._tag_menuitem,
            'template': self._tag_template,
            'asset': self._tag_asset,
            **dict.fromkeys(self.DATA_ROOTS, self._tag_root),
        }

    # -- Entorno -------------------------------------------------------------

    def get_env(self, node, eval_context=None):
        """≙ ``get_env`` (``:217-231``) — el ámbito que el nodo declara.

        Devuelve un ``ExitStack`` **sin entrar**: quien lo empuja decide cuándo,
        y el ``finally`` de :meth:`_tag_root` lo cierra. Allá el equivalente es
        un objeto ``Environment`` nuevo; el anidamiento es el mismo.
        """
        stack = ExitStack()
        uid = node.get('uid')
        context = node.get('context')
        if uid:
            stack.enter_context(user_scope(self.id_get(uid)))
        if context:
            values = safe_eval(context, {
                'ref': self.id_get, **(eval_context or {})})
            stack.enter_context(context_scope(**values))
        return stack

    @property
    def noupdate(self):
        """≙ ``noupdate`` (``:632-634``) — el del nodo más interno."""
        return self._noupdate[-1]

    def next_sequence(self):
        """≙ ``next_sequence`` (``:636-640``) — 10 en 10, o ``None``."""
        value = self._sequences[-1]
        if value is not None:
            value = self._sequences[-1] = value + 10
        return value

    # -- Identificadores externos --------------------------------------------

    def make_xml_id(self, xml_id):
        """≙ ``make_xml_id`` (``:233-236``) — le pone el módulo si le falta."""
        if not xml_id or '.' in xml_id:
            return xml_id
        return '%s.%s' % (self.module, xml_id)

    def _test_xml_id(self, xml_id):
        """≙ ``_test_xml_id`` (``:238-246``).

        Dos invariantes: un identificador lleva **como mucho** un punto, y si
        nombra otro módulo, ese módulo tiene que estar instalado. La segunda es
        la que impide que un addon declare datos sobre uno que no está.
        """
        if '.' in xml_id:
            module, _, ident = xml_id.partition('.')
            assert '.' not in ident, (
                'The ID reference "%s" must contain maximum one dot. They are '
                'used to refer to other modules ID, in the form: '
                'module.record_id' % (xml_id,))
            if module != self.module:
                IrModule = _model_of('ir.module.module')
                count = IrModule.objects.using(self.using).filter(
                    name=module, state='installed').count()
                assert count == 1, (
                    'The ID "%s" refers to an uninstalled module' % (xml_id,))

    def id_get(self, id_str, raise_if_not_found=True):
        """≙ ``id_get`` (``:581-585``) — el id del registro que nombra."""
        id_str = self.make_xml_id(id_str)
        if id_str in self.idref:
            return self.idref[id_str]
        return self.model_id_get(id_str, raise_if_not_found)[1]

    def model_id_get(self, id_str, raise_if_not_found=True):
        """≙ ``model_id_get`` (``:587-589``) — la pareja (modelo, id)."""
        id_str = self.make_xml_id(id_str)
        IrModelData = _model_of('ir.model.data')
        return IrModelData._xmlid_to_res_model_res_id(
            id_str, raise_if_not_found=raise_if_not_found, using=self.using)

    # -- Las seis etiquetas --------------------------------------------------

    def _tag_delete(self, rec):
        """≙ ``_tag_delete`` (``:248-266``).

        Borra por búsqueda, por identificador, o por las dos. Los dos avisos de
        la fuente se portan enteros: una búsqueda que falla o un identificador
        que ya no está **no** abortan la carga —*"doesn't matter in this
        case"*—, sólo se registran.
        """
        d_model = rec.get('model')
        model = _model_of(d_model)
        pks = set()

        if d_search := rec.get('search'):
            context = _get_eval_context(self, d_model)
            try:
                pks.update(_search(model, safe_eval(d_search, context),
                                   using=self.using).values_list('pk', flat=True))
            except ValueError:
                _logger.warning('Skipping deletion for failed search `%r`',
                                d_search, exc_info=True)

        if d_id := rec.get('id'):
            try:
                pks.add(self.id_get(d_id))
            except ValueError:
                # d_id cannot be found. doesn't matter in this case
                _logger.warning('Skipping deletion for missing XML ID `%r`',
                                d_id, exc_info=True)

        if pks:
            model.objects.using(self.using).filter(pk__in=pks).delete()

    def _tag_function(self, rec):
        """≙ ``_tag_function`` (``:268-272``).

        Un ``<function>`` es una llamada, no un dato: en modo actualización con
        ``noupdate`` **no corre**, porque volver a ejecutarla sobre datos que el
        usuario ya tocó es lo que la bandera existe para evitar.
        """
        if self.noupdate and self.mode != 'init':
            return
        with self.get_env(rec):
            _eval_xml(self, rec, using=self.using)

    def _tag_menuitem(self, rec, parent=None):
        """≙ ``_tag_menuitem`` (``:274-334``).

        Un ``<menuitem>`` es azúcar sobre un ``ir.ui.menu``: se arman sus
        valores —padre, secuencia, acción, grupos— y se cargan por la misma
        vía que un ``<record>``. Los hijos se recorren después, con el id del
        padre ya conocido.
        """
        rec_id = rec.attrib['id']
        self._test_xml_id(rec_id)

        # The parent attribute was specified, if non-empty determine its ID,
        # otherwise explicitly make a top-level menu
        values = {
            'parent_id': False,
            'active': nodeattr2bool(rec, 'active', default=True),
        }

        if rec.get('sequence'):
            values['sequence'] = int(rec.get('sequence'))

        if parent is not None:
            values['parent_id'] = parent
        elif rec.get('parent'):
            values['parent_id'] = self.id_get(rec.attrib['parent'])
        elif rec.get('web_icon'):
            values['web_icon'] = rec.attrib['web_icon']

        if rec.get('name'):
            values['name'] = rec.attrib['name']

        if rec.get('action'):
            a_action = rec.attrib['action']
            if '.' not in a_action:
                a_action = '%s.%s' % (self.module, a_action)
            IrModelData = _model_of('ir.model.data')
            with sudo():
                act = IrModelData.ref(a_action, using=self.using)
            values['action'] = '%s,%d' % (act.type, act.pk)
            if (not values.get('name')
                    and act.type.endswith(('act_window', 'wizard', 'url',
                                           'client', 'server'))
                    and act.name):
                values['name'] = act.name

        if not values.get('name'):
            values['name'] = rec_id or '?'

        groups = []
        for group in rec.get('groups', '').split(','):
            if group.startswith('-'):
                groups.append(Command.unlink(self.id_get(group[1:])))
            elif group:
                groups.append(Command.link(self.id_get(group)))
        if groups:
            values['group_ids'] = groups

        data = {
            'xml_id': self.make_xml_id(rec_id),
            'values': values,
            'noupdate': self.noupdate,
        }
        menu = _model_of('ir.ui.menu')._load_records(
            [data], self.mode == 'update', using=self.using)[0]
        for child in rec.iterchildren('menuitem'):
            self._tag_menuitem(child, parent=menu.pk)

    def _tag_record(self, rec, extra_vals=None):
        """≙ ``_tag_record`` (``:336-465``) — el corazón del cargador.

        Arma los valores del registro leyendo cada ``<field>`` por sus tres
        canales (``search=``, ``ref=``, literal), y delega en
        ``_load_records``, que decide crear o actualizar. Las dos guardas de
        ``noupdate`` de la fuente se portan enteras:

        1. En modo actualización con ``noupdate``, si el identificador ya
           existe **no se toca** — sólo se anota su id, *"can be useful"*.
        2. Un identificador de **otro** módulo que no existe se rechaza, salvo
           que el nodo declare ``forcecreate``: crear datos ajenos en silencio
           deja un registro que su dueño borrará al actualizarse.
        """
        rec_model = rec.get('model')
        rec_id = rec.get('id', '')
        model = _model_of(rec_model)

        with ExitStack() as stack:
            stack.enter_context(self.get_env(rec))
            if self.xml_filename and rec_id:
                stack.enter_context(context_scope(
                    install_mode=True,
                    install_module=self.module,
                    install_filename=self.xml_filename,
                    install_xmlid=rec_id,
                ))
            return self._tag_record_inner(rec, model, rec_model, rec_id,
                                          extra_vals)

    def _tag_record_inner(self, rec, model, rec_model, rec_id, extra_vals):
        """La mitad de :meth:`_tag_record` que corre YA dentro de su ámbito.

        No tiene contraparte en la fuente y es consecuencia directa de la
        divergencia del entorno: allá ``model.with_context(...)`` devuelve otro
        recordset y el cuerpo sigue en la misma función; aquí el ámbito es un
        ``with``, y partir el cuerpo evita indentarlo entero. La lógica es la
        de ``:336-465``, sin cambios.
        """
        IrModelData = _model_of('ir.model.data')
        self._test_xml_id(rec_id)
        xid = self.make_xml_id(rec_id)

        # in update mode, the record won't be updated if the data node
        # explicitly opt-out using @noupdate="1". A second check will be
        # performed in model._load_records() using the record's ir.model.data
        # `noupdate` field.
        if self.noupdate and self.mode != 'init':
            # check if the xml record has no id, skip
            if not rec_id:
                return None

            if record := IrModelData._load_xmlid(xid, using=self.using):
                for child in rec.xpath('.//record[@id]'):
                    sub_xid = child.get('id')
                    self._test_xml_id(sub_xid)
                    sub_xid = self.make_xml_id(sub_xid)
                    if sub_record := IrModelData._load_xmlid(
                            sub_xid, using=self.using):
                        self.idref[sub_xid] = sub_record.pk

                # if the resource already exists, don't update it but store
                # its database id (can be useful)
                self.idref[xid] = record.pk
                return None
            elif not nodeattr2bool(rec, 'forcecreate', True):
                # if it doesn't exist and we shouldn't create it, skip it
                return None
            # else create it normally

        foreign_record_to_create = False
        if xid and xid.partition('.')[0] != self.module:
            # updating a record created by another module
            record = IrModelData._load_xmlid(xid, using=self.using)
            if not record and not (foreign_record_to_create := nodeattr2bool(
                    rec, 'forcecreate')):
                # Allow foreign records if explicitely stated
                if self.noupdate and not nodeattr2bool(rec, 'forcecreate', True):
                    # if it doesn't exist and we shouldn't create it, skip it
                    return None
                raise ValueError('Cannot update missing record %r' % xid)

        res = {}
        sub_records = []
        for field in rec.iterchildren('field'):
            f_name = field.get('name')
            if '@' in f_name:
                continue  # used for translations
            f_model = field.get('model')
            field_obj = model._meta.get_field(f_name) if _has_field(
                model, f_name) else None
            if not f_model and field_obj is not None:
                related = getattr(field_obj, 'related_model', None)
                f_model = registry.name_of(related) if related else None
            f_use = field.get('use', '') or 'id'
            f_val = False

            if f_search := field.get('search'):
                context = _get_eval_context(self, f_model)
                domain = safe_eval(f_search, context)
                assert f_model, 'Define an attribute model="..." in your .XML file!'
                found = _search(_model_of(f_model), domain, using=self.using)
                if isinstance(field_obj, models.ManyToManyField):
                    key = 'pk' if f_use == 'id' else f_use
                    f_val = [Command.set(list(found.values_list(key, flat=True)))]
                else:
                    first = found.first()
                    if first is not None:
                        f_val = first.pk if f_use == 'id' else getattr(first, f_use)
            elif f_ref := field.get('ref'):
                if _is_reference_field(field_obj):
                    val = self.model_id_get(f_ref)
                    f_val = val[0] + ',' + str(val[1])
                else:
                    f_val = self.id_get(f_ref, raise_if_not_found=nodeattr2bool(
                        rec, 'forcecreate', True))
                    if not f_val:
                        _logger.warning(
                            'Skipping creation of %r because %s=%r could not '
                            'be resolved', xid, f_name, f_ref)
                        return None
            else:
                f_val = _eval_xml(self, field, using=self.using)
                if field_obj is not None:
                    f_val = _coerce(field_obj, f_val, field, f_name)
                    if isinstance(field_obj, models.ManyToOneRel):
                        for child in field.iterchildren('record'):
                            sub_records.append(
                                (child, field_obj.field.name))
                        if isinstance(f_val, str):
                            # We do not want to write on the field since we
                            # will write on the childrens' parents later
                            continue
            res[f_name] = f_val

        if extra_vals:
            res.update(extra_vals)
        if 'sequence' not in res and _has_field(model, 'sequence'):
            sequence = self.next_sequence()
            if sequence:
                res['sequence'] = sequence

        data = dict(xml_id=xid, values=res, noupdate=self.noupdate)
        with ExitStack() as stack:
            if foreign_record_to_create:
                stack.enter_context(context_scope(
                    foreign_record_to_create=foreign_record_to_create))
            record = model._load_records(
                [data], self.mode == 'update', using=self.using)[0]
        if xid:
            self.idref[xid] = record.pk
        for child_rec, inverse_name in sub_records:
            self._tag_record(child_rec, extra_vals={inverse_name: record.pk})
        return rec_model, record.pk

    def _tag_template(self, el):
        """≙ ``_tag_template`` (``:467-546``).

        «This helper transforms a ``<template>`` element into a ``<record>`` and
        forwards it.» Se porta entero, incluida la regla de ``active``: puesta
        en el nodo raíz vale **sólo si no se está actualizando**, para que una
        versión nueva del módulo no reactive una vista que alguien apagó.
        """
        tpl_id = el.get('id', el.get('t-name'))
        full_tpl_id = tpl_id
        if '.' not in full_tpl_id:
            full_tpl_id = '%s.%s' % (self.module, tpl_id)
        # set the full template name for qweb <module>.<id>
        if not el.get('inherit_id'):
            el.set('t-name', full_tpl_id)
            el.tag = 't'
        else:
            el.tag = 'data'
        el.attrib.pop('id', None)

        model = ('theme.ir.ui.view' if self.module.startswith('theme_')
                 else 'ir.ui.view')
        record_attrs = {'id': tpl_id, 'model': model}
        for att in ['forcecreate', 'context']:
            if att in el.attrib:
                record_attrs[att] = el.attrib.pop(att)

        Field = builder.E.field
        name = el.get('name', tpl_id)

        record = etree.Element('record', attrib=record_attrs)
        record.append(Field(name, name='name'))
        record.append(Field(full_tpl_id, name='key'))
        record.append(Field('qweb', name='type'))
        if 'track' in el.attrib:
            record.append(Field(el.get('track'), name='track'))
        if 'priority' in el.attrib:
            record.append(Field(el.get('priority'), name='priority'))
        if 'inherit_id' in el.attrib:
            record.append(Field(name='inherit_id', ref=el.get('inherit_id')))
        if 'website_id' in el.attrib:
            record.append(Field(name='website_id', ref=el.get('website_id')))
        if 'key' in el.attrib:
            record.append(Field(el.get('key'), name='key'))

        # If the "active" value is set on the root node (instead of an inner
        # <field>), it is treated as the value for the "active" field but only
        # when *not updating*.
        if el.get('active') in ('True', 'False'):
            view_id = self.id_get(tpl_id, raise_if_not_found=False)
            if self.mode != 'update' or not view_id:
                record.append(Field(name='active', eval=el.get('active')))

        if el.get('customize_show') in ('True', 'False'):
            record.append(Field(name='customize_show',
                                eval=el.get('customize_show')))
        groups = el.attrib.pop('groups', None)
        if groups:
            grp_lst = ["ref('%s')" % x for x in groups.split(',')]
            record.append(Field(
                name='group_ids',
                eval='[Command.set([' + ', '.join(grp_lst) + '])]'))
        if el.get('primary') == 'True':
            # Pseudo clone mode, we'll set the t-name to the full canonical xmlid
            el.append(builder.E.xpath(
                builder.E.attribute(full_tpl_id, name='t-name'),
                expr='.', position='attributes'))
            record.append(Field('primary', name='mode'))
        # inject complete <template> element (after changing node name) into
        # the ``arch`` field
        record.append(Field(el, name='arch', type='xml'))

        return self._tag_record(record)

    def _tag_asset(self, el):
        """≙ ``_tag_asset`` (``:548-579``).

        «Transforms an ``<asset>`` element into a ``<record>`` and forwards
        it.» Misma regla de ``active`` que ``<template>``, por el mismo motivo.
        """
        asset_id = el.get('id')
        Field = builder.E.field

        record = etree.Element('record', attrib={
            'id': asset_id,
            'model': ('theme.ir.asset' if self.module.startswith('theme_')
                      else 'ir.asset'),
        })

        name = el.get('name', asset_id)
        record.append(Field(name, name='name'))

        # E.g. <bundle directive="prepend">web.assets_frontend</bundle>
        bundle_el = el.find('bundle')
        record.append(Field(bundle_el.text, name='bundle'))
        if 'directive' in bundle_el.attrib:
            record.append(Field(bundle_el.get('directive'), name='directive'))

        # E.g. <path>website/static/src/snippets/s_share/000.scss</path>
        record.append(Field(el.find('path').text, name='path'))

        if el.get('active') in ('True', 'False'):
            record_id = self.id_get(asset_id, raise_if_not_found=False)
            if self.mode != 'update' or not record_id:
                record.append(Field(name='active', eval=el.get('active')))

        for child in el.iterchildren('field'):
            record.append(child)

        return self._tag_record(record)

    # -- El recorrido --------------------------------------------------------

    def _tag_root(self, el):
        """≙ ``_tag_root`` (``:591-627``).

        Empuja el ámbito, el ``noupdate`` y la secuencia del nodo, despacha
        cada hijo por su etiqueta, y los saca en el ``finally``. Los tres
        manejadores de excepción se portan con su forma: ``ParseError`` sube
        tal cual, un ``ValidationError`` se envuelve nombrando archivo, línea y
        contexto, y cualquier otra se envuelve con el XML del nodo — que es lo
        que convierte *"algo falló al instalar"* en *"esta línea de este
        archivo"*.
        """
        for rec in el:
            handler = self._tags.get(rec.tag)
            if handler is None:
                continue

            self._scopes.append(self.get_env(el))
            self._scopes[-1].__enter__()
            self._noupdate.append(nodeattr2bool(el, 'noupdate', self.noupdate))
            self._sequences.append(
                0 if nodeattr2bool(el, 'auto_sequence', False) else None)
            try:
                handler(rec)
            except ParseError:
                raise
            except ValidationError as err:
                msg = (
                    'while parsing {file}:{viewline}\n{err}\n\n'
                    'View error context:\n{context}\n'.format(
                        file=rec.getroottree().docinfo.URL,
                        viewline=rec.sourceline,
                        context=pprint.pformat(
                            getattr(err, 'context', None) or '-no context-'),
                        err=err.args[0]))
                _logger.debug(msg, exc_info=True)
                raise ParseError(msg) from None
            except Exception as exc:
                raise ParseError(
                    'while parsing %s:%s, somewhere inside\n%s' % (
                        rec.getroottree().docinfo.URL,
                        rec.sourceline,
                        etree.tostring(rec, encoding='unicode').rstrip(),
                    )) from exc
            finally:
                self._noupdate.pop()
                self._sequences.pop()
                self._scopes.pop().__exit__(None, None, None)

    def parse(self, de):
        """≙ ``parse`` (``:662-664``) — la raíz tiene que ser una de las suyas."""
        assert de.tag in self.DATA_ROOTS, (
            'Root xml tag must be <odoo>, <data>, <openerp> or <kaupamex>.')
        self._tag_root(de)


#: Alias del nombre de la fuente, para que una cita de ``odoo19c:`` resuelva.
xml_import = XmlImport


def _is_reference_field(field_obj):
    """¿Es un campo ``reference`` (modelo + id en una cadena)?

    ≙ ``model._fields[f_name].type == 'reference'``. Aquí ese tipo lo porta
    ``orm.fields.Reference``; se pregunta por la clase y no por una cadena.
    """
    return isinstance(field_obj, Reference)


def _coerce(field_obj, f_val, field_node, f_name):
    """≙ el bloque de coerción por tipo de ``_tag_record`` (``:429-448``).

    Un archivo de datos trae todo como texto; la fuente lo convierte según el
    tipo del campo. Se extrae a función porque aquí el ``match`` sobre el tipo
    es un ``isinstance`` sobre la clase, y en línea partiría el flujo del
    lector.
    """
    if isinstance(field_obj, models.ForeignKey):
        return int(f_val) if f_val else False
    if isinstance(field_obj, models.IntegerField):
        return int(f_val)
    if isinstance(field_obj, (models.FloatField, models.DecimalField)):
        return float(f_val)
    if isinstance(field_obj, models.BooleanField) and isinstance(f_val, str):
        return str2bool(f_val)
    if _is_html_field(field_obj) and field_node.get('type') == 'xml':
        _logger.warning('HTML field %r is declared as `type="xml"`', f_name)
    return f_val


def _is_html_field(field_obj):
    """¿Es un ``fields.Html``? — la identidad de tipo de H-API-700."""
    return isinstance(field_obj, Html)


def convert_file(env_module, filename, idref, mode='update', noupdate=False,
                 pathname=None, using=DEFAULT_DB_ALIAS):
    """≙ ``convert_file`` (``odoo19c: convert.py:666-698``).

    Despacha por extensión. El ``kind`` de la fuente **no se porta**: allá ya
    está marcado ``DeprecationWarning`` en 19 y su único efecto es avisar.

    La firma pierde el primer parámetro ``env`` por la divergencia del entorno
    y gana ``using``; ``module`` conserva su sitio.
    """
    module = env_module
    if pathname is None:
        pathname = os.path.join(module, filename)
    ext = os.path.splitext(filename)[1].lower()

    with file_open(pathname, 'rb') as handle:
        if ext == '.csv':
            convert_csv_import(module, pathname, handle.read(), idref, mode,
                               noupdate, using=using)
        elif ext == '.sql':
            convert_sql_import(handle, using=using)
        elif ext == '.xml':
            convert_xml_import(module, handle, idref, mode, noupdate,
                               using=using)
        elif ext == '.js':
            pass  # .js files are valid but ignored here.
        else:
            raise ValueError("Can't load unknown file type %s." % filename)


def convert_sql_import(fp, using=DEFAULT_DB_ALIAS):
    """≙ ``convert_sql_import`` (``:700-701``) — ejecuta el archivo tal cual."""
    with connections[using].cursor() as cursor:
        cursor.execute(fp.read().decode() if isinstance(fp.read.__self__, io.IOBase)
                       else fp.read())


def convert_csv_import(module, fname, csvcontent, idref=None, mode='init',
                       noupdate=False, using=DEFAULT_DB_ALIAS):
    """≙ ``convert_csv_import`` (``:703-758``).

    Porte BLOQUEADO — 0 de 1 símbolos. BLOQUEADO por ``BaseModel.load`` — el
    importador de filas de la fuente, que es quien recibe ``(fields, datas)``
    y aplica la misma resolución de identificadores que el XML pero por
    columnas. Medido: ``grep -rn "def load(" src/orm/models.py`` → **0**.

    El símbolo se declara con su nombre y su firma para que el despachador de
    :func:`convert_file` no tenga un hueco silencioso, y levanta nombrando el
    bloqueo. Su cuerpo se porta con ``load``; tarea **#132**.
    """
    raise NotImplementedError(
        'convert_csv_import necesita BaseModel.load, que aún no está portado '
        '(tarea #132). Los datos en CSV se cargan hoy por migración.')


def convert_xml_import(module, xmlfile, idref=None, mode='init',
                       noupdate=False, using=DEFAULT_DB_ALIAS):
    """≙ ``convert_xml_import`` (``:760-792``).

    Valida contra ``import_xml.rng`` **antes** de interpretar, y sólo entonces
    construye el :class:`XmlImport` y lo recorre. El orden importa: un archivo
    que no cumple la gramática se rechaza entero en vez de dejar media carga
    aplicada.

    El camino ``jingtrang`` de la fuente es un fallback de **mensajes** (si el
    paquete está, ``pyjing`` explica mejor el fallo); se conserva con su
    ``try/except ImportError``, igual que allá.
    """
    doc = etree.parse(xmlfile)
    schema = os.path.join(config.root_path(), 'import_xml.rng')
    relaxng = etree.RelaxNG(etree.parse(schema))
    try:
        relaxng.assert_(doc)
    except Exception:
        _logger.exception(
            "The XML file '%s' does not fit the required schema!",
            getattr(xmlfile, 'name', xmlfile))
        if jingtrang:
            proc = subprocess.run(
                ['pyjing', schema, xmlfile.name], stdout=subprocess.PIPE,
                check=False)
            _logger.warning(proc.stdout.decode())
        else:
            for err in relaxng.error_log:
                _logger.warning(err)
            _logger.info("Install 'jingtrang' for more precise and useful "
                         'validation messages.')
        raise

    if isinstance(xmlfile, str):
        xml_filename = xmlfile
    else:
        xml_filename = getattr(xmlfile, 'name', '')
    obj = XmlImport(module, idref, mode, noupdate=noupdate,
                    xml_filename=xml_filename, using=using)
    obj.parse(doc.getroot())
