"""``project.task`` — la tarea privada («to-do») del addon ``project_todo``.

Adaptación de Odoo ``project_todo/models/project_task.py``
(``odoo19c: addons/project_todo/models/project_task.py``, 48 líneas, LGPL-3)
— atribución y aviso de licencia preservados (DEC-KX-03).

Medido por AST en la fuente: 1 clase (``_inherit = 'project.task'``),
0 campos, **3 métodos**. Un to-do es una ``project.task`` sin proyecto: el
addon no declara modelo propio, sólo cuelga comportamiento sobre el que ya
existe (``addons/project/models/project_task.py``).

Porte símbolo por símbolo — 3 símbolos: 1 portado, 1 bloqueado, 1 navegación
============================================================================

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Símbolo de la referencia (línea)
     - Desenlace
   * - ``create`` (``:11-22``)
     - **portado** — reexpresado como gancho de ``save()`` (divergencia 1).
       Es la única lógica de negocio del archivo: nombrar el to-do sin
       título a partir de la primera línea de su descripción.
   * - ``action_convert_to_task`` (``:24-32``)
     - BLOQUEADO por ``project.ProjectTask.company`` — el cuerpo del método
       es ``self.company_id = self.project_id.company_id``, y la tarea de
       este árbol **no tiene** campo de compañía (medido: 0 hits de
       ``company`` en ``addons/project/models/project_task.py``; sí lo tiene
       ``Project.company``). Su valor de retorno es además una acción
       ``ir.actions.act_window`` del cliente web, sin consumidor DRF.
       Sucesor: tarea PENDIENTE DE ASIGNAR (resumen de este pase) — se porta
       en el mismo pase que ``addons/project`` reciba ``ProjectTask.company``.
   * - ``get_todo_views_id`` (``:34-48``)
     - no portado — **navegación pura**: resuelve cinco identificadores
       externos de vistas del cliente web de Odoo (kanban / list / form /
       calendar / activity) con ``ir.model.data._xmlid_to_res_id``. Mismo
       criterio que ``project_account.action_profitability_items`` y
       ``account_debit_note/models/account_move.py``: la capa de vistas XML
       no existe en este árbol (el cliente es React).

Divergencias declaradas
=========================

1. **``create`` → gancho de ``save()``.** La referencia sobreescribe
   ``@api.model_create_multi def create(vals_list)`` y llama
   ``super().create(...)``. Aquí el alta pasa por Django
   (``ProjectTask.objects.create(...)`` / ``instancia.save()``), así que el
   punto de enganche equivalente es ``save()``: el idioma que este árbol ya
   usa para «suplir un valor en el alta»
   (``account/models/account_analytic_line.py:268``,
   ``chain_method(AccountAnalyticLine, 'save', _derive_general_account_on_save)``).
   El gancho retorna ``None`` para que ``chain_method`` siga con el ``save()``
   real — semántica de relevo.
2. **El término ``parent_id`` de la guarda cae.** La referencia exige
   ``not vals.get('name') and not vals.get('project_id') and not
   vals.get('parent_id')``. ``ProjectTask`` de este árbol no declara
   sub-tareas (medido: 0 hits de ``parent`` en
   ``addons/project/models/project_task.py``), así que la condición se
   evalúa con los dos términos que sí existen. Vuelve el tercero el día que
   ``addons/project`` porte ``parent_id``.
3. **``self.env._('Untitled to-do')`` → ``_('To-do sin título')``.** El
   análogo vivo del árbol es ``tools.translate._``; los textos van en
   español como el resto de los ports (criterio de
   ``stock.StockPicking.get_empty_list_help``).
4. **``description`` es ``Text``, no ``Html``.** El campo local es
   ``fields.Text`` (``addons/project/models/project_task.py:37``), pero se
   conserva el paso por ``html2plaintext`` de la referencia: sobre texto
   plano es idempotente, y la descripción del to-do llega como HTML del
   editor cuando el cliente lo envía.
"""
from orm.model_classes import extend_model
from orm.method_chain import chain_method
from tools.mail import html2plaintext
from tools.translate import _

#: Longitud a partir de la cual el nombre derivado se trunca, y hasta dónde
#: se corta. Valores verbatim de la referencia (``odoo19c: :19``): compara
#: contra 100 y recorta a 97 + ``'...'``.
_MAX_NAME_LENGTH = 100
_TRUNCATED_NAME_LENGTH = 97


def _name_from_description(description):
    """La primera línea de la descripción, como nombre del to-do.

    ≙ el cuerpo del ``if vals.get('description')`` de la referencia
    (``odoo19c: addons/project_todo/models/project_task.py:16-19``):
    ``html2plaintext`` → ``strip()`` → quitar asteriscos → primera línea →
    truncar a 97 caracteres más elipsis si pasa de 100.
    """
    text = html2plaintext(description)
    name = text.strip().replace('*', '').partition('\n')[0]
    if len(name) > _MAX_NAME_LENGTH:
        return name[:_TRUNCATED_NAME_LENGTH] + '...'
    return name


def _derive_todo_name_on_save(self, *args, **kwargs):
    """≙ ``create`` (``odoo19c:
    addons/project_todo/models/project_task.py:11-22``) — pone nombre al
    to-do que nace sin él.

    Sólo en el alta (``self.pk is None``, ≙ ``create``) y sólo cuando la
    tarea no tiene ni nombre ni proyecto: eso es lo que la referencia
    entiende por «to-do» (una tarea privada, fuera de todo proyecto). Un
    nombre dado a mano SIEMPRE gana, igual que en la fuente.

    Retorna ``None`` para que ``chain_method`` siga con el ``save()`` real
    (ver divergencia 1 del módulo).
    """
    if self.pk is None and not self.name and self.project_id is None:
        if self.description:
            self.name = _name_from_description(self.description)
        else:
            self.name = _('To-do sin título')
    return None


def _chain_todo_naming(model):
    """Engancha el nombrado del to-do en el alta — el ``luego`` de
    ``extend_model``, porque su bloque ``metodos`` instala sobre el nombre
    tal cual y aquí interesa dejar constancia de que se encadena ``save()``,
    no un método propio del addon."""
    chain_method(model, 'save', _derive_todo_name_on_save)


def apply_project_todo_project_task_extensions():
    """Cuelga sobre ``project.ProjectTask`` el nombrado del to-do — ≙
    ``_inherit = 'project.task'``. La llama ``ProjectTodoConfig.ready()``.

    Par de Django (``'project', 'ProjectTask'``) porque el destino no declara
    ``_name`` (``addons/project/models/project_task.py``).
    """
    extend_model('project', 'ProjectTask', luego=_chain_todo_naming)


__all__ = ['apply_project_todo_project_task_extensions']
