"""Excepciones codificadas — addons.finance.

Cada una lleva la clave canonica ``codigo_error`` en su ``detail`` para que el
``custom_exception_handler`` (DRF) la exponga al cliente igual que el resto del
proyecto (mismo patron que ``addons.authz.exceptions.ReauthRequired``). Los
enums/codigos van en INGLES (canon-idioma).
"""
from rest_framework.exceptions import APIException


class DuplicateCode(APIException):
    """409 ``DUPLICATE_CODE`` — el ``code`` del concepto ya existe (UC-FIN-06 EX-02)."""

    status_code = 409
    default_code = 'duplicate_code'

    def __init__(self, code):
        super().__init__(detail={
            'detail': f'Ya existe un concepto con el codigo "{code}".',
            'codigo_error': 'DUPLICATE_CODE',
        })


class ImmutableField(APIException):
    """422 ``IMMUTABLE_FIELD`` — intento de cambiar ``code``/``kind`` (UC-FIN-06 EX-04)."""

    status_code = 422
    default_code = 'immutable_field'

    def __init__(self, field):
        super().__init__(detail={
            'detail': f'El campo "{field}" es inmutable una vez creado el concepto.',
            'codigo_error': 'IMMUTABLE_FIELD',
        })


class ConceptInUse(APIException):
    """409 ``CONCEPT_IN_USE`` — borrado fisico de un concepto referenciado
    (UC-FIN-06 EX-03). Se sugiere desactivar en su lugar.
    """

    status_code = 409
    default_code = 'concept_in_use'

    def __init__(self):
        super().__init__(detail={
            'detail': 'El concepto esta en uso; desactivalo en lugar de borrarlo.',
            'codigo_error': 'CONCEPT_IN_USE',
        })


class SodViolation(APIException):
    """409 ``SOD_VIOLATION`` — segregacion de funciones violada (UC-FIN-02 EX-01).

    El mismo usuario que preparo el corte intenta aprobarlo/sellarlo, o se
    intenta sellar un corte sin aprobador distinto en registro.
    """

    status_code = 409
    default_code = 'sod_violation'

    def __init__(self, detail=None):
        super().__init__(detail={
            'detail': detail or 'Quien prepara un corte no puede aprobarlo ni sellarlo.',
            'codigo_error': 'SOD_VIOLATION',
        })


class CashCloseSealed(APIException):
    """409 ``CASH_CLOSE_SEALED`` — intento de modificar un corte sellado
    (UC-FIN-02 EX-02). El sello es inmutable.
    """

    status_code = 409
    default_code = 'cash_close_sealed'

    def __init__(self):
        super().__init__(detail={
            'detail': 'El corte esta sellado y es inmutable; reabrelo para corregirlo.',
            'codigo_error': 'CASH_CLOSE_SEALED',
        })


class SettlementsNotReconciled(APIException):
    """409 ``SETTLEMENTS_NOT_RECONCILED`` — sellar con liquidaciones del periodo
    sin conciliar (UC-FIN-02 EX-03).
    """

    status_code = 409
    default_code = 'settlements_not_reconciled'

    def __init__(self):
        super().__init__(detail={
            'detail': 'Hay liquidaciones del dia sin conciliar; concilialas antes de sellar.',
            'codigo_error': 'SETTLEMENTS_NOT_RECONCILED',
        })


class CashCloseAlreadyOpen(APIException):
    """409 ``CASH_CLOSE_ALREADY_OPEN`` — ya existe un corte sin sellar para la
    fecha (UC-FIN-02 EX-06). No se abre un segundo corte del mismo dia.
    """

    status_code = 409
    default_code = 'cash_close_already_open'

    def __init__(self):
        super().__init__(detail={
            'detail': 'Ya existe un corte sin sellar para esa fecha.',
            'codigo_error': 'CASH_CLOSE_ALREADY_OPEN',
        })


class PeriodOpenMovements(APIException):
    """409 ``OPEN_MOVEMENTS`` — cerrar un ejercicio con pendientes (UC-FIN-08 EX-03).

    Quedan liquidaciones sin conciliar (UC-FIN-01) o cortes sin sellar
    (UC-FIN-02) dentro del ejercicio.
    """

    status_code = 409
    default_code = 'open_movements'

    def __init__(self):
        super().__init__(detail={
            'detail': 'Quedan movimientos sin conciliar o cortes sin sellar en el ejercicio.',
            'codigo_error': 'OPEN_MOVEMENTS',
        })


class OutOfOrderClose(APIException):
    """409 ``OUT_OF_ORDER_CLOSE`` — cerrar dejando un ejercicio anterior abierto
    (UC-FIN-08 EX-04). El cierre es en orden cronologico.
    """

    status_code = 409
    default_code = 'out_of_order_close'

    def __init__(self):
        super().__init__(detail={
            'detail': 'Hay un ejercicio anterior sin cerrar; cierralos en orden cronologico.',
            'codigo_error': 'OUT_OF_ORDER_CLOSE',
        })


class PeriodInvalidState(APIException):
    """409 ``INVALID_STATE`` — cerrar un ejercicio ya sellado o reabrir uno ya
    abierto (UC-FIN-08 EX-05).
    """

    status_code = 409
    default_code = 'invalid_state'

    def __init__(self, detail=None):
        super().__init__(detail={
            'detail': detail or 'El ejercicio no esta en un estado valido para esta operacion.',
            'codigo_error': 'INVALID_STATE',
        })


class BackupRequired(APIException):
    """409 ``BACKUP_REQUIRED`` — cerrar sin backup completo reciente (UC-FIN-08
    EX-07 / PRE-05). El cierre sella la historia de forma inmutable.
    """

    status_code = 409
    default_code = 'backup_required'

    def __init__(self):
        super().__init__(detail={
            'detail': 'Ejecuta un respaldo completo del ejercicio antes de sellarlo.',
            'codigo_error': 'BACKUP_REQUIRED',
        })
