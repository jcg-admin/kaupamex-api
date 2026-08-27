"""Extensión del modelo abstracto ``base`` — el veto de alias "sólo
empleados" (Odoo ``hr``).

Adaptación de Odoo hr/models/models.py (odoo-tools@622ddc2a, odoo19c:,
LGPL-3, 21 líneas) — atribución y aviso de licencia preservados (DEC-KX-03).

La referencia extiende ``_inherit = 'base'`` (el AbstractModel del que
heredan TODOS los modelos) con un solo método: ``_alias_get_error``, el
gancho que la pasarela de correo entrante consulta para decidir si un
mensaje dirigido a un alias con política ``'employees'`` viene de un
empleado registrado.

Porte símbolo por símbolo — 1 de 1 (forma), con la mitad de pasarela BLOQUEADA
===============================================================================

.. list-table::
   :header-rows: 1

   * - Símbolo (línea)
     - Estado
   * - ``_alias_get_error`` (``:12-21``)
     - portado como función de módulo — la lógica de negocio (¿este correo
       pertenece a un empleado?) es real y consultable hoy; lo que queda
       BLOQUEADO es su integración en una pasarela que no existe

Bloqueos y divergencias declarados
===================================

1. **No hay destino ``'base'`` que extender.** Este árbol no tiene un
   AbstractModel universal del que cuelguen todos los modelos (la herencia
   es la de Django: ``TimeStampedModel`` y mixins explícitos). Por eso el
   símbolo vive como **función de módulo**, no como método colgado — el
   consumidor natural (la pasarela) tampoco existe (ver 2).
2. **BLOQUEADO por la pasarela de correo entrante.** El propio
   ``addons/mail/models/mail_alias.py`` de este árbol lo declara: "la
   pasarela de correo entrante de Odoo (…el ruteo de mensajes por modelo)
   no se porta aquí". Sin ella, nadie llama a este gancho. La función queda
   lista para ese consumidor. Sucesor: el porte de la pasarela es parte del
   addon ``mail`` (mismo bloque que ``_alias_bounced_content``, declarado
   allá), no de ``hr``.
3. **BLOQUEADO por ``addons.mail.tools.alias_error.AliasError``** — la
   clase no existe (medido: 0 hits de ``AliasError`` en ``addons/`` y
   ``src/``), y su hogar es ``mail/tools``, no este addon (crearla aquí
   violaría la cláusula del SITIO de ``atributos-de-clase-de-modelo.md``).
   DIVERGENCIA de retorno: se devuelve la tupla
   ``(código, mensaje)`` en vez de ``AliasError(código, mensaje)``; cuando
   ``mail`` porte la clase, el envoltorio es una línea.
4. **``message``/``message_dict`` → ``email_address`` explícito.** La
   extracción del remitente (``decode_message_header`` +
   ``email_normalize``) es trabajo de la pasarela bloqueada; ``tools.mail``
   de este árbol no trae esos helpers (medido). La función recibe la
   dirección ya extraída y la normaliza de forma mínima
   (``strip().lower()``).
5. **``user_id.email`` → ruta ORM real.** ``hr.HrEmployee.user`` es una
   propiedad (delegada a ``resource.user``), no filtrable por ORM; el
   segundo intento de la referencia se traduce al camino de columnas
   ``resource__user__partner__email`` (el correo del usuario vive en su
   partner en este árbol).
"""
from addons.hr.models.hr_employee import HrEmployee
from tools.translate import _

#: ≙ el código del ``AliasError`` de la referencia (``:20``).
ALIAS_ERROR_HR_EMPLOYEE_RESTRICTED = 'error_hr_employee_restricted'


def _alias_get_error(email_address, alias):
    """¿Puede ``email_address`` publicar en ``alias``? — ≙ ``_alias_get_error``
    (``odoo19c: hr/models/models.py:12-21``).

    Con política ``'employees'``: devuelve ``False`` si la dirección
    pertenece a un empleado registrado (por su correo de trabajo o el de su
    usuario), y la tupla ``(código, mensaje)`` si no. Con cualquier otra
    política devuelve ``None`` — el relevo al comportamiento por defecto
    (el ``super()`` de la referencia).
    """
    if alias.alias_contact != 'employees':
        return None
    normalized = (email_address or '').strip().lower()
    employee = HrEmployee.objects.filter(
        work_email__iexact=normalized,
    ).first()
    if employee is None:
        employee = HrEmployee.objects.filter(
            resource__user__partner__email__iexact=normalized,
        ).first()
    if employee is None:
        return (
            ALIAS_ERROR_HR_EMPLOYEE_RESTRICTED,
            _('restricted to employees'),
        )
    return False
