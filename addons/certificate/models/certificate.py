"""``certificate.certificate`` — un certificado X.509 y sus metadatos.

Adaptación fiel de Odoo certificate/models/certificate.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3).

Divergencias declaradas frente a la referencia
===============================================

1. **``content``/``pem_certificate`` son bytes crudos, no base64.** Igual
   razón que ``key.py``: el ``Binary`` de Odoo guarda base64; el
   ``BinaryField`` de Django guarda bytes crudos. Se omiten todos los
   ``base64.b64decode``/``b64encode`` de entrada/salida de la referencia.

2. **``date_start``/``date_end`` quedan timezone-aware (UTC), no naive.**
   La referencia hace ``cert.not_valid_before_utc.replace(tzinfo=None)``
   porque su ORM asume datetimes naive-UTC. Este proyecto declara
   ``USE_TZ = True`` (``config/settings/base.py:269``), así que Django
   **espera** datetimes aware — quitarles el tzinfo aquí produciría un
   ``RuntimeWarning`` y comparaciones incorrectas contra ``timezone.now()``.
   Se usa ``cert.not_valid_before_utc``/``not_valid_after_utc`` sin más (el
   proyecto fija ``cryptography>=42.0.0``, así que el *fallback* de la
   referencia para ``cryptography<42`` — vía ``parse_version`` — no aplica).

3. **``_compute_issuer_cert_id`` se simplifica a una sola compañía por
   consulta, no al escaneo multi-compañía de ``_check_company_domain``.**
   La referencia arma un dominio de "todas las compañías visibles" (record
   rules ``ir.rule``); este addon no porta vistas ni reglas de registro —
   se filtra directo por ``company=self.company`` (mismo criterio de
   aislamiento por fila que el resto del árbol, p. ej. ``CompanySetting``).
   Documentado como decisión de forma, no como hallazgo pendiente.

   La divergencia es **sólo** el eje multi-compañía. La otra mitad de
   ``_check_company_domain`` — el ``+ [False]`` de registros compartidos —
   **no** se pierde: es vacía en ambos árboles, porque la referencia declara
   ``company_id`` con ``required=True``
   (``odoo19c: addons/certificate/models/certificate.py:94-99``) y nuestra
   columna es ``IS_NULLABLE = NO``. Medido al refutar H-API-298.

4. **``ensure_one()`` no aplica** — Django no tiene recordsets.

5. **El batch de ``create``/``write`` (``vals_list``) se colapsa a una fila
   por ``save()``.** La referencia declara los dos métodos porque su ORM los
   separa (uno recibe el batch de altas, el otro la escritura); Django tiene
   un solo punto de persistencia por fila. El **cuerpo** no se fusiona:
   ``_parse_chain_missing_ca_vals`` sigue devolviendo los valores de las CAs
   faltantes y quien crea es el llamador, igual que allá.

6. **Los campos calculados sin ``store=True`` son ``property``, y su método
   ``_compute_*`` se conserva.** ``is_valid`` e ``issuer_cert_id`` se declaran
   en la referencia con ``compute=`` y sin persistir; aquí la lectura pública
   es la ``property`` (el campo) y el cálculo vive en ``_compute_is_valid`` /
   ``_compute_issuer_cert_id``, con el nombre de la fuente. Es el caso (b) de
   ``porte-completo-no-parcial.md``: el guion bajo marca lo interno porque el
   público es el campo.
"""
import re
from contextlib import suppress

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import constant_time, serialization
from cryptography.hazmat.primitives.asymmetric import (
    dsa, ec, ed448, ed25519, padding, rsa,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, pkcs12,
)
from cryptography.x509.extensions import DuplicateExtension, ExtensionNotFound
from cryptography.x509.oid import ExtensionOID, SignatureAlgorithmOID
from django.utils import timezone

import fields
import models

from addons.base.models import ResCompany, TimeStampedModel
from addons.certificate.models.key import (
    STR_TO_HASH, CertificateKey, _get_formatted_value,
)
from exceptions import UserError, ValidationError


class CertificateScope(models.TextChoices):
    """``scope`` — alcance del certificado (certificate.py:47-52)."""

    GENERAL = 'general', 'General'


class CertificateContentFormat(models.TextChoices):
    """``content_format`` — formato original detectado del contenido cargado
    (certificate.py:53-58)."""

    DER = 'der', 'DER'
    PEM = 'pem', 'PEM'
    PKCS12 = 'pkcs12', 'PKCS12'


class CertificateCertificate(TimeStampedModel):
    """``certificate.certificate`` — un certificado X.509 con su cadena.

    ``pem_certificate``/``content_format``/``subject_common_name``/
    ``serial_number``/``date_start``/``date_end``/``loading_error``/
    ``private_key`` son ``compute='...', store=True`` en la referencia — se
    recalculan en ``save()`` (ver módulo). ``is_valid`` e ``issuer_cert`` son
    ``compute='...'`` **sin** ``store=True`` — se exponen como ``@property``,
    sin columna, recalculados en cada lectura (fiel a esa falta de store).
    """

    name = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Nombre',
    )
    content = fields.Binary(verbose_name='Certificado')
    pkcs12_password = fields.Char(
        max_length=255, blank=True, default='',
        verbose_name='Contraseña del certificado',
        help_text='Contraseña para descifrar el archivo PKCS12.',
    )
    private_key = fields.Many2one(
        CertificateKey, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='certificates_as_private_key',
        verbose_name='Llave privada',
        help_text='Computado: se detecta o crea automáticamente al cargar '
                  'el certificado.',
    )
    public_key = fields.Many2one(
        CertificateKey, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='certificates_as_public_key',
        verbose_name='Llave pública',
        help_text='Usar cuando la llave pública autocontenida en el '
                  'certificado es errónea.',
    )
    scope = fields.Selection(
        max_length=20, choices=CertificateScope.choices, blank=True,
        default='', verbose_name='Alcance del certificado',
    )
    content_format = fields.Selection(
        max_length=10, choices=CertificateContentFormat.choices, blank=True,
        default='', verbose_name='Formato original del certificado',
    )
    pem_certificate = fields.Binary(
        null=True, blank=True, verbose_name='Certificado en PEM',
    )
    subject_common_name = fields.Char(
        max_length=255, blank=True, default='', verbose_name='Nombre del sujeto',
    )
    serial_number = fields.Char(
        max_length=64, blank=True, default='', verbose_name='Número de serie',
        help_text='El número de serie a añadir a documentos electrónicos.',
    )
    date_start = fields.Datetime(
        null=True, blank=True, verbose_name='Fecha de disponibilidad',
        help_text='La fecha desde la que el certificado es válido.',
    )
    date_end = fields.Datetime(
        null=True, blank=True, db_index=True, verbose_name='Fecha de expiración',
        help_text='La fecha en que el certificado expira.',
    )
    loading_error = fields.Text(
        blank=True, default='', verbose_name='Error de carga',
    )
    active = fields.Boolean(
        default=True, verbose_name='Activo',
        help_text='Archivar sin borrar el certificado.',
    )
    company = fields.Many2one(
        ResCompany, on_delete=models.CASCADE, related_name='certificates',
        verbose_name='Empresa',
    )

    class Meta:
        db_table = 'certificate_certificate'
        verbose_name = 'Certificado'
        verbose_name_plural = 'Certificados'
        ordering = ['-date_end']  # fiel a `_order = 'date_end DESC'`

    def __str__(self):
        return self.name or self.subject_common_name or str(self.pk)

    # -------------------------------------------------------
    #                Ciclo de vida (compute + constrains)
    # -------------------------------------------------------

    def save(self, *args, **kwargs):
        """Fusión declarada de ``create`` + ``write`` (certificate.py:483-511).

        La referencia declara **dos** métodos porque su ORM los separa: uno
        recibe ``vals_list`` (batch de altas) y el otro ``vals`` (escritura
        sobre un recordset). Django tiene **un solo** punto de persistencia
        por fila, así que los dos aterrizan aquí; el batch se colapsa a una
        fila (divergencia 5 del docstring del módulo).

        Lo que **no** se fusiona es el cuerpo: la referencia delega en
        ``_parse_chain_missing_ca_vals`` para obtener los valores de las CAs
        faltantes y crea desde el llamador. Ese reparto se conserva verbatim.
        """
        self._compute_pem_certificate()
        self._compute_private_key()
        self._constrains_certificate_loaded()
        self._constrains_certificate_key_compatibility()
        super().save(*args, **kwargs)

        # ≙ el bucle de ``create``/``write`` (certificate.py:485-491, 499-505):
        # sólo cuando hay ``content`` que parsear y se cargó bien.
        if self.content and not self.loading_error:
            for ca_vals in self._parse_chain_missing_ca_vals({
                'company': self.company,
                'content': self.content,
                'pkcs12_password': self.pkcs12_password,
            }):
                type(self).objects.create(**ca_vals)

    def clean(self):
        """``check_company=True`` de ``private_key_id``/``public_key_id``
        (certificate.py:29-46): la referencia lo declara como atributo de
        campo; Django no tiene ese mecanismo, así que la invariante —la
        llave y el certificado son de la misma empresa— es explícita aquí.
        """
        super().clean()
        if self.private_key_id and self.private_key.company_id != self.company_id:
            raise ValidationError({'private_key': 'CERTIFICATE_KEY_COMPANY_MISMATCH'})
        if self.public_key_id and self.public_key.company_id != self.company_id:
            raise ValidationError({'public_key': 'CERTIFICATE_KEY_COMPANY_MISMATCH'})

    @property
    def is_valid(self):
        """``is_valid = fields.Boolean(compute='_compute_is_valid',
        search='_search_is_valid')`` (certificate.py:92), sin ``store=True``
        — property sin columna. El cálculo vive en ``_compute_is_valid``."""
        return self._compute_is_valid()

    def _compute_is_valid(self):
        """≙ ``_compute_is_valid`` (certificate.py:251-262).

        La ventana de validez es cerrada por ambos extremos, y un certificado
        que no cargó nunca es válido. La referencia compara contra
        ``fields.Datetime.now()`` (naive-UTC); aquí contra ``timezone.now()``
        (aware), por la divergencia 2 del docstring del módulo.
        """
        if not self.date_start or not self.date_end or self.loading_error:
            return False
        now = timezone.now()
        return self.date_start <= now <= self.date_end

    @classmethod
    def _search_is_valid(cls, operator='in', value=True):
        """≙ ``_search_is_valid`` (certificate.py:264-272).

        La referencia devuelve el **dominio** que su ORM compila; aquí devuelve
        el queryset ya filtrado, que es la forma que este árbol usa para un
        ``search=`` (mismo reparto que ``_search_activity_state`` en
        ``mail_activity_mixin.py``).

        Conserva su guarda: sólo el operador ``in`` está soportado. La
        referencia devuelve ``NotImplemented`` para el resto — aquí lo mismo,
        porque un queryset vacío mentiría (diría *"no hay ninguno"* cuando lo
        que pasa es que no se sabe buscar así).
        """
        if operator != 'in':
            return NotImplemented
        now = timezone.now()
        # Los cuatro términos de la fuente, en el mismo orden.
        return cls.objects.exclude(pem_certificate__isnull=True).filter(
            date_start__lte=now, date_end__gte=now, loading_error='',
        )

    @property
    def country_code(self):
        """``related='company_id.country_code'`` (certificate.py:101)."""
        return self.company.country_code if self.company_id else ''

    @property
    def issuer_cert(self):
        """``issuer_cert_id = fields.Many2one(compute='_compute_issuer_cert_id')``
        (certificate.py:102-108), sin ``store=True`` — recalculado en cada
        lectura. El cálculo vive en ``_compute_issuer_cert_id``."""
        return self._compute_issuer_cert_id()

    def _compute_issuer_cert_id(self):
        """≙ ``_compute_issuer_cert_id`` (certificate.py:110-165).

        Ver divergencia 3 del docstring del módulo: una compañía por consulta,
        no el escaneo multi-compañía de la referencia.
        """
        loaded = self._load_x509()
        if loaded is None:
            return None
        issuer_cn = self._get_common_name(loaded, issuer=True)
        if not issuer_cn:
            return None

        # Sólo la ``company`` de la fila. El ``+ [False]`` que añade
        # ``_check_company_domain`` en la referencia es la rama de registros
        # **compartidos**, y aquí es vacía: ``certificate.company_id`` se
        # declara ``required=True`` en la referencia
        # (``odoo19c: addons/certificate/models/certificate.py:94-99``) y
        # nuestra columna es ``IS_NULLABLE = NO``, así que una CA compartida
        # no es representable en ninguno de los dos árboles. Ver H-API-298.
        candidates = list(
            type(self).objects
            .filter(company=self.company, subject_common_name=issuer_cn)
            .exclude(pk=self.pk)
            .exclude(pem_certificate__isnull=True)
            .order_by('-date_end')
        )

        # Preferencia 1: un candidato que criptográficamente firmó este
        # certificado (prueba matemática).
        for candidate in candidates:
            candidate_x509 = candidate._load_x509()
            if candidate_x509 is not None \
                    and self._is_issued_by(loaded, candidate_x509):
                return candidate

        # Preferencia 2 (sin prueba matemática): el SKI del candidato
        # coincide con el AKI esperado del certificado.
        expected_ski = self._get_authority_key_identifier(loaded)
        if expected_ski:
            for candidate in candidates:
                candidate_x509 = candidate._load_x509()
                if candidate_x509 is not None and \
                        self._get_subject_key_identifier(candidate_x509) == expected_ski:
                    return candidate
        return None

    def _load_x509(self):
        """Intenta cargar ``pem_certificate`` como x509; ``None`` si falla
        (equivalente al ``with suppress(ValueError, TypeError)`` inline de
        la referencia)."""
        if not self.pem_certificate:
            return None
        with suppress(ValueError, TypeError):
            return x509.load_pem_x509_certificate(bytes(self.pem_certificate))
        return None

    def _constrains_certificate_loaded(self):
        """``@api.constrains('content', 'pem_certificate')`` (certificate.py
        :304-310): si hay ``content`` pero no se pudo cargar, rechazar."""
        if self.content and not self.pem_certificate:
            raise ValidationError({
                'content': self.loading_error or 'CERTIFICATE_LOAD_FAILED',
            })

    def _constrains_certificate_key_compatibility(self):
        """``@api.constrains('pem_certificate', 'private_key_id',
        'public_key_id')`` (certificate.py:275-303): la llave pública de
        ``private_key``/``public_key`` debe coincidir con la del certificado."""
        if not self.pem_certificate:
            return
        cert = x509.load_pem_x509_certificate(bytes(self.pem_certificate))
        cert_public_key_bytes = cert.public_key().public_bytes(
            encoding=Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        for field_name, key in (
            ('private_key', self.private_key), ('public_key', self.public_key),
        ):
            if not key:
                continue
            if key.loading_error:
                raise ValidationError({field_name: key.loading_error})
            key_public_key_bytes = key._get_public_key_bytes(
                encoding='pem', formatting='raw')
            if not constant_time.bytes_eq(key_public_key_bytes, cert_public_key_bytes):
                raise ValidationError({field_name: 'CERTIFICATE_KEY_INCOMPATIBLE'})

    # -------------------------------------------------------
    #                       Cómputo (store=True)
    # -------------------------------------------------------

    def _compute_pem_certificate(self):
        """Normaliza ``content`` a PEM y extrae los metadatos del
        certificado. Adaptación fiel de ``_compute_pem_certificate``
        (certificate.py:208-249)."""

        def reset():
            self.pem_certificate = None
            self.subject_common_name = ''
            self.content_format = ''
            self.date_start = None
            self.date_end = None
            self.serial_number = ''
            self.loading_error = ''

        content = bytes(self.content) if self.content else None
        if not content:
            reset()
            return

        password = (self.pkcs12_password.encode('utf-8')
                    if self.pkcs12_password else None)
        leaf_pem, _additional_pems, content_format = \
            self._parse_certificate_content(content, password)

        if not leaf_pem:
            reset()
            if self.pkcs12_password:
                self.loading_error = (
                    'No se pudo cargar este certificado. Su contenido o su '
                    'contraseña son erróneos.'
                )
            return

        cert = x509.load_pem_x509_certificate(leaf_pem)
        self.loading_error = ''
        self.pem_certificate = leaf_pem
        self.content_format = content_format
        self.serial_number = str(cert.serial_number)
        self.subject_common_name = (
            self._get_common_name(cert) or str(cert.serial_number))
        self.date_start = cert.not_valid_before_utc
        self.date_end = cert.not_valid_after_utc

    def _compute_private_key(self):
        """Detecta o crea la llave privada correspondiente al certificado.

        Adaptación de ``_compute_private_key`` (certificate.py:167-206),
        simplificada: la referencia deduplica contra ``ir.attachment``
        (adjuntos del campo Binary de ``certificate.key``); aquí se
        deduplica directo contra ``CertificateKey`` por (``pem_key``,
        ``company``) — el campo YA es la tabla, sin capa de adjunto de
        por medio.
        """
        if not self.pem_certificate:
            self.private_key = None
            return

        content = bytes(self.content) if self.content else None
        password = (self.pkcs12_password.encode('utf-8')
                    if self.pkcs12_password else None)
        key = None

        if self.content_format == CertificateContentFormat.PKCS12:
            with suppress(ValueError, TypeError, UnsupportedAlgorithm):
                key, _cert, _chain = pkcs12.load_key_and_certificates(
                    content, password)
        elif self.content_format == CertificateContentFormat.PEM:
            with suppress(ValueError, TypeError, UnsupportedAlgorithm):
                key = serialization.load_pem_private_key(content, password=password)

        if key is None:
            return

        pem_key = key.private_bytes(
            encoding=Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        existing = CertificateKey.objects.filter(
            company=self.company, pem_key=pem_key,
        ).first()
        if existing is None:
            existing = CertificateKey.objects.create(
                name=(self.subject_common_name or self.name or '') + '.key',
                content=pem_key,
                company=self.company,
            )
        self.private_key = existing

    # -------------------------------------------------------
    #        Extracción de contenido (funciones puras, sin ORM)
    # -------------------------------------------------------

    @staticmethod
    def _get_subject_key_identifier(x509_cert):
        """Extrae el Subject Key Identifier (SKI), si existe."""
        with suppress(ExtensionNotFound, DuplicateExtension, ValueError):
            return x509_cert.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_KEY_IDENTIFIER).value.digest
        return None

    @staticmethod
    def _get_authority_key_identifier(x509_cert):
        """Extrae el Authority Key Identifier (AKI), si existe."""
        with suppress(ExtensionNotFound, DuplicateExtension, ValueError):
            return x509_cert.extensions.get_extension_for_oid(
                ExtensionOID.AUTHORITY_KEY_IDENTIFIER).value.key_identifier
        return None

    @staticmethod
    def _get_common_name(cert, issuer=False):
        """Extrae el Common Name del sujeto (o del emisor) del certificado."""
        with suppress(ValueError, IndexError):
            x509_name = cert.issuer if issuer else cert.subject
            return x509_name.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
        return None

    @staticmethod
    def _is_issued_by(x509_certificate, x509_issuer_certificate):
        """Verifica criptográficamente que ``x509_certificate`` fue emitido
        directamente por ``x509_issuer_certificate``: el DN del emisor debe
        coincidir y la firma debe verificar contra la llave pública del
        emisor.

        :return: ``True`` si la emisión está criptográficamente probada,
            ``False`` si está refutada, ``None`` si no se pudo comprobar
            (esquema o parámetros no soportados).
        """
        with suppress(ValueError):
            if x509_certificate.issuer != x509_issuer_certificate.subject:
                return False

        public_key = x509_issuer_certificate.public_key()
        signature = x509_certificate.signature
        signed_bytes = x509_certificate.tbs_certificate_bytes
        try:
            hash_alg = x509_certificate.signature_hash_algorithm
        except UnsupportedAlgorithm:
            return None

        match public_key:
            case ed25519.Ed25519PublicKey() | ed448.Ed448PublicKey():
                attempts, on_failure = [(signature, signed_bytes)], False
            case _ if hash_alg is None:
                attempts, on_failure = [], False
            case ec.EllipticCurvePublicKey():
                attempts, on_failure = (
                    [(signature, signed_bytes, ec.ECDSA(hash_alg))], False)
            case dsa.DSAPublicKey():
                attempts, on_failure = [(signature, signed_bytes, hash_alg)], False
            case rsa.RSAPublicKey() if (
                x509_certificate.signature_algorithm_oid
                != SignatureAlgorithmOID.RSASSA_PSS
            ):
                attempts, on_failure = (
                    [(signature, signed_bytes, padding.PKCS1v15(), hash_alg)], False)
            case rsa.RSAPublicKey():
                attempts = [
                    (signature, signed_bytes,
                     padding.PSS(mgf=padding.MGF1(hash_alg), salt_length=salt_length),
                     hash_alg)
                    for salt_length in (hash_alg.digest_size, padding.PSS.MAX_LENGTH)
                ]
                on_failure = None
            case _:
                attempts, on_failure = [], None

        for verify_args in attempts:
            with suppress(InvalidSignature, TypeError, ValueError, UnsupportedAlgorithm):
                public_key.verify(*verify_args)
                return True
        return on_failure

    @staticmethod
    def _parse_pem_certificate_bundle(decoded_content, password=None):
        """Extrae los bloques de certificado de un bundle PEM y los ordena
        según la llave privada provista (el certificado que corresponde a
        esa llave queda primero — el resto de la cadena de CA le sigue)."""

        def subject(obj):
            return obj.public_key().public_bytes(
                Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

        cert_blocks = re.findall(
            rb'(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)',
            decoded_content, flags=re.DOTALL,
        )
        certs = [x509.load_pem_x509_certificate(block) for block in cert_blocks]

        try:
            private_key = serialization.load_pem_private_key(
                decoded_content, password=password)
        except (ValueError, TypeError, UnsupportedAlgorithm):
            return cert_blocks

        target_pub_bytes = subject(private_key)
        chain_blocks = []
        for block, cert in zip(cert_blocks, certs):
            if subject(cert) == target_pub_bytes:
                chain_blocks.insert(0, block)
            else:
                chain_blocks.append(block)
        return chain_blocks

    @staticmethod
    def _parse_certificate_content(content, password=None):
        """Intenta cargar ``content`` (bytes crudos) como DER, luego PKCS12,
        luego PEM. ``content`` NO se base64-decodifica (ver divergencia 1
        del docstring del módulo)."""

        def pem(x):
            return x.public_bytes(Encoding.PEM) if x else None

        with suppress(ValueError):
            return pem(x509.load_der_x509_certificate(content)), [], \
                CertificateContentFormat.DER

        with suppress(ValueError):
            _key, leaf_cert, additional_certs = \
                pkcs12.load_key_and_certificates(content, password)
            return (pem(leaf_cert), [pem(x) for x in additional_certs],
                    CertificateContentFormat.PKCS12)

        with suppress(ValueError):
            leaf, *additional = CertificateCertificate._parse_pem_certificate_bundle(
                content, password)
            return leaf, additional, CertificateContentFormat.PEM

        return None, [], None

    @staticmethod
    def _extract_and_filter_chain(content_bytes, password=None):
        """Devuelve sólo los certificados de la cadena del leaf (leaf →
        raíz), descartando lo que el bundle traiga de más."""
        leaf_pem, additional_pems, _fmt = \
            CertificateCertificate._parse_certificate_content(content_bytes, password)
        if not leaf_pem:
            return [None]

        ski_cert_map = {}
        for pem in additional_pems:
            cert = x509.load_pem_x509_certificate(pem)
            ski = CertificateCertificate._get_subject_key_identifier(cert)
            if ski:
                ski_cert_map[ski] = cert

        leaf_cert = x509.load_pem_x509_certificate(leaf_pem)
        certs_chain = [leaf_cert]
        current_cert = leaf_cert
        while True:
            aki = CertificateCertificate._get_authority_key_identifier(current_cert)
            parent_cert = ski_cert_map.get(aki) if aki else None
            if parent_cert is None or parent_cert in certs_chain:
                break
            certs_chain.append(parent_cert)
            current_cert = parent_cert

        return [c.public_bytes(Encoding.PEM) for c in certs_chain]

    # -------------------------------------------------------
    #             Auto-creación de CAs (create/write de la referencia)
    # -------------------------------------------------------

    def _parse_chain_missing_ca_vals(self, vals):
        """≙ ``_parse_chain_missing_ca_vals`` (certificate.py:513-562).

        Extrae la cadena de CAs del ``content`` y devuelve **los diccionarios
        de campos de las que faltan** en la base — no las crea. Quien crea es
        el llamador, igual que en la referencia: allí son ``create``/``write``
        (certificate.py:483-511), aquí es ``save()`` (divergencia 5 del
        docstring del módulo: el batch por ``vals_list`` se colapsa a una fila).

        :param vals: los valores de la escritura en curso. La referencia lee
          ``company_id``/``pkcs12_password``/``content`` de ahí; se conserva
          la firma para que el llamador siga siendo quien decide qué valores
          se están escribiendo.
        :return: lista de ``dict`` listos para ``objects.create()``.
        """
        company = vals.get('company')
        password = (vals['pkcs12_password'].encode('utf-8')
                    if vals.get('pkcs12_password') else None)
        content = bytes(vals.get('content') or b'')

        _leaf_pem, *ca_pems = self._extract_and_filter_chain(content, password)
        if not ca_pems:
            return []

        ca_data_list = []
        for pem in ca_pems:
            ca_cert = x509.load_pem_x509_certificate(pem)
            serial = str(ca_cert.serial_number)
            subject = self._get_common_name(ca_cert) or serial
            ca_data_list.append({
                'name': f'{subject} (CA)', 'company': company,
                'serial_number': serial, 'subject_common_name': subject,
                'content': pem, 'active': False,
            })

        # Las ya existentes se descartan para no duplicar. La referencia usa
        # ``with_context(active_test=False)`` porque una CA se siembra con
        # ``active=False``; aquí no hay ``active_test``, así que el queryset
        # ya ve las archivadas sin pedir nada.
        existing_keys = set(
            type(self).objects.filter(
                company=company,
                serial_number__in=[d['serial_number'] for d in ca_data_list],
            ).values_list('serial_number', 'subject_common_name')
        )

        missing = []
        for ca_data in ca_data_list:
            key = (ca_data['serial_number'], ca_data['subject_common_name'])
            if key in existing_keys:
                continue
            missing.append(ca_data)
            existing_keys.add(key)
        return missing

    # -------------------------------------------------------
    #                   Métodos de negocio
    # -------------------------------------------------------

    def _get_der_certificate_bytes(self, formatting='encodebytes'):
        """Bytes DER del certificado."""
        cert = x509.load_pem_x509_certificate(bytes(self.pem_certificate))
        return _get_formatted_value(
            cert.public_bytes(serialization.Encoding.DER), formatting=formatting)

    def _get_fingerprint_bytes(self, hashing_algorithm='sha256', formatting='encodebytes'):
        """Bytes de la huella (fingerprint) del certificado."""
        cert = x509.load_pem_x509_certificate(bytes(self.pem_certificate))
        if hashing_algorithm not in STR_TO_HASH:
            raise UserError(
                f"Algoritmo de hash no soportado '{hashing_algorithm}'. "
                "Soportados: sha1 y sha256.")
        return _get_formatted_value(
            cert.fingerprint(STR_TO_HASH[hashing_algorithm]), formatting=formatting)

    def _get_signature_bytes(self, formatting='encodebytes'):
        """Bytes de la firma del certificado."""
        cert = x509.load_pem_x509_certificate(bytes(self.pem_certificate))
        return _get_formatted_value(cert.signature, formatting=formatting)

    def _get_public_key_numbers_bytes(self, formatting='encodebytes'):
        """Números públicos de la llave pública del certificado."""
        if self.public_key or self.private_key:
            return (self.public_key or self.private_key)._get_public_key_numbers_bytes(
                formatting=formatting)
        return CertificateKey._numbers_public_key_bytes_with_key(
            self._get_public_key_bytes(encoding='pem', formatting='raw'),
            formatting=formatting,
        )

    def _get_public_key_bytes(self, encoding='der', formatting='encodebytes'):
        """Bytes de la llave pública del certificado."""
        if self.public_key or self.private_key:
            return (self.public_key or self.private_key)._get_public_key_bytes(
                encoding=encoding, formatting=formatting)

        try:
            cert = x509.load_pem_x509_certificate(bytes(self.pem_certificate))
            public_key = cert.public_key()
        except ValueError:
            raise UserError('No se pudo cargar la llave pública del certificado.')

        enc = (serialization.Encoding.DER if encoding == 'der'
               else serialization.Encoding.PEM)
        return _get_formatted_value(
            public_key.public_bytes(
                encoding=enc,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
            formatting=formatting,
        )

    def _sign(self, message, hashing_algorithm='sha256', formatting='encodebytes'):
        """Firma ``message`` con la llave privada de este certificado."""
        if not self.is_valid:
            raise UserError(
                self.loading_error or
                'Este certificado no es válido, su vigencia expiró.')
        if not self.private_key:
            raise UserError(
                'No hay llave privada asociada al certificado; es '
                'requerida para firmar documentos.')

        return self.private_key._sign(
            message, hashing_algorithm=hashing_algorithm, formatting=formatting)

    def _get_certificate_chain(self):
        """Cadena completa del certificado, Leaf → Root, siguiendo
        ``issuer_cert``.

        Divergencia declarada: la referencia devuelve un recordset; Django
        no tiene ese tipo — se devuelve una ``list`` de instancias.
        """
        chain = [self]
        current = self
        while True:
            issuer = current.issuer_cert
            if issuer is None or issuer in chain:
                break
            chain.append(issuer)
            current = issuer
        return chain
