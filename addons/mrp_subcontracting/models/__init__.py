"""Modelos del addon ``mrp_subcontracting`` — subcontratación de fabricación.

Extiende ``mrp`` (DEC-SALE-01): ubicaciones de subcontratación, subcontratistas
(``res.partner``/``AUTH_USER``), el vínculo BoM ↔ subcontratista y el
subcontratista de la orden. El costo de subcontratación (componentes + servicio)
vive en ``services``.
"""
from addons.mrp_subcontracting.models.mrp_bom_subcontractor import (
    BomSubcontractor,
    SubcontractProduction,
)
from addons.mrp_subcontracting.models.subcontracting_location import (
    Subcontractor,
    SubcontractingLocation,
)

__all__ = [
    'BomSubcontractor',
    'SubcontractProduction',
    'Subcontractor',
    'SubcontractingLocation',
]
