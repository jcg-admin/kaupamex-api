"""Lo que ``account`` le cuelga de ``account.analytic.line`` — ≙ ``_inherit``.

Adaptación de Odoo ``addons/account/models/account_analytic_line.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 183 líneas, 11 ``def``:
medido por AST — ``_compute_general_account_id``, ``_check_general_account_id``,
``_compute_partner_id``, ``_compute_analytic_profitability``,
``on_change_unit_amount``, ``view_header_get``, ``create``, ``_field_to_sql``,
``_search_analytic_profitability``, ``write``, ``unlink``). Extiende
``account.analytic.line`` — ya portado en ``analytic/models/analytic_line.py``
— con el enlace al apunte contable (``move_line_id``) y los campos que se
derivan de él.

BLOQUEADO — los 11 símbolos, ninguno se porta
==============================================

Todos dependen, directa o transitivamente, de **una columna nueva**:
``move_line_id`` (``Many2one`` a ``account.move.line``, odoo19c: líneas
39-45), el puente entre un apunte analítico y el asiento contable que lo
generó. ``account.analytic.line`` vive en el app **``analytic``**
(``addons/analytic/models/analytic_line.py``): igual que
``account_analytic_distribution_model.py`` de este mismo tramo, su migración
correspondería a ``addons/analytic/migrations/``, fuera de la lista de
archivos escribibles de este pase (sólo ``addons/account/migrations/**``).
Ver ese archivo para el precedente completo (``product.py``: *"el
autodetector atribuye la migración al app_label del modelo"*).

Con ``move_line_id`` bloqueado, la cascada sobre los 11:

- ``_compute_general_account_id`` / ``_check_general_account_id`` — leen
  ``move_line_id.account_id``. Sin la columna, no hay qué leer.
- ``_compute_partner_id`` — lee ``move_line_id.partner_id``. **Doble bloqueo**:
  aunque ``move_line_id`` existiera, ``account.move.line``
  (``account_move_line.py:43-98``, medido) tampoco declara ``partner`` — y
  ese archivo no está en la lista de escribibles de este tramo (mismo
  bloqueo que ``account_analytic_account.py`` documenta para
  ``analytic_distribution``).
- ``_compute_analytic_profitability`` / ``_field_to_sql`` /
  ``_search_analytic_profitability`` — el primero lee
  ``general_account_id.account_type``, que a su vez depende del
  ``general_account_id`` bloqueado arriba. Los otros dos son SQL crudo de
  proyección/búsqueda sobre un campo ``store=False`` — sin el campo base
  computable, no hay nada que proyectar. Independientemente de eso: no hay
  framework de ``_search`` custom en este ORM (``AccountAnalyticDistributionModel``
  ya documenta la misma ausencia para su propio ``_create_domain``
  heredado) — sería divergencia de mecanismo aun sin el bloqueo de campo.
- ``create`` / ``write`` / ``unlink`` — los tres invocan
  ``self.move_line_id._update_analytic_distribution()`` — un método que la
  referencia cuelga sobre ``account.move.line`` desde el propio addon
  ``analytic`` (no visto en este árbol) y que, aun colgándolo por
  ``add_to_class`` sin tocar el archivo, escribiría en
  ``AccountMoveLine.analytic_distribution`` — el mismo campo ausente que
  bloquea ``account_analytic_account.py`` de este tramo.
- ``on_change_unit_amount`` — onchange de formulario
  (``@api.onchange`` existe aquí como marcador declarativo puro,
  ``orm/decorators.py:37-41``: ``func._onchange = fields``, sin motor de
  eventos de cliente que lo dispare). Sin un cliente web que emita el evento,
  no hay quién lo invoque. **Divergencia de mecanismo**, no bloqueo de campo.
- ``view_header_get`` — construye el título de una vista lista del cliente
  web de Odoo. Esta API es DRF, sin cliente web propio. **Divergencia de
  mecanismo.**

Sucesor: tarea PENDIENTE DE ASIGNAR — declarar ``addons/analytic/migrations/``
(y, para ``_compute_partner_id``, también ``account_move_line.py`` +
``addons/account/migrations/``) en el alcance de un pase futuro; entonces
portar ``move_line_id``/``general_account_id``/``journal_id``/``product_id``/
``code``/``ref`` como campos reales y recuperar los métodos que dependen de
ellos.
"""


def apply_account_analytic_line_extensions():
    """No-op documentado — ninguno de los 11 símbolos de la referencia se porta.

    Mismo criterio que ``account_analytic_account.py`` de este tramo: se
    conserva la función, cableable cuando el sucesor la desbloquee. Probado
    en ``tests/unit/account/test_account_analytic_line.py``.
    """
    return None
