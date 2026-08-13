"""Servicios del portal — verificación de acceso a documentos por token.

``document_check_access`` es la adaptación fiel de
``portal/controllers/portal.py:961-980`` (``_document_check_access``, leído
completo). Es el corazón de la compartición por link: si el usuario no puede
leer el documento por sus permisos normales, se acepta si presenta el
``access_token`` correcto — comparado en tiempo constante con ``consteq``
(el mismo ``odoo.tools.consteq`` de la referencia, ya portado en
``tools/misc``).

El contrato de acceso normal (``check_access('read')`` de Odoo) aquí es una
función ``can_read`` inyectable: cada documento decide su regla de lectura
(capacidad, fila-por-usuario L3). Sin token válido y sin permiso normal →
``AccessDenied``; documento inexistente → ``NotFound``.
"""
from exceptions import AccessDenied, MissingError
from tools.misc import consteq


def document_check_access(model, document_id, user, access_token=None,
                          can_read=None):
    """≙ ``_document_check_access`` (portal.py:961-980).

    :param model: la clase del modelo del documento (debe tener
        ``access_token``; ≙ heredar ``portal.mixin``).
    :param document_id: id del documento solicitado.
    :param user: el usuario que solicita (``request.user``).
    :param access_token: token presentado en el link, si lo hay.
    :param can_read: callable ``(document, user) -> bool`` con la regla de
        lectura normal del documento. Si se omite, sólo el token concede
        acceso (equivalente a un documento sin regla propia).
    :return: el documento (acceso concedido).
    :raise MissingError: el documento no existe (≙ ``MissingError`` de la
        referencia).
    :raise AccessDenied: ni permiso normal ni token válido (≙ ``AccessError``).
    """
    document = model.objects.filter(pk=document_id).first()
    if document is None:
        raise MissingError('This document does not exist.')

    if can_read is not None and can_read(document, user):
        return document

    # Sin permiso normal: sólo un token válido (comparación en tiempo
    # constante) concede el acceso — igual que la referencia.
    if (access_token and document.access_token
            and consteq(document.access_token, access_token)):
        return document

    raise AccessDenied(
        'You are not allowed to access this document.')
