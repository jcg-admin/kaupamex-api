"""``hr.employee`` — la compañía por defecto al mapear un empleado a un
proyecto (Odoo ``sale_timesheet``).

Adaptación de Odoo ``sale_timesheet/models/hr_employee.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3, 15 líneas) — atribución y
aviso de licencia preservados (DEC-KX-03).

Medido por AST sobre la referencia: 1 clase (``HrEmployee``, ``_inherit``),
**0 campos**, **1 método**.

Porte símbolo por símbolo — 1 de 1
=====================================

``default_get`` (:9-15) — **PORTADO**.

.. note:: **Corregido.** Este archivo declaraba el símbolo como bloqueado
   *"por mecanismo ausente"* y se cerraba con ``Sucesor: ninguno``, sobre dos
   premisas que **hoy son falsas**:

   1. *"``default_get`` como tal tampoco tiene análogo"* — lo tiene:
      ``src/orm/models.py:411`` lo declara con los cinco orígenes de valor de
      la fuente, y diez modelos del árbol lo sobrescriben. Lo construyó la
      tarea #113.
   2. *"el canal es ``env.context``, que no existe en este árbol"* — existe:
      ``src/orm/environments.py:243-266`` declara el ``ContextVar``,
      ``get_context()`` y ``context_scope(**valores)``, que es el
      ``with_context`` de la referencia.

   Las dos eran ciertas cuando se escribieron y dejaron de serlo sin que nadie
   volviera al archivo. Es estado incorrecto heredado (Clausula 2 del
   principio rector): se corrige en el pase que lo encuentra, no se hereda.

   El argumento que acompañaba al bloqueo —*"el llamador ya tiene el proyecto
   en la mano, así que la asignación por contexto es un argumento
   explícito"*— describía la referencia en vez de nuestra diferencia, que es
   el anti-patrón que ``porte-completo-no-parcial.md`` nombra. Y no se sostenía
   por sí solo: el ``default_get`` de la fuente lo consume **el formulario**,
   que no pasa por ningún llamador nuestro.
"""
from orm.environments import get_context
from orm.method_chain import chain_method
from orm.model_classes import extend_model

#: La clave de contexto que la fuente lee, verbatim
#: (``odoo19c: sale_timesheet/models/hr_employee.py:12``). Su valor es el id
#: de la compañía del proyecto desde cuyo formulario de tarifas se está
#: creando el empleado.
CREATE_PROJECT_EMPLOYEE_MAPPING = 'create_project_employee_mapping'


def default_get(cls, fields):
    """≙ ``default_get`` (:9-15) — la APORTACIÓN de este addon, no el total.

    *"Add the company of the project as default when the employee is being
    created from the project rate mapping."*

    La fuente escribe ``result = super().default_get(fields)`` y luego pisa
    una clave. Aquí el ``super()`` lo pone la cadena: esta función devuelve
    **sólo su aportación** y ``_merge_defaults`` la funde sobre la del eslabón
    previo. El nombre de la clave de contexto y su semántica son los de la
    fuente — si trae un id de compañía, ese id gana.

    :param fields: nombres de los campos cuyo default se pide, verbatim de la
      firma de ``orm.models.BaseModel.default_get``.
    """
    project_company_id = get_context().get(CREATE_PROJECT_EMPLOYEE_MAPPING, False)
    if project_company_id:
        return {'company_id': project_company_id}
    return {}


def _merge_defaults(new, previous):
    """``combine=`` de ``chain_method`` — ≙ ``result[...] = ...; return result``.

    Va con ``combine`` y **no** con el relevo por ``None`` que
    ``extend_model(metodos=)`` aplica: el relevo corre el eslabón previo sólo
    cuando el nuevo devuelve ``None``, y aquí los dos tienen que correr
    siempre. Con el relevo, un contexto sin la clave devolvería ``{}`` —que no
    es ``None``— y **el default de la base entera se perdería**.

    El orden de fusión sí importa, al revés que en
    ``account_check_printing``: la clave de este addon es ``company_id``, que
    la base también puede traer, y la fuente la pisa. Por eso ``new`` va
    después.
    """
    merged = dict(previous or {})
    merged.update(new or {})
    return merged


def _chain_hr_employee_default_get(model):
    """El ``luego`` de ``extend_model``: ``default_get`` necesita ``combine=``,
    y el bloque ``metodos=`` no lo expone — instala con relevo por ``None``.
    """
    chain_method(model, 'default_get', classmethod(default_get),
                 combine=_merge_defaults)


def apply_sale_timesheet_hr_employee_extensions():
    """Cuelga ``default_get`` sobre ``hr.HrEmployee`` — ≙ ``_inherit =
    'hr.employee'``.

    Sin bloque ``campos``: la referencia no declara ninguno en este archivo.
    """
    extend_model('hr', 'HrEmployee', luego=_chain_hr_employee_default_get)


__all__ = ['apply_sale_timesheet_hr_employee_extensions', 'default_get',
           'CREATE_PROJECT_EMPLOYEE_MAPPING']
