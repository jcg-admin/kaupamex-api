"""``kpi.provider`` — el modelo abstracto que publica los KPI de la base.

Adaptación de ``odoo19c: addons/base_setup/models/kpi_provider.py``
(``odoo-tools@622ddc2a``, LGPL-3 — atribución y aviso de licencia preservados,
DEC-KX-03; mecanismo: **copia + adaptación**, que es lo que la licencia del
manifiesto admite).

Los 3 símbolos de la fuente están portados: los dos atributos de clase y
``get_kpi_summary``.
"""
import models


class KpiProvider(models.Model):
    """≙ ``KpiProvider`` (``odoo19c: kpi_provider.py:4-25``).

    ``models.AbstractModel`` allá ≙ ``Meta.abstract`` aquí: declara el
    contrato y no tiene tabla. Su razón de ser es que **otros módulos lo
    sobreescriban**; sin él, cada addon que quisiera publicar un KPI tendría
    que inventar su propio nombre de método.
    """

    _name = 'kpi.provider'
    _description = 'KPI Provider'

    class Meta:
        abstract = True

    @classmethod
    def get_kpi_summary(cls):
        """≙ ``get_kpi_summary`` (``odoo19c: :8-25``), con su docstring verbatim:

            Other modules can override this method to add their own KPIs to
            the list. This method will be called by the databases module to
            retrieve the data displayed on the databases list. The return
            value shall be a list of dictionaries with the following keys:

            - id: a unique identifier for the KPI
            - type: the type of data (`integer` or `return_status`)
            - name: the translated name of the KPI, as displayable to the
              current user
            - value: either the numeric value (for `type=integer`) or one of
              the statuses (for `type=return_status`):

              - late       one return of this type should have been done already
              - longterm   the deadline of the closest uncompleted return is in
                more than 3 months
              - to_do      the deadline of the closest uncompleted return is in
                less than 3 months
              - to_submit  the closest uncompleted return is ready, but still
                needs an action
              - done       all of the forseeable returns are completed

        ``@api.model`` de la fuente ≙ ``classmethod``: no lee ningún registro.
        La lista vacía **no es un hueco**: es el contrato del que cada addon
        parte, igual que en la fuente.
        """
        return []
