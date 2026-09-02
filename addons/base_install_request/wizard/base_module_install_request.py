"""``base.module.install.request`` / ``base.module.install.review`` — el asistente.

Adaptación de ``odoo19c: addons/base_install_request/wizard/
base_module_install_request.py`` (``odoo-tools@622ddc2a``, LGPL-3, 87 líneas)
y de ``_auto_install_apps`` (``odoo19c: base_install_request/__init__.py:9-21``)
— atribución y aviso de licencia preservados (DEC-KX-03).

El sitio del archivo es el de la fuente
========================================

La versión anterior de este puerto vivía en ``models/``. La referencia lo
declara en ``wizard/`` (``ls`` sobre la raíz: ``wizard/__init__.py`` y
``wizard/base_module_install_request.py``), y ``atributos-de-clase-de-modelo.md``
§2 manda listar la raíz de la referencia antes de decidir dónde va un archivo.
El precedente propio es ``src/addons/base/wizard/``.

Porte BLOQUEADO — 6 de 8 símbolos
==================================

Ocho símbolos entre el asistente y su arranque; **seis portados**, dos
bloqueados por el mismo método ausente.

Qué cambió respecto de la versión anterior de este docstring
=============================================================

Declaraba **0 de 6**, con los seis sin portar. Cuatro de esos seis vetos ya no
se sostienen, y las mediciones que los sostenían medían la ausencia de un
mecanismo que **sí existe en este árbol**:

.. code-block:: text

   grep -rn "class TransientModel" --include=*.py src/ | wc -l
   → 1     (src/orm/models_transient.py:52 — el mecanismo del wizard EXISTE)

   grep -rn "def all_user_ids" --include=*.py src/ | wc -l
   → 1     (src/addons/base/models/res_groups.py:922)

   grep -rn "def upstream_dependencies" --include=*.py src/ | wc -l
   → 1     (src/addons/base/models/ir_module.py:443)

   grep -rn "def dispatch_email" --include=*.py addons/ | wc -l
   → 1     (addons/mail/models/email_executor.py:35)

Cuatro de los seis dependían de piezas presentes; el veredicto anterior las
declaró ausentes sin medirlas o midió antes de que existieran. El bloqueo real
es **uno solo** y lo comparten dos símbolos.

El bloqueo real, medido — y su instrumento
===========================================

.. code-block:: text

   grep -rnE "def button_immediate_install|def button_install" \
       --include=*.py src/ addons/ | grep -v base_install_request | wc -l
   → 0

El ``grep -v`` **no es cosmético**: sin él la cuenta da 2, y los dos hits son
las líneas de este mismo docstring citando el comando. Un instrumento que se
lee a sí mismo publica que el símbolo existe cuando lo único que existe es su
mención (``metrica-decide-la-conclusion.md``, sub-patrón D).

Instalar un addon contra una base viva es una operación de **deploy** en esta
plataforma (``INSTALLED_APPS`` + migración), no una fila que un asistente
escriba en caliente; el veredicto lo declara
``src/addons/base/models/ir_module.py``.

Símbolo a símbolo
==================

- ``BaseModuleInstallRequest`` (``:8-20``) — portado: ``TransientModel`` con
  sus cuatro campos y sus tres atributos de clase.
- ``BaseModuleInstallRequest._compute_user_ids`` (``:22-25``) — portado.
- ``BaseModuleInstallRequest.action_send_request`` (``:27-44``) — portado.
- ``BaseModuleInstallReview`` (``:47-59``) — portado.
- ``BaseModuleInstallReview._compute_modules_description`` (``:61-67``) —
  portado; su plantilla QWeb se compone nativa (ver la divergencia abajo).
- ``BaseModuleInstallReview._get_depending_apps`` (``:69-79``) — portado.
- ``BaseModuleInstallReview.action_install_module`` (``:81-87``) —
  BLOQUEADO por ``ir.module.module.button_immediate_install`` — el método no
  existe en este árbol (medido arriba: 0 definiciones fuera de este addon).
  Sucesor: tarea **#452**, que porta lo que le falta a
  ``src/addons/base/models/ir_module.py``.
- ``_auto_install_apps`` (``__init__.py:9-21``) —
  BLOQUEADO por ``ir.module.module.button_install`` — misma medición, 0
  definiciones. Sucesor: tarea **#452**.

Divergencias declaradas — de mecanismo, no de alcance
======================================================

- **``user_ids`` y ``module_ids`` no tienen columna.** La fuente los declara
  ``compute=`` sin ``store``, así que aquí son ``fields.NonStored``: se
  computan al leer y no añaden tabla intermedia. El método de cómputo conserva
  su nombre (``_compute_user_ids``, ``_compute_modules_description``) y el
  descriptor lo invoca.
- **La descripción se compone en Python, no en QWeb.** La fuente la delega en
  ``ir.qweb._render`` sobre la plantilla
  ``base_install_request.base_module_install_review_description``; este árbol
  no tiene motor QWeb (medido: ``ls src/addons/base/models/ | grep qweb`` → 0
  archivos). El marcado de la plantilla —el párrafo condicional, el ``<ul
  class="list-unstyled row">``, el ``<li class="mt8 col-lg-6">`` por app con su
  ``<img>`` y su ``shortdesc``— se compone verbatim en
  :func:`render_modules_description`. Es la vía «se construye» de
  ``porte-completo-no-parcial.md``, no una omisión.
- **El correo sale por ``dispatch_email``.** La fuente llama a
  ``mail_template.send_mail(...)``; ``MailTemplate`` de este árbol renderiza
  (``render``) y el envío lo hace la capa de servicio
  (``addons/mail/models/email_executor.py``), que es la separación que ese
  archivo ya declara. Se conservan el destinatario por usuario, el
  ``force_send`` (aquí, el envío inmediato del ejecutor) y el contexto de
  render con ``partner`` y ``menu_id``.
- **``ensure_one()`` no se porta.** Aquí ``self`` es una instancia por
  construcción; mismo criterio que ``src/addons/base/models/res_company.py:744``.

Lo que este archivo no cierra
==============================

Los dos símbolos que la tabla de arriba declara con su arista, ambos con
sucesor registrado (tarea
**#452**). El enlace *Review Request* del cuerpo del correo, que apunta a una
ruta del cliente web de Odoo, se declara en ``data.py``.
"""
import html

import fields
import models
from exceptions import UserError

from addons.base.models.ir_model import IrModelData
from addons.base_install_request.data import (
    INSTALL_REQUEST_TEMPLATE_MODULE, INSTALL_REQUEST_TEMPLATE_XMLID)
from addons.mail.models.email_executor import dispatch_email
from orm.environments import get_current_user
from orm.models_transient import TransientModel
from tools.translate import _

#: ≙ ``self.env.ref('base.group_system')`` (``:24``) — el grupo cuyos usuarios
#: reciben la solicitud, verbatim de la fuente.
GROUP_SYSTEM_XMLID = 'base.group_system'

#: ≙ ``self.env.ref('base.menu_apps').id`` (``:29``). El identificador viaja al
#: contexto de render igual que allá; aquí no hay menú del cliente web que
#: resolver, así que se pasa la cadena sin resolver — mismo criterio que los
#: xml_id sin resolver de ``addons/crm/models/digest.py``.
MENU_APPS_XMLID = 'base.menu_apps'

#: ≙ ``domain=[('state', '=', "uninstalled")]`` de los dos ``module_id``.
STATE_UNINSTALLED = 'uninstalled'
STATE_INSTALLED = 'installed'


def _users_of_group_system():
    """Los usuarios del grupo de administración, o ninguno si no está sembrado.

    ``IrModelData.ref`` con ``raise_if_not_found=False``: un árbol sin el grupo
    sembrado devuelve lista vacía en vez de romper. La fuente no tiene ese caso
    porque su ``base`` siempre trae el grupo.
    """
    grupo = IrModelData.ref(GROUP_SYSTEM_XMLID, raise_if_not_found=False)
    if grupo is None:
        return []
    return list(grupo.all_user_ids)


def render_modules_description(apps):
    """El marcado de la plantilla QWeb, compuesto en Python.

    ≙ ``base_install_request.base_module_install_review_description``
    (``odoo19c: base_install_request/data/mail_templates_module_install.xml:3-17``),
    marca por marca: el párrafo sólo si alguna app lo es (``t-if="any(...)"``),
    la lista sin viñetas en fila, y un elemento por app **que sea aplicación**
    con su icono y su ``shortdesc``.

    El texto de las apps se escapa: allá lo hace ``t-esc`` por definición, y
    aquí ``shortdesc`` viene del manifest de un addon de terceros.
    """
    applications = [app for app in apps if app.application]
    piezas = []
    if applications:
        piezas.append('<p>The following apps will be installed:</p>')
    piezas.append('<div class="container-fluid">')
    piezas.append('<ul class="list-unstyled row">')
    for app in applications:
        piezas.append(
            '<li class="mt8 col-lg-6"><div>'
            '<img width="24px" height="24px" class="img-fluid" src="%s"/>'
            '%s</div></li>' % (html.escape(app.icon or ''),
                               html.escape(app.shortdesc or '')))
    piezas.append('</ul>')
    piezas.append('</div>')
    return ''.join(piezas)


class BaseModuleInstallRequest(TransientModel):
    """≙ ``BaseModuleInstallRequest`` (``:8-44``) — pedir la activación."""

    _name = 'base.module.install.request'
    _description = 'Module Activation Request'
    _rec_name = 'module_id'

    module_id = fields.Many2one(
        'base.IrModule', on_delete=models.CASCADE, db_column='module_id',
        limit_choices_to={'state': STATE_UNINSTALLED},
        related_name='install_requests', verbose_name='Module',
        help_text='Módulo cuya activación se solicita (Odoo module_id).')
    user_id = fields.Many2one(
        'base.ResUsers', on_delete=models.CASCADE, null=True, blank=True,
        db_column='user_id', related_name='module_install_requests',
        help_text='Quien solicita (Odoo user_id, default self.env.user).')
    #: ≙ ``user_ids = fields.Many2many(..., compute='_compute_user_ids')``:
    #: ``compute`` sin ``store`` → sin columna ni tabla intermedia.
    user_ids = fields.NonStored(
        'Send to:', default=lambda wizard: wizard._compute_user_ids())
    body_html = fields.Html(blank=True, default='', verbose_name='Body')

    class Meta:
        db_table = 'base_module_install_request'
        verbose_name = 'Solicitud de activación de módulo'
        verbose_name_plural = 'Solicitudes de activación de módulo'

    def __str__(self):
        """El ``_rec_name`` de la fuente es ``module_id``."""
        return self.module_id.shortdesc if self.module_id_id else ''

    def _compute_user_ids(self):
        """≙ ``_compute_user_ids`` (``:22-25``) — los del grupo de sistema.

        La fuente escribe ``self.user_ids = [(6, 0, users.ids)]``; aquí el
        campo no tiene columna, así que el cómputo **es** su lectura.
        """
        return _users_of_group_system()

    def action_send_request(self):
        """≙ ``action_send_request`` (``:27-44``) — envía y avisa.

        Renderiza la plantilla una vez por destinatario con su ``partner`` en
        el contexto —igual que la fuente, que arma un ``render_ctx`` por
        usuario— y despacha el correo. Devuelve el mismo
        ``ir.actions.client``/``display_notification`` de la fuente.

        :raises UserError: si la plantilla no está sembrada. La fuente usa
            ``env.ref`` sin ``raise_if_not_found``, que también levanta.
        """
        plantilla = IrModelData.ref(
            '%s.%s' % (INSTALL_REQUEST_TEMPLATE_MODULE,
                       INSTALL_REQUEST_TEMPLATE_XMLID),
            raise_if_not_found=False)
        if plantilla is None:
            raise UserError(_(
                'La plantilla de correo %(xmlid)s no está sembrada.',
                xmlid=INSTALL_REQUEST_TEMPLATE_XMLID))
        for user in self._compute_user_ids():
            partner = getattr(user, 'partner_id', None)
            destino = getattr(partner, 'email', None) or user.email
            if not destino:
                continue
            render = plantilla.render(self, {
                'ctx_partner_id': getattr(partner, 'pk', None),
                'partner': partner,
                'menu_id': MENU_APPS_XMLID,
            })
            dispatch_email(render['subject'], render['body_html'],
                           render['email_from'] or None, [destino])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('Your request has been successfully sent'),
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class BaseModuleInstallReview(TransientModel):
    """≙ ``BaseModuleInstallReview`` (``:47-87``) — revisar antes de instalar."""

    _name = 'base.module.install.review'
    _description = 'Module Activation Review'
    _rec_name = 'module_id'

    module_id = fields.Many2one(
        'base.IrModule', on_delete=models.CASCADE, db_column='module_id',
        limit_choices_to={'state': STATE_UNINSTALLED},
        related_name='install_reviews', verbose_name='Module',
        help_text='Módulo bajo revisión (Odoo module_id).')
    #: ≙ ``module_ids`` y ``modules_description``, los dos ``compute`` sin
    #: ``store`` que la fuente declara juntos en ``_compute_modules_description``.
    module_ids = fields.NonStored(
        'Depending Apps',
        default=lambda wizard: wizard._compute_modules_description()[0])
    modules_description = fields.NonStored(
        default=lambda wizard: wizard._compute_modules_description()[1])

    class Meta:
        db_table = 'base_module_install_review'
        verbose_name = 'Revisión de activación de módulo'
        verbose_name_plural = 'Revisiones de activación de módulo'

    def __str__(self):
        return self.module_id.shortdesc if self.module_id_id else ''

    def _compute_modules_description(self):
        """≙ ``_compute_modules_description`` (``:61-67``).

        Devuelve la pareja ``(apps, descripción)`` porque la fuente escribe los
        dos campos en la misma pasada y aquí ninguno tiene columna: cada
        descriptor toma su mitad. Calcular una sola vez conserva el invariante
        de la fuente —la descripción describe **esas** apps— que dos cómputos
        independientes podrían romper si el grafo cambiara entre ambos.
        """
        apps = self._get_depending_apps(self.module_id)
        return apps, render_modules_description(apps)

    @classmethod
    def _get_depending_apps(cls, module):
        """≙ ``_get_depending_apps`` (``:69-79``) — el cierre hacia arriba.

        El ``recordset | otro`` de la fuente es unión de conjuntos preservando
        el orden de aparición; aquí se compone con un ``dict`` por clave
        primaria, que es la estructura que da esa misma semántica en Python.

        :raises UserError: sin módulo o con el módulo ya instalado — los dos
            mensajes de la fuente, verbatim.
        """
        if not module:
            raise UserError(_('No module selected.'))
        if module.state == STATE_INSTALLED:
            raise UserError(_('The module is already installed.'))
        deps = list(module.upstream_dependencies())
        apps = {module.pk: module}
        for dep in deps:
            if dep.application:
                apps.setdefault(dep.pk, dep)
        for dep in deps:
            for arriba in dep.upstream_dependencies():
                apps.setdefault(arriba.pk, arriba)
        return list(apps.values())

    def action_install_module(self):
        """BLOQUEADO por ``ir.module.module.button_immediate_install`` — razón:
        el método no existe en este árbol (medido en el encabezado del módulo:
        0 definiciones fuera de este addon), porque instalar contra una base
        viva es aquí una operación de deploy. Sucesor: tarea **#452**.
        """
        raise NotImplementedError(
            'action_install_module está bloqueado: '
            'ir.module.module.button_immediate_install no existe en este árbol '
            '(tarea #452).')


def _auto_install_apps():
    """BLOQUEADO por ``ir.module.module.button_install`` — razón: el método no
    existe en este árbol (misma medición, 0 definiciones fuera de este addon).
    Sucesor: tarea **#452**.
    """
    raise NotImplementedError(
        '_auto_install_apps está bloqueado: ir.module.module.button_install no '
        'existe en este árbol (tarea #452).')
