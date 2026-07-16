"""Excepciones codificadas — apps.modules.finance.

Cada una lleva la clave canonica ``codigo_error`` en su ``detail`` para que el
``custom_exception_handler`` (DRF) la exponga al cliente igual que el resto del
proyecto (mismo patron que ``apps.platform.authz.exceptions.ReauthRequired``). Los
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
