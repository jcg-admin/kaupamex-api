"""Contrato de ``CertificateCertificate`` — puerto de ``certificate.certificate``
(Odoo 19c).

Adaptación de Odoo certificate/models/certificate.py (odoo-tools@622ddc2a,
odoo19c:, LGPL-3). Cubre el cómputo de metadatos x509 (``_compute_pem_
certificate``), la detección/creación de la llave privada
(``_compute_private_key``), ``is_valid``, la resolución de cadena
(``issuer_cert`` / ``_get_certificate_chain``), la auto-creación de CAs
faltantes y las invariantes de compatibilidad llave/certificado.
"""
import datetime

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from django.core.exceptions import ValidationError
from django.utils import timezone

from addons.base.models import ResCompany
from addons.certificate.models.certificate import CertificateCertificate
from addons.certificate.models.key import CertificateKey
from exceptions import UserError

pytestmark = pytest.mark.django_db


def _company(code):
    return ResCompany.objects.create(code=code, name=code)


def _rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _private_pem(private_key):
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _self_signed_cert(private_key, common_name, days_valid=365,
                       not_before_delta=-1, extensions=True):
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now + datetime.timedelta(days=not_before_delta))
        .not_valid_after(now + datetime.timedelta(days=days_valid))
    )
    if extensions:
        ski = x509.SubjectKeyIdentifier.from_public_key(private_key.public_key())
        builder = builder.add_extension(ski, critical=False)
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ski),
            critical=False,
        )
    return builder.sign(private_key, hashes.SHA256())


def _signed_cert(subject_private_key, common_name, issuer_private_key,
                  issuer_cert, days_valid=365):
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    subject_ski = x509.SubjectKeyIdentifier.from_public_key(
        subject_private_key.public_key())
    issuer_ski = issuer_cert.extensions.get_extension_for_class(
        x509.SubjectKeyIdentifier).value
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_cert.subject)
        .public_key(subject_private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=days_valid))
        .add_extension(subject_ski, critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier(
                key_identifier=issuer_ski.digest,
                authority_cert_issuer=None,
                authority_cert_serial_number=None,
            ),
            critical=False,
        )
    )
    return builder.sign(issuer_private_key, hashes.SHA256())


def _pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


class TestComputePemCertificateDer:
    def test_der_content_is_detected_and_metadata_extracted(self):
        acme = _company('acme-cert-der-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'der-leaf')
        der_bytes = cert.public_bytes(serialization.Encoding.DER)

        row = CertificateCertificate(name='c', company=acme, content=der_bytes)
        row.save()

        assert row.content_format == 'der'
        assert row.subject_common_name == 'der-leaf'
        assert row.serial_number == str(cert.serial_number)
        assert row.loading_error == ''
        assert bytes(row.pem_certificate).startswith(
            b'-----BEGIN CERTIFICATE-----')

    def test_date_start_and_date_end_are_timezone_aware(self):
        """Divergencia deliberada vs. la referencia: aquí quedan aware (UTC),
        no naive — ver docstring de ``certificate.py`` (``USE_TZ=True``)."""
        acme = _company('acme-cert-tz-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'tz-leaf')
        row = CertificateCertificate(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
        )
        row.save()
        assert row.date_start.tzinfo is not None
        assert row.date_end.tzinfo is not None


class TestComputePemCertificatePem:
    def test_pem_bundle_with_private_key_detects_leaf_and_links_private_key(self):
        acme = _company('acme-cert-pem-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'pem-leaf')
        bundle = _private_pem(priv) + _pem(cert)

        row = CertificateCertificate(name='c', company=acme, content=bundle)
        row.save()

        assert row.content_format == 'pem'
        assert row.subject_common_name == 'pem-leaf'
        assert row.private_key is not None
        assert row.private_key.public is False
        assert row.private_key.company_id == acme.pk


class TestComputePemCertificatePkcs12:
    def test_pkcs12_bundle_is_detected_and_loaded(self):
        acme = _company('acme-cert-p12-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'p12-leaf')
        p12_bytes = pkcs12.serialize_key_and_certificates(
            name=b'p12-leaf', key=priv, cert=cert,
            cas=None, encryption_algorithm=serialization.NoEncryption(),
        )

        row = CertificateCertificate(name='c', company=acme, content=p12_bytes)
        row.save()

        assert row.content_format == 'pkcs12'
        assert row.subject_common_name == 'p12-leaf'
        assert row.private_key is not None


class TestLoadingError:
    def test_garbage_content_computes_no_pem_and_is_not_valid(self):
        """Sólo el cómputo (sin ``save()``): fiel a ``_compute_pem_certificate``
        (certificate.py:208-249) en aislamiento, antes de que el constrain
        de la siguiente prueba lo rechace."""
        acme = _company('acme-cert-bad-1')
        row = CertificateCertificate(
            name='bad', company=acme, content=b'no es un certificado')
        row._compute_pem_certificate()
        assert row.pem_certificate is None
        assert row.content_format == ''
        assert row.is_valid is False

    def test_save_rejects_content_that_failed_to_load(self):
        """``@api.constrains('content', 'pem_certificate')`` (certificate.py
        :304-310): ``content`` puesto pero no cargado → rechazado en escritura."""
        acme = _company('acme-cert-bad-2')
        row = CertificateCertificate(
            name='bad', company=acme, content=b'no es un certificado')
        with pytest.raises(ValidationError):
            row.save()


class TestIsValid:
    def test_expired_certificate_is_not_valid(self):
        acme = _company('acme-cert-expired-1')
        priv = _rsa_key()
        cert = _self_signed_cert(
            priv, 'expired-leaf', days_valid=-1, not_before_delta=-30)
        row = CertificateCertificate.objects.create(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
        )
        assert row.is_valid is False

    def test_currently_valid_certificate_is_valid(self):
        acme = _company('acme-cert-valid-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'valid-leaf')
        row = CertificateCertificate.objects.create(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
        )
        assert row.is_valid is True


class TestIssuerChain:
    def test_leaf_signed_by_root_resolves_issuer_cert_to_the_root(self):
        acme = _company('acme-cert-chain-1')
        root_priv = _rsa_key()
        root_cert = _self_signed_cert(root_priv, 'root-ca')
        root_row = CertificateCertificate.objects.create(
            name='root', company=acme,
            content=root_cert.public_bytes(serialization.Encoding.DER),
        )

        leaf_priv = _rsa_key()
        leaf_cert = _signed_cert(leaf_priv, 'leaf', root_priv, root_cert)
        leaf_row = CertificateCertificate.objects.create(
            name='leaf', company=acme,
            content=leaf_cert.public_bytes(serialization.Encoding.DER),
        )

        issuer = leaf_row.issuer_cert
        assert issuer is not None
        assert issuer.pk == root_row.pk

    def test_get_certificate_chain_returns_leaf_then_root(self):
        acme = _company('acme-cert-chain-2')
        root_priv = _rsa_key()
        root_cert = _self_signed_cert(root_priv, 'root-ca-2')
        root_row = CertificateCertificate.objects.create(
            name='root', company=acme,
            content=root_cert.public_bytes(serialization.Encoding.DER),
        )
        leaf_priv = _rsa_key()
        leaf_cert = _signed_cert(leaf_priv, 'leaf-2', root_priv, root_cert)
        leaf_row = CertificateCertificate.objects.create(
            name='leaf', company=acme,
            content=leaf_cert.public_bytes(serialization.Encoding.DER),
        )

        chain = leaf_row._get_certificate_chain()
        assert [c.pk for c in chain] == [leaf_row.pk, root_row.pk]

    def test_self_signed_certificate_has_no_further_issuer(self):
        acme = _company('acme-cert-chain-3')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'self-signed')
        row = CertificateCertificate.objects.create(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
        )
        # El propio certificado es su emisor por DN pero la referencia lo
        # excluye explícitamente en `_is_issued_by`'s caller (Odoo:
        # "Exclude the certificate itself"); aquí, `.exclude(pk=self.pk)`
        # en la property `issuer_cert` cumple el mismo rol.
        assert row.issuer_cert is None


class TestAutoCaCreation:
    def test_bundle_with_missing_intermediate_ca_creates_it_archived(self):
        acme = _company('acme-cert-autoca-1')
        root_priv = _rsa_key()
        root_cert = _self_signed_cert(root_priv, 'auto-root')

        leaf_priv = _rsa_key()
        leaf_cert = _signed_cert(leaf_priv, 'auto-leaf', root_priv, root_cert)

        bundle = _private_pem(leaf_priv) + _pem(leaf_cert) + _pem(root_cert)
        leaf_row = CertificateCertificate.objects.create(
            name='leaf', company=acme, content=bundle)

        created_root = CertificateCertificate.objects.filter(
            company=acme, subject_common_name='auto-root',
        ).exclude(pk=leaf_row.pk).first()

        assert created_root is not None
        assert created_root.active is False
        assert created_root.issuer_cert is None or \
            created_root.issuer_cert.pk == created_root.pk

    def test_auto_ca_creation_is_idempotent_across_two_certificates(self):
        """Dos hojas emitidas por la misma CA no duplican la CA (fiel a la
        deduplicación por (serial_number, subject_common_name) de
        ``_parse_chain_missing_ca_vals``)."""
        acme = _company('acme-cert-autoca-2')
        root_priv = _rsa_key()
        root_cert = _self_signed_cert(root_priv, 'auto-root-shared')

        for cn in ('leaf-a', 'leaf-b'):
            leaf_priv = _rsa_key()
            leaf_cert = _signed_cert(leaf_priv, cn, root_priv, root_cert)
            bundle = _private_pem(leaf_priv) + _pem(leaf_cert) + _pem(root_cert)
            CertificateCertificate.objects.create(
                name=cn, company=acme, content=bundle)

        root_count = CertificateCertificate.objects.filter(
            company=acme, subject_common_name='auto-root-shared',
        ).count()
        assert root_count == 1


class TestCertificateKeyCompatibility:
    def test_public_key_matching_the_certificate_is_accepted(self):
        acme = _company('acme-cert-compat-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'compat-leaf')
        pub_pem = priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        pub_key_row = CertificateKey.objects.create(
            name='pub', company=acme, content=pub_pem)

        row = CertificateCertificate(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
            public_key=pub_key_row,
        )
        row.save()  # no debe lanzar
        assert row.pk is not None

    def test_mismatched_public_key_is_rejected(self):
        acme = _company('acme-cert-compat-2')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'compat-leaf-2')

        other_priv = _rsa_key()
        other_pub_pem = other_priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        mismatched_key = CertificateKey.objects.create(
            name='pub-otra', company=acme, content=other_pub_pem)

        row = CertificateCertificate(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
            public_key=mismatched_key,
        )
        with pytest.raises(ValidationError):
            row.save()


class TestCompanyMismatchClean:
    def test_clean_rejects_public_key_from_a_different_company(self):
        acme = _company('acme-cert-clean-1')
        globex = _company('globex-cert-clean-1')
        priv = _rsa_key()
        pub_pem = priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        other_company_key = CertificateKey.objects.create(
            name='k', company=globex, content=pub_pem)

        cert = _self_signed_cert(priv, 'clean-leaf')
        row = CertificateCertificate(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
            public_key=other_company_key,
        )
        row._compute_pem_certificate()
        with pytest.raises(ValidationError):
            row.clean()


class TestBusinessMethods:
    def test_get_der_certificate_bytes_roundtrips_to_the_same_certificate(self):
        acme = _company('acme-cert-der-bytes-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'der-bytes-leaf')
        row = CertificateCertificate.objects.create(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
        )
        der_out = row._get_der_certificate_bytes(formatting='raw')
        assert x509.load_der_x509_certificate(der_out).serial_number == \
            cert.serial_number

    def test_get_fingerprint_bytes_matches_manual_fingerprint(self):
        acme = _company('acme-cert-fp-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'fp-leaf')
        row = CertificateCertificate.objects.create(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
        )
        fp = row._get_fingerprint_bytes(formatting='raw')
        assert fp == cert.fingerprint(hashes.SHA256())

    def test_sign_uses_the_linked_private_key(self):
        acme = _company('acme-cert-sign-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'sign-leaf')
        bundle = _private_pem(priv) + _pem(cert)
        row = CertificateCertificate.objects.create(
            name='c', company=acme, content=bundle)

        signature = row._sign(b'documento')
        assert len(signature) > 0

    def test_sign_raises_without_private_key(self):
        acme = _company('acme-cert-sign-2')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'sign-leaf-2')
        row = CertificateCertificate.objects.create(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
        )
        assert row.private_key is None
        with pytest.raises(UserError):
            row._sign(b'documento')

    def test_sign_raises_on_expired_certificate(self):
        acme = _company('acme-cert-sign-3')
        priv = _rsa_key()
        cert = _self_signed_cert(
            priv, 'sign-leaf-expired', days_valid=-1, not_before_delta=-30)
        bundle = _private_pem(priv) + _pem(cert)
        row = CertificateCertificate.objects.create(
            name='c', company=acme, content=bundle)
        with pytest.raises(UserError):
            row._sign(b'documento')


class TestMeta:
    def test_str_prefers_name(self):
        acme = _company('acme-cert-str-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'str-leaf')
        row = CertificateCertificate.objects.create(
            name='mi-certificado', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
        )
        assert str(row) == 'mi-certificado'

    def test_country_code_delegates_to_company(self):
        acme = _company('acme-cert-country-1')
        priv = _rsa_key()
        cert = _self_signed_cert(priv, 'country-leaf')
        row = CertificateCertificate.objects.create(
            name='c', company=acme,
            content=cert.public_bytes(serialization.Encoding.DER),
        )
        assert row.country_code == acme.country_code


class TestSearchIsValid:
    """``_search_is_valid`` (``odoo19c: certificate.py:264-272``).

    Es el ``search=`` que la referencia declara junto al ``compute=`` en el
    campo ``is_valid``: sin él, un campo calculado no persistido no es
    buscable. Los cuatro términos de la fuente —``pem_certificate`` presente,
    la ventana de fechas abierta, y ``loading_error`` vacío— se ejercitan aquí
    contra filas reales, no contra el código.

    **Medido con la guarda anulada**, término por término: retirando cualquiera
    de los cuatro del filtro —o la guarda del operador— cae al menos un caso.

    ==========================  ===========================
    término retirado            resultado del subconjunto
    ==========================  ===========================
    ``pem_certificate``         1 failed, 5 passed
    ``date_start <= now``       1 failed, 5 passed
    ``date_end >= now``         2 failed, 4 passed
    ``loading_error == \'\'``     1 failed, 5 passed
    guarda ``operator != in``   1 failed, 5 passed
    ==========================  ===========================

    Las dos primeras filas NO discriminaban en la primera versión de esta
    clase: el caso de contenido basura se caía por el primer término, así que
    ni el de ``loading_error`` ni el de la ventana llegaban a medirse.
    Cada término tiene ahora su caso con los otros tres cumpliéndose.
    Restaurada la guarda, el archivo vuelve byte a byte a su versión.
    """

    def test_only_currently_valid_certificates_come_back(self):
        acme = _company('acme-cert-search-1')
        priv = _rsa_key()
        vigente = CertificateCertificate.objects.create(
            name='vigente', company=acme,
            content=_self_signed_cert(priv, 'search-vigente').public_bytes(
                serialization.Encoding.DER),
        )
        CertificateCertificate.objects.create(
            name='vencido', company=acme,
            content=_self_signed_cert(
                priv, 'search-vencido', days_valid=-1,
                not_before_delta=-30).public_bytes(serialization.Encoding.DER),
        )

        encontrados = CertificateCertificate._search_is_valid().filter(
            company=acme)
        assert list(encontrados) == [vigente]

    def test_a_certificate_with_a_loading_error_is_excluded(self):
        """El cuarto término (``loading_error = \'\'``), aislado.

        El estado se construye a mano y eso es deliberado: por el camino real
        es inalcanzable, porque ``_compute_pem_certificate`` pone
        ``loading_error = \'\'`` justo antes de asignar ``pem_certificate``
        (``certificate.py:401-402``). Una fila con contenido basura tampoco
        sirve como caso — se cae por el PRIMER término
        (``pem_certificate`` nulo) y el cuarto nunca se ejercita.

        Medido: con el término retirado del filtro, este caso pasa de fallar a
        pasar, así que es él quien lo mide y no otro.
        """
        acme = _company('acme-cert-search-2')
        priv = _rsa_key()
        fila = CertificateCertificate.objects.create(
            name='con-error', company=acme,
            content=_self_signed_cert(priv, 'search-con-error').public_bytes(
                serialization.Encoding.DER),
        )
        # Los otros tres términos se cumplen: entra en la búsqueda.
        assert fila in CertificateCertificate._search_is_valid()

        CertificateCertificate.objects.filter(pk=fila.pk).update(
            loading_error='no se pudo cargar')
        assert fila not in CertificateCertificate._search_is_valid()

    def test_a_certificate_not_yet_in_force_is_excluded(self):
        """El segundo término (``date_start <= now``), aislado.

        Un certificado cuya ventana **aún no abre** cumple los otros tres
        —tiene ``pem_certificate``, su ``date_end`` es futuro y no hubo error
        de carga— así que sólo este término lo deja fuera. Sin este caso, el
        término se podía retirar del filtro y la suite seguía verde.
        """
        acme = _company('acme-cert-search-4')
        priv = _rsa_key()
        futuro = CertificateCertificate.objects.create(
            name='aun-no-vigente', company=acme,
            content=_self_signed_cert(
                priv, 'search-futuro', days_valid=365,
                not_before_delta=10).public_bytes(serialization.Encoding.DER),
        )
        assert futuro.date_start > timezone.now()
        assert futuro.date_end > timezone.now()
        assert futuro.pem_certificate
        assert not futuro.loading_error
        assert futuro not in CertificateCertificate._search_is_valid()

    def test_a_row_without_pem_certificate_is_excluded(self):
        """El primer término (``pem_certificate`` presente), aislado.

        Los otros tres se fuerzan a cumplirse —ventana abierta, sin error de
        carga— para que sólo la ausencia del PEM decida. Ese estado no se
        alcanza por ``save()``, que rechaza el contenido que no cargó
        (``_constrains_certificate_loaded``); se construye con ``update()``
        por la misma razón que el caso de ``loading_error``.
        """
        acme = _company('acme-cert-search-5')
        priv = _rsa_key()
        fila = CertificateCertificate.objects.create(
            name='sin-pem', company=acme,
            content=_self_signed_cert(priv, 'search-sin-pem').public_bytes(
                serialization.Encoding.DER),
        )
        assert fila in CertificateCertificate._search_is_valid()

        CertificateCertificate.objects.filter(pk=fila.pk).update(
            pem_certificate=None)
        assert fila not in CertificateCertificate._search_is_valid()

    def test_an_unsupported_operator_returns_not_implemented(self):
        """La guarda de la fuente: sólo ``in``.

        Devolver un queryset vacío mentiría — diría *"no hay ninguno"* cuando
        lo que ocurre es que no se sabe buscar así. La referencia devuelve
        ``NotImplemented`` y aquí igual.
        """
        assert CertificateCertificate._search_is_valid('=') is NotImplemented

    def test_the_search_agrees_with_the_compute_row_by_row(self):
        """El control que liga los dos símbolos: lo que ``_search_is_valid``
        devuelve es exactamente el conjunto de filas cuyo ``_compute_is_valid``
        da verdadero. Si divergieran, el campo ``is_valid`` mostraría una cosa
        y el filtro devolvería otra."""
        acme = _company('acme-cert-search-3')
        priv = _rsa_key()
        for label, days in (('uno', 365), ('dos', -1), ('tres', 30)):
            CertificateCertificate.objects.create(
                name=label, company=acme,
                content=_self_signed_cert(
                    priv, f'search-{label}', days_valid=days,
                    not_before_delta=-30).public_bytes(
                        serialization.Encoding.DER),
            )
        del priv

        todas = CertificateCertificate.objects.filter(company=acme)
        by_compute = {r.pk for r in todas if r._compute_is_valid()}
        by_search = set(
            CertificateCertificate._search_is_valid()
            .filter(company=acme).values_list('pk', flat=True))
        assert by_compute == by_search
        assert by_compute  # el conjunto no es vacío: el acuerdo no es trivial
