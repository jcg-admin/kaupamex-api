"""``res.config`` y ``res.config.settings`` — el motor de configuración por convención.

Adaptación de ``odoo/addons/base/models/res_config.py``
(``odoo-tools@bf077302``, ``odoo19c:``, 567 líneas). Dos clases:
``ResConfig``, el asistente base de un paso de configuración, y
``ResConfigSettings``, que es lo interesante — un formulario cuyos campos
**se comportan según cómo se llaman**.

La convención, que es todo el archivo
=====================================

Un campo de un formulario de ajustes no declara qué hace: lo dice su prefijo,
y ``execute`` lo interpreta.

=================== ======================================================
Prefijo del campo   Qué hace ``execute`` con su valor
=================== ======================================================
``default_XXX``     fija el valor por defecto **global** del campo ``XXX``
                    en el modelo que diga ``default_model``
``group_XXX``       añade o quita ``implied_group`` de los grupos implicados
                    por ``group`` (por defecto, el de empleado)
``module_XXX``      instala el módulo ``XXX`` si el valor es verdadero
(sin prefijo, pero   guarda el valor en un parámetro de sistema
con ``config_parameter``)
el resto            lo resuelve ``set_values``, que se sobreescribe
=================== ======================================================

Y ``default_get`` hace el camino inverso: lee el estado actual de cada
categoría para llenar el formulario. Las dos direcciones tienen que coincidir
o el formulario muestra una cosa y guarda otra.

Cómo se declaran los atributos extra en este árbol
==================================================

La referencia cuelga atributos del propio campo:
``fields.Char(..., config_parameter='my.parameter')``. Eso su ORM lo admite —
de hecho ``_valid_field_parameter`` (línea 152) existe **precisamente** para
declararlos válidos, lo que confirma que son no-estándar incluso allá.

Un campo de Django rechaza kwargs desconocidos, así que los atributos extra se
declaran en un dict de clase, ``field_attrs``:

.. code-block:: python

    class MySettings(ResConfigSettings):
        config_qux = fields.Char(max_length=64, blank=True, default='')
        field_attrs = {
            'config_qux': {'config_parameter': 'my.parameter'},
            'default_foo': {'default_model': 'my.model'},
            'group_bar': {'group': 'base.group_user',
                          'implied_group': 'my.group'},
        }

La **convención de nombres no cambia** — que es lo que el archivo aporta—;
sólo cambia dónde se guarda el metadato que la acompaña. ``classify_fields``
levanta el mismo error que la fuente cuando falta: un ``default_`` sin
``default_model`` o un ``group_`` sin ``implied_group`` es un formulario que
no puede guardar, y descubrirlo al guardar es tarde.

Relación con lo que este árbol ya tiene
=======================================

``res_config_settings.py`` de este repo define ``SiteSettings``, y su
docstring se declaraba *"contraparte de ``res.config.settings``"*. **No lo
es**, y se corrige en el mismo commit: ``SiteSettings`` es una fila **tipada
y persistente** (identidad del sitio, IVA, umbrales) con validación de campo;
``res.config.settings`` es un formulario **transitorio** cuyos campos se
interpretan por su nombre y cuyo efecto se escribe en otros sitios
(``ir.default``, grupos, parámetros). Son piezas distintas que coexisten.

Nota de nombre: en la referencia **no existe** ``res_config_settings.py``
(``ls odoo19c: odoo/addons/base/models/ | grep res_config`` → sólo
``res_config.py``). El archivo de este árbol es propio; conservarlo con ese
nombre junto a este ``res_config.py`` es lo que hace útil aclarar la
diferencia.

Qué NO se porta, con su medición
================================

- **La mitad de instalación de módulos de ``execute``.**
  ``_install_modules`` llama a ``button_immediate_install``, y
  ``ir_module.py`` ya declara que este árbol **no tiene instalador**: su
  ``state`` sale de ``INSTALLED_APPS`` y sólo admite tres valores
  (``uninstallable`` / ``uninstalled`` / ``installed``, ``ir_module.py:87-94``),
  frente a los seis de la referencia. Sin ``to install`` / ``to upgrade`` no
  hay transición que disparar. La categoría ``module`` **sí** se clasifica y
  **sí** se lee (``default_get`` refleja si está instalado); lo que no existe
  es el efecto de escritura.
- **``create`` con su poda de campos ``related``** (líneas 526-557): evita
  reescribir valores que no cambiaron usando ``convert_to_cache`` /
  ``convert_to_record`` del ORM de Odoo. Es una optimización atada a su motor
  de campos calculados; Django no recalcula en cadena al escribir, así que la
  poda no tiene qué evitar.
- **``get_option_path`` / ``_compute_display_name`` / ``cancel``**: resuelven
  un ``xml_id`` de menú contra ``ir.model.data`` y buscan la acción de ventana
  del modelo. Medido: ``ir.model.data`` existe desde ``api@b618a6b`` pero
  **nadie la puebla** —falta el cargador declarativo—, así que resolver un
  ``xml_id`` hoy devuelve vacío siempre. Entran con el cargador.
- **``get_config_warning`` completo**: sustituye ``%(field:...)s`` y
  ``%(menu:...)s`` por el nombre legible del campo y la ruta del menú. La
  mitad del campo **sí** se porta (sale del ``verbose_name``); la del menú
  depende del ``xml_id``, o sea del cargador. Se porta la sustitución con la
  mitad disponible y se deja el marcador de menú intacto en vez de borrarlo:
  un mensaje al que le falta la ruta sigue siendo legible; uno al que le
  desaparece el marcador miente sobre lo que el autor escribió.
- **``action_open_template_user``**: abre la ficha de un usuario plantilla
  resolviendo dos ``xml_id``. Mismo bloqueo que arriba.
"""
import logging
import re

import models
from django.core.exceptions import ValidationError

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_default import IrDefault
from addons.base.models.ir_module import IrModule
from addons.base.models.res_groups import ResGroups

_logger = logging.getLogger(__name__)

#: Grupo implicante por defecto de un campo ``group_XXX`` — el de empleado.
DEFAULT_GROUP = 'base.group_user'

#: ``regex_path`` de ``get_config_warning``, verbatim de la fuente.
CONFIG_WARNING_PATTERN = re.compile(r'%\(((?:menu|field):[a-z_\.]*)\)s', re.I)

#: Categorías que devuelve ``classify_fields``, en el orden de la fuente.
FIELD_CATEGORIES = ('default', 'group', 'module', 'config', 'other')

#: Tipos admitidos en un campo con ``config_parameter``, verbatim.
CONFIG_PARAMETER_TYPES = (
    'boolean', 'integer', 'float', 'char', 'selection', 'many2one', 'datetime',
)


class ConfigWarning(ValidationError):
    """Aviso de configuración con la ruta del panel que lo resuelve.

    La fuente devuelve ``RedirectWarning`` cuando el mensaje cita un menú, y
    ``UserError`` cuando no. Aquí una sola excepción lleva el ``menu_ref``
    cuando lo hay: sin resolutor de ``xml_id`` no hay ``action_id`` al que
    redirigir, pero la referencia al menú sí se conserva para quien la
    resuelva arriba.
    """

    def __init__(self, message, menu_ref=None):
        super().__init__(message)
        self.menu_ref = menu_ref


class ResConfig(models.Model):
    """``res.config`` — un paso de configuración.

    Transitorio en la fuente (``TransientModel``): no persiste, es el estado
    de un formulario. Aquí ``managed = False`` dice lo mismo — sin tabla.
    """

    class Meta:
        abstract = True

    def start(self):
        """``start`` — arranca el asistente."""
        return self.next()

    def next(self):
        """``next`` — recarga la página de ajustes."""
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def execute(self):
        """``execute`` — qué hace este paso. **Debe** sobreescribirse.

        La fuente levanta ``NotImplementedError`` a propósito: un paso de
        configuración que no declara su efecto es un botón que no hace nada.
        """
        raise NotImplementedError(
            'Un paso de configuración debe implementar execute().')

    def cancel(self):
        """``cancel`` — qué hace el botón "Omitir". No-op por defecto."""
        return None

    def action_next(self):
        """``action_next`` — ejecuta; si no devuelve acción, avanza."""
        return self.execute() or self.next()

    def action_skip(self):
        """``action_skip`` — cancela; si no devuelve acción, avanza."""
        return self.cancel() or self.next()

    def action_cancel(self):
        """``action_cancel`` — igual que omitir, con otro botón."""
        return self.cancel() or self.next()


class ResConfigSettings(ResConfig):
    """``res.config.settings`` — formulario de ajustes por convención.

    Ver el docstring del módulo: los prefijos ``default_`` / ``group_`` /
    ``module_`` y el atributo ``config_parameter`` deciden qué hace cada
    campo.
    """

    #: Atributos extra por campo. La referencia los cuelga del propio campo;
    #: un campo Django no admite kwargs desconocidos, así que viven aquí.
    field_attrs = {}

    class Meta:
        abstract = True

    # --- Clasificación ---------------------------------------------------

    @classmethod
    def attrs_for(cls, fname):
        """Atributos extra declarados para ``fname`` (dict, posiblemente vacío)."""
        return cls.field_attrs.get(fname, {})

    @classmethod
    def settings_field_names(cls):
        """Los campos concretos del formulario, sin la clave primaria."""
        return [
            field.name for field in cls._meta.get_fields()
            if getattr(field, 'concrete', False) and not field.primary_key
        ]

    @classmethod
    def classify_fields(cls, fnames=None):
        """``_get_classified_fields`` — clasifica los campos por categoría.

        Devuelve un dict con las cinco claves de ``FIELD_CATEGORIES``:

        - ``default``: ``[(nombre, modelo, campo), ...]``
        - ``group``:   ``[(nombre, [grupos], grupo_implicado), ...]``
        - ``module``:  ``[(nombre, nombre_modulo), ...]``
        - ``config``:  ``[(nombre, clave_parametro), ...]``
        - ``other``:   ``[nombre, ...]``

        Levanta si falta el metadato obligatorio, igual que la fuente: un
        ``default_`` sin ``default_model`` no se puede guardar, y enterarse
        al guardar es tarde.
        """
        if fnames is None:
            fnames = cls.settings_field_names()

        classified = {key: [] for key in FIELD_CATEGORIES}
        for name in fnames:
            attrs = cls.attrs_for(name)
            if name.startswith('default_'):
                model = attrs.get('default_model')
                if not model:
                    raise ValueError(
                        f'El campo {name} no declara "default_model" en '
                        f'field_attrs.')
                classified['default'].append((name, model, name[len('default_'):]))
            elif name.startswith('group_'):
                implied = attrs.get('implied_group')
                if not implied:
                    raise ValueError(
                        f'El campo {name} no declara "implied_group" en '
                        f'field_attrs.')
                groups = [
                    part.strip()
                    for part in attrs.get('group', DEFAULT_GROUP).split(',')
                    if part.strip()
                ]
                classified['group'].append((name, groups, implied))
            elif name.startswith('module_'):
                classified['module'].append((name, name[len('module_'):]))
            elif attrs.get('config_parameter'):
                classified['config'].append((name, attrs['config_parameter']))
            else:
                classified['other'].append(name)
        return classified

    # --- Lectura del estado actual ---------------------------------------

    @classmethod
    def get_values(cls):
        """``get_values`` — valores de los campos que no son de las categorías.

        Devuelve ``{}``. Contrato de la fuente para que se sobreescriba, no
        un hueco.
        """
        return {}

    @classmethod
    def current_values(cls, fnames=None):
        """``default_get`` — el estado actual, para llenar el formulario.

        Es el **inverso** de ``apply_values``. Las dos direcciones tienen que
        coincidir; si divergen, el formulario muestra una cosa y guarda otra.
        """
        classified = cls.classify_fields(fnames)
        values = {}

        for name, model, field in classified['default']:
            stored = IrDefault.get_default(model, field)
            if stored is not None:
                values[name] = stored

        for name, group_refs, implied in classified['group']:
            values[name] = cls._group_is_implied(group_refs, implied)

        for name, module_name in classified['module']:
            module = IrModule.objects.filter(name=module_name).first()
            values[name] = (
                module is not None and module.state == IrModule.STATE_INSTALLED)

        for name, param in classified['config']:
            values[name] = SystemParameter.get_param(param)

        values.update(cls.get_values())
        return values

    @staticmethod
    def _group_is_implied(group_refs, implied_ref):
        """¿Todos los grupos de ``group_refs`` implican a ``implied_ref``?

        La fuente usa ``all(...)``, no ``any(...)``, y la diferencia importa:
        la casilla sólo sale marcada si **todos** los grupos citados conceden
        el implicado. Con ``any`` bastaría uno y desmarcarla no quitaría el
        permiso de los demás.

        Los identificadores llegan como ``xml_id`` en la referencia; aquí se
        resuelven por ``name``, porque no hay cargador que puebla
        ``ir.model.data`` (ver el docstring del módulo).
        """
        implied = ResGroups.objects.filter(name=implied_ref).first()
        if implied is None:
            return False
        groups = list(ResGroups.objects.filter(name__in=group_refs))
        if not groups:
            return False
        return all(
            implied.pk in {row.pk for row in group.all_implied_ids}
            for group in groups
        )

    # --- Escritura del efecto --------------------------------------------

    def set_values(self):
        """``set_values`` — efecto de los campos sin categoría. Sobreescribible."""
        return None

    def apply_values(self):
        """``set_values`` + ``execute`` de la fuente, sin la parte de módulos.

        Escribe cada categoría en su destino: los ``default_`` en
        ``ir.default``, los ``group_`` aplicando o quitando el grupo
        implicado, y los ``config_parameter`` en el parámetro de sistema.
        Sólo escribe lo que **cambió**, igual que la fuente — reescribir un
        valor idéntico dispara efectos en cascada sin ganar nada.

        La instalación de módulos no se ejecuta: ver el docstring del módulo.
        """
        classified = self.classify_fields()
        current = self.current_values()

        for name, model, field in classified['default']:
            value = getattr(self, name)
            if current.get(name) != value:
                IrDefault.set_default(model, field, value)

        # Ordenar por el valor, como la fuente: aplicar antes de quitar deja
        # el conjunto de grupos en el mismo estado con independencia del
        # orden de declaración de los campos.
        for name, group_refs, implied_ref in sorted(
                classified['group'], key=lambda item: bool(getattr(self, item[0]))):
            value = bool(getattr(self, name))
            if current.get(name) == value:
                continue
            implied = ResGroups.objects.filter(name=implied_ref).first()
            if implied is None:
                _logger.warning(
                    'El campo %s implica el grupo %r, que no existe.',
                    name, implied_ref)
                continue
            for group in ResGroups.objects.filter(name__in=group_refs):
                if value:
                    group.apply_group(implied)
                else:
                    group.remove_group(implied)

        for name, param in classified['config']:
            value = getattr(self, name)
            if isinstance(value, str):
                # La fuente recorta los espacios: guardar una clave de API con
                # espacios alrededor produce fallos difíciles de ver.
                value = value.strip()
            stored = SystemParameter.get_param(param)
            if stored == value or stored == str(value):
                continue
            SystemParameter.set_param(param, value)

        self.set_values()

    def copy(self, *args, **kwargs):
        """``copy`` — un formulario de ajustes no se duplica."""
        raise ValidationError('No se puede duplicar una configuración.')

    # --- Mensajes de aviso ------------------------------------------------

    @classmethod
    def option_name(cls, full_field_name):
        """``get_option_name`` — nombre legible de un campo ``modelo.campo``.

        Aquí el nombre legible es el ``verbose_name`` de Django, que es el
        equivalente del ``string`` de Odoo.
        """
        _model_name, field_name = full_field_name.rsplit('.', 1)
        try:
            field = cls._meta.get_field(field_name)
        except Exception:
            _logger.warning('Campo desconocido en un aviso: %r', full_field_name)
            return field_name
        return str(getattr(field, 'verbose_name', '') or field_name)

    @classmethod
    def config_warning(cls, msg):
        """``get_config_warning`` — sustituye los marcadores del mensaje.

        Reemplaza ``%(field:modelo.campo)s`` por el nombre legible del campo.
        El marcador ``%(menu:...)s`` se **deja intacto** y su referencia viaja
        en ``ConfigWarning.menu_ref``: sin cargador de ``xml_id`` no hay ruta
        que poner, y borrarlo haría que el mensaje mintiera sobre lo que su
        autor escribió (ver el docstring del módulo).
        """
        references = CONFIG_WARNING_PATTERN.findall(msg)
        values = {}
        menu_ref = None
        for item in references:
            ref_type, ref = item.split(':', 1)
            if ref_type.lower() == 'field':
                values[item] = cls.option_name(ref)
            else:
                menu_ref = ref
                values[item] = f'%({item})s'   # se deja tal cual
        return ConfigWarning(msg % values if values else msg, menu_ref=menu_ref)
