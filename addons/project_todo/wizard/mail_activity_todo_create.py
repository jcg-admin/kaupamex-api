"""``mail.activity.todo.create`` — crear a la vez el to-do y su actividad.

Adaptación de Odoo ``project_todo/wizard/mail_activity_todo_create.py``
(``odoo19c: addons/project_todo/wizard/mail_activity_todo_create.py``,
38 líneas, LGPL-3) — atribución y aviso de licencia preservados (DEC-KX-03).

``TransientModel`` → clase sin tabla con classmethods
=======================================================

Mismo patrón que ``account_debit_note.AccountDebitNoteWizard`` y
``hr.HrDepartureWizard``: el estado del asistente (resumen, fecha, usuario,
nota) no vive en una fila — lo pasa el llamador como argumentos. La clase
conserva ``_name``/``_description`` verbatim de la fuente y
``Meta: abstract = True; managed = False``.

Porte símbolo por símbolo — 6 símbolos, los 6 portados
=======================================================

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Símbolo de la referencia (línea)
     - Desenlace
   * - ``summary`` (``:10``)
     - portado — argumento ``summary`` de :meth:`create_todo_activity`.
   * - ``date_deadline`` (``:11``)
     - portado — argumento ``date_deadline``; su ``default=fields.Date.
       context_today`` es :meth:`default_date_deadline` (hoy), y el
       ``required=True`` se conserva como validación explícita.
   * - ``user_id`` (``:12``)
     - portado — argumento ``user`` (obligatorio, ≙ ``required=True``). Su
       ``default=lambda self: self.env.user`` es del cliente web: aquí lo da
       el llamador, que es quien tiene la sesión (mismo criterio que
       ``HrDepartureWizard``, cuyo ``context['active_ids']`` también se
       volvió argumento).
   * - ``note`` (``:13``)
     - portado — argumento ``note``, la descripción del to-do.
   * - ``create_todo_activity`` (``:15-38``)
     - portado — ver las divergencias.

Divergencias declaradas
=========================

1. **``user_ids: self.user_id.ids`` → ``assignee``.** ``ProjectTask`` de este
   árbol declara ``assignee``, FK simple, donde la referencia tiene un M2M de
   asignados (``addons/project/models/project_task.py:58``). Un solo usuario
   entra igual; el día que ``project`` porte el M2M, el argumento ya es el
   mismo dato.
2. **``res_model_id: self.env['ir.model']._get('project.task').id`` →
   ``res_model`` (``Char``).** ``MailActivity`` de este árbol guarda la
   identidad polimórfica como par ``(res_model, res_id)`` con ``res_model``
   de texto (``addons/mail/models/mail_activity.py:47``), no como FK a
   ``ir.model``. El valor se deriva de ``ProjectTask._meta.label`` y no se
   escribe a mano, que es exactamente lo que hace
   ``MailActivityMixin._activity_res_model`` cuando el modelo destino no
   declara ``_name`` — y ``ProjectTask`` no lo declara (medido).
3. **El retorno ``ir.actions.client`` / ``display_notification`` cae.** La
   referencia devuelve el payload de una notificación del cliente web de
   Odoo. Aquí el método devuelve **el par ``(todo, activity)`` creado**: el
   dato de negocio que el llamador necesita. Mismo criterio de exclusión de
   navegación que ``project_account.action_profitability_items``; el texto de
   la notificación pertenece al cliente React.
4. **``_('...')`` en español**, criterio del árbol para textos de usuario.
"""
from django.utils import timezone

from addons.mail.models.mail_activity import MailActivity
from addons.project.models.project_task import ProjectTask
from exceptions import UserError
from orm.models_transient import TransientModel
from tools.translate import _


class MailActivityTodoCreate(TransientModel):
    """``mail.activity.todo.create`` — asistente de to-do + actividad.

    Sin tabla (``TransientModel``, ``managed = False``): el estado del
    asistente lo pasa el llamador como argumentos de
    :meth:`create_todo_activity`.
    """

    # Atributos de clase de modelo — los dos que la referencia declara
    # (``odoo19c: addons/project_todo/wizard/mail_activity_todo_create.py:7-8``),
    # verbatim.
    _name = 'mail.activity.todo.create'
    _description = 'Create activity and todo at the same time'

    class Meta:
        abstract = True
        managed = False

    @staticmethod
    def default_date_deadline():
        """≙ ``default=fields.Date.context_today`` del campo ``date_deadline``
        (``odoo19c: :11``) — la fecha de hoy en la zona activa."""
        return timezone.localdate()

    @classmethod
    def create_todo_activity(cls, summary, user, note='', date_deadline=None):
        """≙ ``create_todo_activity`` (``odoo19c: :15-38``) — crea el to-do y
        la actividad que lo recuerda, en ese orden.

        :param summary: resumen; es el nombre del to-do y el de la actividad.
        :param user: usuario asignado (``res.users``). Obligatorio, ≙
            ``required=True`` del campo ``user_id``.
        :param note: descripción del to-do (≙ el campo ``note``).
        :param date_deadline: fecha límite; por defecto hoy, ≙ el ``default``
            del campo homónimo.
        :returns: la tupla ``(todo, activity)`` — ver divergencia 3.
        :raises UserError: si falta el usuario asignado o la fecha límite
            queda vacía (los dos ``required=True`` de la referencia).
        """
        if user is None:
            raise UserError(_('El to-do necesita un usuario asignado.'))
        if date_deadline is None:
            date_deadline = cls.default_date_deadline()

        todo = ProjectTask.objects.create(
            name=summary,
            description=note,
            date_deadline=date_deadline,
            assignee=user,
        )
        activity = MailActivity.objects.create(
            res_model=ProjectTask._meta.label,
            res_id=todo.pk,
            summary=summary,
            user=user,
            date_deadline=date_deadline,
            activity_type=MailActivity._default_activity_type_for_model(
                ProjectTask._meta.label,
            ),
        )
        return todo, activity


__all__ = ['MailActivityTodoCreate']
