"""Modelos del addon ``stock`` — inventario (adaptación de Odoo ``stock``).

Expone la máquina de movimientos de inventario adaptada fielmente de Odoo
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3): ubicaciones y rutas,
existencias (quants), lotes, paquetes y su tipo, categorías de almacenamiento,
estrategias de retiro y colocación, movimientos con reservación, transferencias
(pickings) y reglas de aprovisionamiento.

**El orden de import importa y no es alfabético.** Django resuelve los FK
declarados por cadena (``'stock.StockLocation'``) de forma tardía, así que el
orden no rompe las relaciones; lo que sí rompe es un módulo que importe a otro
del mismo paquete en su cuerpo. Por eso los que se citan entre sí lo hacen por
``apps.get_model('stock', 'X')`` — una llamada, no un ``import`` (ver
``.claude/rules/no-lazy-imports.md``, excepción #4 y su mismo criterio).
"""
from addons.stock.models.stock_storage_category import (
    StockStorageCategory,
    StockStorageCategoryCapacity,
)
from addons.stock.models.stock_package_type import StockPackageType
from addons.stock.models.product_strategy import ProductRemoval, StockPutawayRule
from addons.stock.models.stock_location import StockLocation, StockRoute
from addons.stock.models.stock_package import StockPackage
from addons.stock.models.stock_package_history import StockPackageHistory
from addons.stock.models.stock_lot import StockLot
from addons.stock.models.stock_move import StockMove
from addons.stock.models.stock_move_line import (
    StockMoveLine,
    StockMoveLineConsumeRel,
)
from addons.stock.models.stock_picking import (
    PickingTypeFavoriteUserRel,
    StockPicking,
    StockPickingType,
)
from addons.stock.models.stock_quant import StockQuant
from addons.stock.models.stock_scrap import StockScrap, StockScrapReasonTag
from addons.stock.models.stock_rule import StockRule
from addons.stock.models.stock_warehouse import (
    StockWarehouse,
    StockWarehouseResupply,
)
from addons.stock.models.return_request import (
    ReturnRequest,
    ReturnItem,
    ReturnHistoryEntry,
    ReturnEvidence,
)

__all__ = [
    'PickingTypeFavoriteUserRel',
    'ProductRemoval',
    'StockLocation',
    'StockLot',
    'StockMove',
    'StockMoveLine',
    'StockMoveLineConsumeRel',
    'StockPackage',
    'StockPackageHistory',
    'StockPackageType',
    'StockPicking',
    'StockPickingType',
    'StockPutawayRule',
    'StockQuant',
    'StockRoute',
    'StockRule',
    'StockScrap',
    'StockScrapReasonTag',
    'StockWarehouse',
    'StockWarehouseResupply',
    'StockStorageCategory',
    'StockStorageCategoryCapacity',
    'ReturnRequest',
    'ReturnItem',
    'ReturnHistoryEntry',
    'ReturnEvidence',
]
