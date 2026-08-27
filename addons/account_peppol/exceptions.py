"""Catálogo de errores del proxy Peppol — código → mensaje traducible.

Adaptación de Odoo ``account_peppol/exceptions.py``
(``odoo19c: addons/account_peppol/exceptions.py``, 170 líneas, LGPL-3) —
atribución y aviso de licencia preservados (DEC-KX-03).

Qué es: el mapa que traduce el código numérico que devuelve el proxy Peppol de
Odoo S.A. (o el código ebMS del estándar AS4) a un mensaje legible. La fuente
envuelve **cada** mensaje en un ``lambda`` a propósito, y su comentario lo dice:
*"We need to wrap all the message inside lambda to make sure they will be called
on demand, with a language context in the environment"*. Aquí se conserva el
envoltorio verbatim.

Porte símbolo por símbolo — 7 símbolos, los 7 portados
=======================================================

.. list-table::
   :header-rows: 1
   :widths: 42 58

   * - Símbolo de la referencia (línea)
     - Desenlace
   * - ``STANDARD_EXCEPTION_CODE_MESSAGES_MAP`` (``:12-47``)
     - portado — **36 códigos**, los mismos y con los mismos aridades de
       ``lambda``.
   * - ``STANDARD_EXCEPTION_ALLOWED_MESSAGES`` (``:49``)
     - portado verbatim — ``(105, 106)``.
   * - ``EBMS_EXCEPTION_CODE_MESSAGES_MAP`` (``:53-96``)
     - portado — **43 códigos** del estándar ebMS.
   * - ``_get_translation_lambda_message`` (``:99-111``)
     - portado, incluida su defensa por aridad (ver divergencia 2).
   * - ``get_peppol_error_message`` (``:114-140``)
     - portado — la regla de precedencia ebMS ≻ estándar y el desempate del
       código 4 se conservan tal cual.
   * - ``get_exception_message`` (``:143-155``)
     - portado.
   * - ``get_ebms_message`` (``:158-170``)
     - portado.

Divergencias declaradas
=========================

1. **``LazyTranslate`` → ``tools.translate._``.** La referencia instancia
   ``_lt = LazyTranslate(__name__)`` para diferir la traducción. El ``_`` de
   este árbol **ya es perezoso** por construcción
   (``src/tools/translate.py:56-67``: ``_lazy_translate = lazy(...)``), así
   que cumple el mismo contrato sin una clase intermedia. El envoltorio
   ``lambda`` de cada entrada se conserva igual — es lo que permite pasar los
   argumentos del error en el momento de formatear.
2. **La defensa por aridad se mide sobre ``__code__.co_argcount``**, igual que
   la referencia. Se conserva porque protege de un ``TypeError`` cuando el
   proxy manda menos argumentos de los que el mensaje espera; el comentario
   de la fuente es explícito al respecto.
3. **Los mensajes van en español**, criterio del árbol para texto de usuario
   (``redaccion-tecnica-es.md``). Los códigos, las claves y la estructura del
   mapa quedan verbatim: son el contrato con el proxy.
"""
from typing import Callable

from tools.translate import _

# Mapa de código → mensaje del proxy Peppol de Odoo (``peppol_proxy/
# exceptions.py`` del lado servidor). Cada mensaje va envuelto en un
# ``lambda`` para que se construya bajo demanda, con el idioma activo.

#: Errores estándar (el proxy los guarda como ``code``).
STANDARD_EXCEPTION_CODE_MESSAGES_MAP: dict[int, Callable[..., str]] = {
    101: lambda: _('Algo salió mal con su solicitud'),
    102: lambda arg: _(
        'Error del proxy, contacte a Odoo (falta «%s» — verifique que se haya '
        'cargado desde el panel de configuración)', arg),
    103: lambda: _('No fue posible validar el documento.'),
    104: lambda arg: _(
        'No se encontró un XSD con el cual validar el documento con '
        'identificador «%s».', arg),
    105: lambda: _('El documento XML no es válido según el esquema XSD.'),
    106: lambda: _('El documento XML no es válido según el schematron.'),
    107: lambda: _('No fue posible canonicalizar el documento XML.'),
    201: lambda: _('Hubo un problema con el participante Peppol.'),
    202: lambda: _(
        'Este usuario no es un usuario Peppol. El proxy_type asociado debe ser '
        '«peppol». Es obligatorio para crear un participante Peppol.'),
    203: lambda arg: _(
        'El Service Metadata Publisher asociado a este participante no es '
        'accesible. url: %s', arg),
    204: lambda: _(
        'El grupo de servicios del participante Peppol encontrado en su Service '
        'Metadata Provider no es válido.'),
    205: lambda: _('No se encontró ningún endpoint AS4 de participante válido.'),
    206: lambda: _(
        'La resolución DNS del participante Peppol devolvió una URL que no '
        'pertenece a este servidor.'),
    207: lambda: _('El participante Peppol no puede recibir este tipo de documento.'),
    208: lambda: _('El certificado del participante Peppol no es válido.'),
    301: lambda: _('No se proporcionó ningún documento UBL al servicio de salida de Peppol.'),
    302: lambda: _('El documento UBL entregado al servicio de salida de Peppol está mal formado.'),
    303: lambda: _('No fue posible enviar el documento al participante Peppol.'),
    304: lambda: _(
        'Hubo un problema con la Hermes Migration Token Collection Interface (MTCI).'),
    501: lambda: _('Hubo un error con el mensaje entrante.'),
    502: lambda: _('Este usuario no está registrado en nuestro Access Point.'),
    503: lambda: _('Fin inesperado del mensaje MIME multiparte.'),
    504: lambda: _('No fue posible verificar el valor del digest.'),
    505: lambda: _(
        'El módulo de seguridad no pudo descifrar los datos cifrados que '
        'referencia la cabecera Security del actor SOAP «ebms».'),
    506: lambda: _('El mensaje no cumple con la política AS4.'),
    507: lambda: _('No fue posible descomprimir el mensaje entrante.'),
    701: lambda: _('Hubo un error con la solicitud Peppol'),
    702: lambda: _('Su solicitud sigue en proceso.'),
    703: lambda: _('Su identificación aún no ha sido aprobada para esta acción'),
    704: lambda: _('Ocurrió un error interno'),
    705: lambda: _('No tiene crédito suficiente'),
    706: lambda: _('No fue posible encontrar el documento'),
    707: lambda: _(
        'Alcanzó el límite de documentos que puede enviar hoy. Reintente más '
        'tarde. Contacte al soporte si considera que necesita ampliar ese límite.'),
    708: lambda: _('No está autorizado para cambiar el correo de contacto.'),
}

#: Códigos cuyo mensaje completo del proxy se muestra tal cual, en vez del
#: genérico del mapa de arriba. Verbatim de la referencia (``:49``).
STANDARD_EXCEPTION_ALLOWED_MESSAGES = (105, 106)


#: Errores del estándar ebMS (el proxy los guarda como ``ebms_code``).
EBMS_EXCEPTION_CODE_MESSAGES_MAP: dict[int, Callable[..., str]] = {
    1: lambda: _(
        'Aunque el documento del mensaje está bien formado y es válido según el '
        'esquema, algún elemento o atributo contiene un valor que el MSH no '
        'pudo reconocer y por tanto no pudo utilizar.'),
    2: lambda: _(
        'Aunque el documento del mensaje está bien formado y es válido según el '
        'esquema, algún valor de elemento o atributo no puede procesarse como '
        'se espera porque el MSH no soporta la característica relacionada.'),
    3: lambda: _(
        'Aunque el documento del mensaje está bien formado y es válido según el '
        'esquema, algún valor de elemento o atributo es inconsistente con el '
        'contenido de otro elemento o atributo, con el modo de procesamiento '
        'del MSH, o con los requisitos normativos de la especificación ebMS.'),
    4: lambda: _('Otro'),
    5: lambda: _(
        'El MSH presenta un fallo temporal o permanente al intentar abrir una '
        'conexión de transporte con un MSH remoto.'),
    6: lambda: _('No hay ningún mensaje disponible para recoger de este MPC en este momento.'),
    7: lambda: _('El uso de MIME no es consistente con el uso que exige esta especificación.'),
    8: lambda: _(
        'Aunque el documento del mensaje está bien formado y es válido según el '
        'esquema, la presencia o ausencia de algún elemento o atributo no es '
        'consistente con las capacidades del MSH respecto a las '
        'características soportadas.'),
    9: lambda: _(
        'La cabecera ebMS no está bien formada como documento XML, o no cumple '
        'las reglas de empaquetado de ebMS.'),
    10: lambda: _(
        'La cabecera ebMS u otra cabecera (fiabilidad, seguridad) que el MSH '
        'esperaba no es compatible con el contenido esperado según el P-Mode '
        'asociado.'),
    11: lambda: _(
        'El MSH no puede resolver una referencia a una carga externa (una parte '
        'que no está contenida en el mensaje ebMS, identificada por el URI de '
        'PartInfo/href).'),
    20: lambda: _(
        'Un MSH intermediario no pudo enrutar un mensaje ebMS y detuvo su '
        'procesamiento.'),
    21: lambda: _(
        'Una entrada de la función de enrutamiento asigna el mensaje a un MPC '
        'para recogida, pero el MSH intermediario no puede almacenar el mensaje '
        'en ese MPC.'),
    22: lambda: _(
        'Un MSH intermediario asignó el mensaje a un MPC para recogida y lo '
        'almacenó correctamente. Sin embargo, fijó un límite de tiempo de '
        'espera para que el mensaje fuera recogido, y ese límite se alcanzó.'),
    23: lambda: _(
        'Un MSH determinó que el mensaje expiró y no intentará reenviarlo ni '
        'entregarlo.'),
    30: lambda: _('La estructura de un paquete recibido no cumple las reglas de agrupamiento.'),
    31: lambda: _(
        'Una unidad de mensaje de un paquete no se procesó porque otra unidad '
        'relacionada del mismo paquete provocó un error.'),
    40: lambda: _('Se recibió un fragmento que pertenece a un grupo previamente rechazado.'),
    41: lambda: _(
        'Se recibió un fragmento, pero más de un mensaje de fragmento del grupo '
        'especifica un valor para este elemento.'),
    42: lambda: _(
        'Se recibió un fragmento, pero más de un mensaje de fragmento del grupo '
        'especifica un valor para este elemento.'),
    43: lambda: _(
        'Se recibió un fragmento, pero más de un mensaje de fragmento del grupo '
        'especifica un valor para este elemento.'),
    44: lambda: _(
        'Se recibió un fragmento, pero más de un mensaje de fragmento del grupo '
        'especifica un valor para este elemento.'),
    45: lambda: _(
        'Se recibió un fragmento, pero más de un mensaje de fragmento del grupo '
        'especifica un valor para un elemento de compresión.'),
    46: lambda: _(
        'Se recibió un fragmento, pero un fragmento recibido antes tenía los '
        'mismos valores de GroupId y FragmentNum.'),
    47: lambda: _(
        'El atributo href no referencia una parte de datos MIME válida: hay '
        'partes MIME distintas de la cabecera del fragmento y de una parte de '
        'datos, o el cuerpo SOAP no está vacío.'),
    48: lambda: _(
        'Un fragmento de mensaje entrante tiene un valor mayor que el '
        'FragmentCount conocido.'),
    49: lambda: _(
        'Se fijó un valor para FragmentCount, pero un fragmento recibido antes '
        'tenía un valor mayor.'),
    50: lambda arg: _(
        'El tamaño de la parte de datos de un mensaje de fragmento es mayor que %s', arg),
    51: lambda arg: _(
        'Pasó más tiempo que %s desde que se recibió el primer fragmento, y aún '
        'no se han recibido todos los demás.', arg),
    52: lambda arg: _(
        'Había propiedades de mensaje en la cabecera SOAP del fragmento que no '
        'estaban especificadas en %s', arg),
    53: lambda: _(
        'La cabecera eb3:Message copiada a la cabecera del fragmento no '
        'coincide con la cabecera eb3:Message del mensaje de origen '
        'reensamblado.'),
    54: lambda: _(
        'No hay espacio en disco suficiente para almacenar todos los fragmentos '
        '(esperados) del grupo.'),
    55: lambda: _('Ocurrió un error al descomprimir el mensaje reensamblado.'),
    60: lambda: _(
        'Un MSH que responde indica que aplica el enlace MEP alternativo al '
        'mensaje de respuesta.'),
    101: lambda: _(
        'El módulo de seguridad no pudo validar la firma de la cabecera '
        'Security destinada al actor SOAP «ebms».'),
    102: lambda: _(
        'El módulo de seguridad no pudo descifrar los datos cifrados que '
        'referencia la cabecera Security destinada al actor SOAP «ebms».'),
    103: lambda: _(
        'El procesador determinó que no se cumplían los métodos, parámetros, '
        'alcance u otros requisitos de política de seguridad del mensaje.'),
    201: lambda: _(
        'Alguna función de fiabilidad implementada por el módulo de fiabilidad '
        'no está operativa, o el estado de fiabilidad asociado a esta secuencia '
        'de mensajes no es válido.'),
    202: lambda: _(
        'Aunque el mensaje se envió con requisito de entrega garantizada, el '
        'módulo de fiabilidad no pudo asegurar que se entregara correctamente, '
        'pese a los reintentos.'),
    301: lambda: _(
        'No se recibió acuse (Receipt) de un mensaje que el MSH que genera este '
        'error había enviado antes.'),
    302: lambda: _(
        'Se recibió acuse (Receipt) de un mensaje enviado antes por el MSH que '
        'genera este error, pero su contenido no coincide con el del mensaje '
        '(alguna parte no fue reconocida, o el digest asociado no coincide con '
        'el digest de la firma, en el caso de NRR).'),
    303: lambda: _('Ocurrió un error durante la descompresión.'),
}


def _get_translation_lambda_message(translation_lambda: Callable[..., str], args: list[str]):
    """≙ ``_get_translation_lambda_message`` (``odoo19c: :99-111``).

    Defensa por aridad, verbatim de la fuente: si el proxy manda una cantidad
    de argumentos distinta de la que el mensaje espera, se rellena con
    ``'<unknown>'`` en vez de reventar con ``TypeError``.
    """
    translation_lambda_arg_count: int = translation_lambda.__code__.co_argcount

    if translation_lambda_arg_count == 0:
        return translation_lambda()
    if translation_lambda_arg_count == len(args):
        return translation_lambda(*args)
    dummy_args = ['<unknown>'] * translation_lambda_arg_count
    return translation_lambda(*dummy_args)


def get_peppol_error_message(error_vals: dict):
    """≙ ``get_peppol_error_message`` (``odoo19c: :114-140``).

    Procesa el diccionario de error que devuelve el proxy: toma el código (o
    el código ebMS) y lo traduce al mensaje correspondiente.

    Precedencia verbatim de la fuente: el mensaje ebMS gana —suele ser más
    específico— **salvo** cuando su código es 4 («Otro»), que es genérico.

    :param error_vals: el diccionario de error codificado que produce el
        método ``_json`` de ``peppol_proxy``.
    :return: el mensaje de error traducido.

    Divergencia: la referencia recibe ``env`` como primer argumento para
    traducir con el idioma de esa sesión; aquí el idioma lo lleva el hilo
    (``django.utils.translation``), así que el parámetro sobra y se retira.
    """
    # Errores que llegan directamente de una ruta jsonrpc, sin convertir.
    if error_vals.get('data', {}).get('context'):
        error_vals = error_vals['data']['context']

    if (ebms_code := error_vals.get('ebms_code')) and ebms_code != 4:
        error_message = get_ebms_message(error_vals)
    elif ((strd_code := error_vals.get('code'))
            and strd_code not in STANDARD_EXCEPTION_ALLOWED_MESSAGES):
        error_message = get_exception_message(error_vals)
    else:
        error_message = error_vals.get('message', 'No fue posible recuperar el mensaje de error')

    return _(
        'Error Peppol [code=%(error_code)s]: %(error_subject)s\n%(error_message)s',
        error_code=error_vals['code'],
        error_subject=error_vals.get('subject', ''),
        error_message=error_message,
    )


def get_exception_message(error_vals: dict):
    """≙ ``get_exception_message`` (``odoo19c: :143-155``).

    :param error_vals: debe traer las claves ``'code'`` y ``'args'``.
    :return: el mensaje estándar traducido.
    """
    peppol_code = error_vals['code']
    if peppol_code not in STANDARD_EXCEPTION_CODE_MESSAGES_MAP:
        return _('Error Peppol desconocido: %s', error_vals)

    translation_lambda = STANDARD_EXCEPTION_CODE_MESSAGES_MAP[peppol_code]
    return _get_translation_lambda_message(translation_lambda, error_vals.get('args', []))


def get_ebms_message(error_vals: dict):
    """≙ ``get_ebms_message`` (``odoo19c: :158-170``).

    :param error_vals: debe traer las claves ``'ebms_code'`` y ``'args'``.
    :return: el mensaje ebMS traducido.
    """
    ebms_code = error_vals['ebms_code']
    if ebms_code not in EBMS_EXCEPTION_CODE_MESSAGES_MAP:
        return _('Error Peppol desconocido: %s', error_vals)

    translation_lambda = EBMS_EXCEPTION_CODE_MESSAGES_MAP[ebms_code]
    return _get_translation_lambda_message(translation_lambda, error_vals['args'])


__all__ = [
    'STANDARD_EXCEPTION_CODE_MESSAGES_MAP',
    'STANDARD_EXCEPTION_ALLOWED_MESSAGES',
    'EBMS_EXCEPTION_CODE_MESSAGES_MAP',
    'get_peppol_error_message',
    'get_exception_message',
    'get_ebms_message',
]
