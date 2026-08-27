"""``account.code.mapping`` — Odoo ``addons/account/models/account_code_mapping.py``.

Adaptación de la referencia (``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3,
86 líneas, 6 ``def`` medidos por AST: ``create``, ``_search``,
``_compute_account_id``, ``_compute_company_id``, ``_compute_code``,
``_inverse_code``). Divergencia de mecanismo declarada — **ningún modelo
Django se crea en este archivo**: el propio comentario de la referencia
explica por qué su premisa no existe aquí.

Qué es en la referencia, y por qué su premisa no aplica
==========================================================

El comentario de cabecera de la clase (odoo19c: líneas 10-12) lo dice
verbatim: *"This model is used purely for UI, to display the account codes
for each company. It is not stored in DB."* Es un modelo **virtual**
(``_auto = False``, ``_table_query = '0'`` — sin tabla real), cuyo único
trabajo es dejar que la vista del plan de cuentas muestre, para **una misma
cuenta contable compartida entre varias compañías**, un **código de cuenta
distinto por compañía** — la semántica de ``company_dependent`` aplicada al
campo ``code`` de ``account.account``.

Esa premisa —una fila de ``account.account`` visible en N compañías, cada una
con su propio código— **no existe en este árbol**. Medido:
``account_account.py:86-89`` declara ``company = fields.Many2one('base.
ResCompany', on_delete=models.CASCADE, ...)`` — **un** ``ForeignKey``, no un
``ManyToMany``: cada cuenta pertenece exactamente a **una** compañía. El
``UniqueConstraint(fields=['company', 'code'], ...)`` de ese mismo archivo
(:101-107) ya impone "un código por cuenta por compañía" — pero porque la
relación cuenta↔compañía es 1:1, no 1:N. No hay "la misma cuenta, dos
compañías, dos códigos" que mapear: el concepto entero que
``account.code.mapping`` existe para resolver está fuera del modelo de datos
de este árbol.

Fabricar un modelo Django ``managed=False`` con un ``_search`` a medida sobre
un ID sintético (``account_id * 10000 + company_id``, odoo19c: línea 6,
``COMPANY_OFFSET``) construiría una feature nueva sobre una premisa que no
existe — el anti-patrón exacto que ``porte-completo-no-parcial.md`` prohíbe
en su forma inversa: no es *no portar lo que sí aplica*, es *inventar sobre
lo que no aplica*. Se declara la divergencia, no se fabrica el modelo.

Los 6 símbolos, uno por uno
=============================

- ``create`` — construye el ID sintético a partir de ``vals['account_id']``/
  ``vals['company_id']``. Sin el ID sintético (que existe sólo porque no hay
  tabla propia), no hay nada que construir.
- ``_search`` — intercepta el dominio ``[('account_id', 'in', [...])]`` y
  expande manualmente el producto cartesiano cuenta×compañía. Depende del
  framework de dominios/``_search`` override de Odoo — ausente en este ORM
  (misma ausencia que documenta ``account_analytic_distribution_model.py``
  para su propio ``_create_domain`` heredado).
- ``_compute_account_id`` / ``_compute_company_id`` — decodifican el ID
  sintético (``// COMPANY_OFFSET``, ``% COMPANY_OFFSET``). Sin ID sintético,
  no hay qué decodificar.
- ``_compute_code`` / ``_inverse_code`` — leen/escriben ``account.code`` con
  ``with_company(record.company_id)`` — el cambio de contexto de compañía
  activa de Odoo, sin análogo en este stack (no hay ``self.env`` ambiental).
  Y como ``AccountAccount.company`` es 1:1, ``account.with_company(X).code``
  no tiene sentido cuando ``X`` no es ya la única compañía de la cuenta.

Qué NO se pierde
==================

Nada del dato real: el código de una cuenta en **su** compañía ya es
consultable directo, ``AccountAccount.objects.get(pk=...).code`` — sin
necesitar un modelo intermedio, porque no hay ambigüedad de "en cuál
compañía" que resolver.

Sucesor: tarea PENDIENTE DE ASIGNAR — si el proyecto decide adoptar
``company_dependent`` de verdad (una cuenta contable compartida por varias
compañías, cada una con su propio código — cambio de ``AccountAccount.company``
de ``ForeignKey`` a través de una tabla puente), este archivo es el punto de
partida para re-derivar el modelo virtual que lo expone a la UI. Hasta
entonces, DESCONOCIDO con esta condición de cierre explícita.
"""
