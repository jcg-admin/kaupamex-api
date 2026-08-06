"""``certificate.key`` — llaves criptográficas (pública o privada).

Adaptación fiel de Odoo certificate/models/key.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3).

Divergencia declarada — ``content``/``pem_key`` son bytes crudos, no base64
=============================================================================

La referencia hace ``base64.b64decode(content)``/``base64.b64encode(...)``
en cada punto de entrada/salida porque el ``Binary`` de Odoo **guarda base64**
en la fila (``with_context(bin_size=False)`` es su forma de pedir los bytes
completos en vez de sólo el tamaño). El ``BinaryField`` de Django guarda
**bytes crudos** — no hay capa base64 que atravesar. Por eso este archivo
**omite** todos los ``base64.b64decode``/``b64encode`` de la referencia:
``self.content``/``self.pem_key`` ya son los bytes reales. ``_get_formatted_value``
se conserva (decide el formato de **salida** para el llamador, no el
almacenamiento) porque sigue siendo una decisión legítima del caller.

``ensure_one()`` de la referencia no aplica: Django no tiene recordsets —
``self`` siempre es una fila.
"""
import base64
from contextlib import suppress

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding

import fields
import models

from addons.base.models import ResCompany, TimeStampedModel
from exceptions import UserError

#: Alias de hash soportados (fiel a la referencia — sólo sha1/sha256).
STR_TO_HASH = {
    'sha1': hashes.SHA1(),
    'sha256': hashes.SHA256(),
}

#: Alias de curva elíptica soportada (fiel — sólo SECP256R1).
STR_TO_CURVE = {
    'SECP256R1': ec.SECP256R1(),
}


def _get_formatted_value(data, formatting='encodebytes'):
    """Formatea bytes crudos para el caller (fiel a ``_get_formatted_value``).

    :param bytes data: los bytes a formatear.
    :param str formatting: ``'encodebytes'`` (base64 en bloques de 76 chars,
        vía ``base64.encodebytes``), ``'base64'`` (base64 sin bloques), o
        cualquier otro valor → bytes crudos sin codificar.
    """
    if formatting == 'encodebytes':
        return base64.encodebytes(data)
    elif formatting == 'base64':
        return base64.b64encode(data)
    else:
        return data


def _int_to_bytes(value, byteorder='big'):
    """Serializa un entero a bytes (fiel a ``_int_to_bytes``)."""
    return value.to_bytes((value.bit_length() + 7) // 8, byteorder=byteorder)


class CertificateKey(TimeStampedModel):
    """``certificate.key`` — una llave pública o privada (PEM/DER).

    ``pem_key``/``public``/``loading_error`` son ``compute='...', store=True``
    en la referencia (``@api.depends('content', 'password')``). Django no
    tiene ese grafo declarativo: se recalculan en ``save()`` en cada
    escritura — equivalente funcional, ejecutado en el único punto por el que
    pasa toda escritura (mismo patrón que ``hr.department._compute_parent_path``
    en este árbol).
    """

    name = fields.Char(
        max_length=255, default='New key', verbose_name='Nombre',
    )
    content = fields.Binary(verbose_name='Archivo de la llave')
    password = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Contraseña de la llave privada',
    )
    pem_key = fields.Binary(
        null=True, blank=True, verbose_name='Bytes de la llave en PEM',
        help_text='Computado: PEM normalizado de la llave (pública o privada).',
    )
    public = fields.Boolean(
        null=True, blank=True, verbose_name='Pública/privada',
        help_text='Computado: True si es pública, False si privada, '
                  'None si no se pudo determinar (error de carga).',
    )
    loading_error = fields.Text(
        blank=True, default='', verbose_name='Error de carga',
    )
    active = fields.Boolean(
        default=True, verbose_name='Activa',
        help_text='Archivar sin borrar la llave.',
    )
    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, related_name='certificate_keys',
        verbose_name='Empresa',
    )

    class Meta:
        db_table = 'certificate_key'
        verbose_name = 'Llave criptográfica'
        verbose_name_plural = 'Llaves criptográficas'
        ordering = ['pk']  # la referencia no declara `_order`; orden de creación

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self._compute_pem_key()
        super().save(*args, **kwargs)

    # -------------------------------------------------------
    #                       Cómputo
    # -------------------------------------------------------

    def _compute_pem_key(self):
        """Normaliza ``content`` a PEM y detecta si es pública o privada.

        Adaptación fiel de ``_compute_pem_key`` (key.py:66-127): intenta
        cargar en orden DER-privada → PEM-privada → DER-pública → PEM-pública;
        la primera que cargue decide ``public`` y el PEM normalizado.
        """
        content = bytes(self.content) if self.content else None
        if not content:
            self.pem_key = None
            self.public = None
            self.loading_error = ''
            return

        pkey_password = self.password.encode('utf-8') if self.password else None

        pkey = None
        is_public = None
        for loader, public in (
            (serialization.load_der_private_key, False),
            (serialization.load_pem_private_key, False),
            (serialization.load_der_public_key, True),
            (serialization.load_pem_public_key, True),
        ):
            try:
                pkey = (loader(content) if public
                        else loader(content, pkey_password))
                is_public = public
                break
            except (ValueError, TypeError):
                continue

        if pkey is None:
            self.pem_key = None
            self.public = None
            self.loading_error = (
                'No se pudo cargar esta llave. Su contenido o su '
                'contraseña son erróneos.'
            )
            return

        self.public = is_public
        if is_public:
            self.pem_key = pkey.public_bytes(
                encoding=Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        else:
            encryption = (
                serialization.BestAvailableEncryption(pkey_password)
                if pkey_password else serialization.NoEncryption()
            )
            self.pem_key = pkey.private_bytes(
                encoding=Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=encryption,
            )
        self.loading_error = ''

    # -------------------------------------------------------
    #                   Métodos de negocio
    # -------------------------------------------------------

    def _sign(self, message, hashing_algorithm='sha256', formatting='encodebytes'):
        """Firma ``message`` con esta llave (debe ser privada)."""
        if self.public:
            raise UserError(
                'Se requiere una llave privada para firmar documentos.')

        pem_key = bytes(self.pem_key) if self.pem_key else None
        if self.loading_error:
            raise UserError(f'{self.name} - {self.loading_error}')

        return self._sign_with_key(
            message, pem_key, pwd=self.password,
            hashing_algorithm=hashing_algorithm, formatting=formatting,
        )

    def _verify(self, signed_message, signature, hashing_algorithm='sha256'):
        """Verifica ``signature`` sobre ``signed_message`` (debe ser pública)."""
        if not self.public:
            raise UserError(
                'Se requiere una llave pública para verificar la firma '
                'de documentos.')

        pem_key = bytes(self.pem_key) if self.pem_key else None
        if self.loading_error:
            raise UserError(f'{self.name} - {self.loading_error}')

        return self._verify_with_key(
            signed_message, signature, pem_key,
            signature_algorithm=hashing_algorithm,
        )

    def _get_public_key_numbers_bytes(self, formatting='encodebytes'):
        """Números públicos (e, n para RSA; x, y para EC) de esta llave."""
        return self._numbers_public_key_bytes_with_key(
            self._get_public_key_bytes(encoding='pem', formatting='raw'),
            formatting=formatting,
        )

    def _get_public_key_bytes(self, encoding='der', formatting='encodebytes'):
        """Bytes de la llave pública correspondiente a esta llave."""
        if self.public:
            public_key = serialization.load_pem_public_key(
                bytes(self.pem_key))
        else:
            password = self.password
            if password and not isinstance(password, bytes):
                password = password.encode()
            public_key = serialization.load_pem_private_key(
                bytes(self.pem_key), password or None,
            ).public_key()

        enc = (serialization.Encoding.DER if encoding == 'der'
               else serialization.Encoding.PEM)
        return _get_formatted_value(
            public_key.public_bytes(
                encoding=enc,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
            formatting=formatting,
        )

    def _decrypt(self, message, hashing_algorithm='sha256'):
        """Descifra ``message`` (RSA-OAEP únicamente, fiel a la referencia)."""
        if not isinstance(message, bytes):
            message = message.encode('utf-8')

        if self.public:
            raise UserError('Se requiere una llave privada para descifrar datos.')
        if hashing_algorithm not in STR_TO_HASH:
            raise UserError(
                f"Algoritmo de hash no soportado '{hashing_algorithm}'. "
                "Soportados: sha1 y sha256.")

        private_key = serialization.load_pem_private_key(
            bytes(self.pem_key), None)
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise UserError(
                'Algoritmo de criptografía asimétrica no soportado '
                f"'{type(private_key)}'. Soportado para descifrado: RSA.")

        return private_key.decrypt(
            message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=STR_TO_HASH[hashing_algorithm]),
                algorithm=STR_TO_HASH[hashing_algorithm],
                label=None,
            ),
        ).decode()

    @staticmethod
    def _sign_with_key(message, pem_key, pwd=None, hashing_algorithm='sha256',
                        formatting='encodebytes'):
        """Firma ``message`` con la llave privada PEM dada (sin instancia)."""
        if not isinstance(message, bytes):
            message = message.encode('utf-8')
        if not isinstance(pem_key, bytes):
            pem_key = pem_key.encode('utf-8')
        if pwd and not isinstance(pwd, bytes):
            pwd = pwd.encode('utf-8')

        if hashing_algorithm not in STR_TO_HASH:
            raise UserError(
                f"Algoritmo de hash no soportado '{hashing_algorithm}'. "
                "Soportados: sha1 y sha256.")

        try:
            private_key = serialization.load_pem_private_key(pem_key, pwd or None)
        except ValueError:
            raise UserError('No se pudo cargar la llave privada.')

        match private_key:
            case ec.EllipticCurvePrivateKey():
                signature = private_key.sign(
                    message, ec.ECDSA(STR_TO_HASH[hashing_algorithm]))
            case rsa.RSAPrivateKey():
                signature = private_key.sign(
                    message, padding.PKCS1v15(), STR_TO_HASH[hashing_algorithm])
            case ed25519.Ed25519PrivateKey():
                signature = private_key.sign(message)
            case _:
                raise UserError(
                    'Algoritmo de criptografía asimétrica no soportado '
                    f"'{type(private_key)}'. Soportado para firma: "
                    'ED25519, EC y RSA.')

        return _get_formatted_value(signature, formatting=formatting)

    @staticmethod
    def _verify_with_key(signed_message, signature, pem_key,
                          signature_algorithm='sha256'):
        """Verifica ``signature`` con la llave pública PEM dada (sin instancia)."""
        if signature_algorithm not in STR_TO_HASH:
            raise UserError(
                f"Algoritmo de firma no soportado '{signature_algorithm}'. "
                "Soportados: sha1 y sha256.")

        if not isinstance(signed_message, bytes):
            signed_message = signed_message.encode('utf-8')
        if not isinstance(pem_key, bytes):
            pem_key = pem_key.encode('utf-8')

        try:
            public_key = serialization.load_pem_public_key(pem_key)
        except ValueError:
            raise UserError('No se pudo cargar la llave pública.')

        match public_key:
            case ec.EllipticCurvePublicKey():
                with suppress(InvalidSignature):
                    public_key.verify(
                        signature, signed_message,
                        ec.ECDSA(STR_TO_HASH[signature_algorithm]))
                    return True
                return False
            case rsa.RSAPublicKey():
                with suppress(InvalidSignature):
                    public_key.verify(
                        signature, signed_message,
                        padding.PKCS1v15(), STR_TO_HASH[signature_algorithm])
                    return True
                return False
            case ed25519.Ed25519PublicKey():
                with suppress(InvalidSignature):
                    public_key.verify(signature, signed_message)
                    return True
                return False
            case _:
                raise UserError(
                    'Algoritmo de criptografía asimétrica no soportado '
                    f'{public_key!r}. Soportado para firma: EC y RSA.')

    @staticmethod
    def _numbers_public_key_bytes_with_key(pem_key, formatting='encodebytes'):
        """Números públicos de la llave pública PEM dada (sin instancia)."""
        if not isinstance(pem_key, bytes):
            pem_key = pem_key.encode('utf-8')

        try:
            public_key = serialization.load_pem_public_key(pem_key)
        except ValueError:
            raise UserError('No se pudo cargar la llave pública.')

        if isinstance(public_key, ec.EllipticCurvePublicKey):
            e = public_key.public_numbers().x
            n = public_key.public_numbers().y
        elif isinstance(public_key, rsa.RSAPublicKey):
            e = public_key.public_numbers().e
            n = public_key.public_numbers().n
        else:
            raise UserError(
                'Algoritmo de criptografía asimétrica no soportado '
                f"'{type(public_key)}'. Soportados: EC, RSA.")

        return (
            _get_formatted_value(_int_to_bytes(e), formatting=formatting),
            _get_formatted_value(_int_to_bytes(n), formatting=formatting),
        )

    @classmethod
    def _generate_ec_private_key(cls, company, name='id_ec', curve='SECP256R1',
                                  password=None):
        """Genera una llave privada de curva elíptica y la persiste.

        Divergencia declarada frente a la referencia (``key.py:407-434``):
        ahí ``password`` se re-encodea a bytes y se guarda TAL CUAL en el
        campo ``password`` (``Char``) — guardaría bytes en un campo de texto.
        Aquí se persiste el ``password`` original (str) y sólo se usa la
        versión bytes para la encriptación PKCS8.
        """
        if curve not in STR_TO_CURVE:
            raise UserError(
                f"Algoritmo de curva no soportado '{curve}'. "
                "Soportado: SECP256R1.")

        private_key = ec.generate_private_key(STR_TO_CURVE[curve])
        password_bytes = (password.encode() if password
                           and not isinstance(password, bytes) else password)
        encryption = (
            serialization.BestAvailableEncryption(password_bytes)
            if password_bytes else serialization.NoEncryption()
        )
        return cls.objects.create(
            name=name,
            content=private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=encryption,
            ),
            company=company,
            password=password or '',
        )

    @classmethod
    def _generate_rsa_private_key(cls, company, name='id_rsa',
                                   public_exponent=65537, key_size=2048,
                                   password=None):
        """Genera una llave privada RSA y la persiste."""
        if public_exponent not in (65537, 3):
            raise UserError(
                'El exponente público debe ser 65537 (o 3 por legado).')
        if key_size < 512:
            raise UserError('El tamaño de la llave debe ser al menos 512 bits.')

        private_key = rsa.generate_private_key(
            public_exponent=public_exponent, key_size=key_size)
        password_bytes = (password.encode() if password
                           and not isinstance(password, bytes) else password)
        encryption = (
            serialization.BestAvailableEncryption(password_bytes)
            if password_bytes else serialization.NoEncryption()
        )
        return cls.objects.create(
            name=name,
            content=private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=encryption,
            ),
            company=company,
            password=password or '',
        )

    @classmethod
    def _generate_ed25519_private_key(cls, company, name='id_ed25519',
                                       password=None):
        """Genera una llave privada Ed25519 y la persiste."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        password_bytes = (password.encode() if password
                           and not isinstance(password, bytes) else password)
        encryption = (
            serialization.BestAvailableEncryption(password_bytes)
            if password_bytes else serialization.NoEncryption()
        )
        return cls.objects.create(
            name=name,
            content=private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=encryption,
            ),
            company=company,
            password=password or '',
        )
