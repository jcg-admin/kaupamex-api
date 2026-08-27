"""Tests — el mimetype de un adjunto, y por que no se cree lo que le digan.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_attachment.py``:
``_compute_mimetype``, ``_check_contents``, ``_generate_access_token`` /
``generate_access_token`` y ``_check_circular_attachment``.

El eje es ``_check_contents`` y es de seguridad
===============================================

La fuente **degrada a ``text/plain``** todo lo que huela a HTML o XML —``ht``
en el mimetype, o ``xml`` sin ser un formato Office— cuando quien sube no
tiene permiso de escribir vistas. Sin esa degradacion, un ``.svg`` o un
``.html`` subido por cualquiera y servido de vuelta con su propio mimetype es
XSS almacenado: el navegador de quien lo abra ejecuta el script que trae
dentro, en el origen del producto.

Aqui el permiso lo decide la capa DRF (DEC-11), no el modelo, asi que la
decision entra por el argumento ``trusted`` y su **valor por defecto es
falso** — fail-closed, como ``HasCapability``.

Los controles, cada uno con lo que lo haria fallar
---------------------------------------------------

``TestContents.test_an_svg_from_anyone_becomes_plain_text``
    El eje. Qué lo haría fallar: retirar la degradacion, o mirar sólo
    ``text/html`` y no la familia entera.

``TestContents.test_an_office_document_is_not_degraded``
    CONTROL de la dirección contraria: los formatos Office llevan ``xml`` en
    su mimetype y la fuente los exceptua por nombre. Una degradacion que mire
    ``xml`` a secas rompe la subida de un ``.docx``.

``TestContents.test_a_trusted_caller_keeps_the_mimetype``
    CONTROL: ``trusted=True`` ≙ *"tiene permiso de escribir vistas"*. Sin este
    caso, degradar SIEMPRE pasaria igual y el argumento seria decorativo.

``TestToken.test_the_token_is_generated_once``
    Qué lo haría fallar: regenerarlo en cada llamada. La fuente devuelve el
    que ya hay; un token que cambia invalida los enlaces ya repartidos.
"""
import base64

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model

from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.res_groups import ResGroups
from exceptions import ValidationError

pytestmark = pytest.mark.integration

SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
DOCX = ('application/vnd.openxmlformats-officedocument'
        '.wordprocessingml.document')


class TestMimetype:
    """≙ ``_compute_mimetype`` — del valor dado, del nombre, de la url."""

    def test_a_given_mimetype_wins(self):
        assert IrAttachment._compute_mimetype(
            {'mimetype': 'image/png', 'name': 'x.txt'}) == 'image/png'

    def test_without_one_it_is_guessed_from_the_name(self):
        assert IrAttachment._compute_mimetype({'name': 'factura.pdf'}) == \
            'application/pdf'

    def test_the_url_loses_its_query_string_first(self):
        """La fuente parte por ``?`` antes de adivinar."""
        assert IrAttachment._compute_mimetype(
            {'url': 'https://x.mx/logo.png?v=3'}) == 'image/png'

    def test_with_nothing_to_go_on_it_is_a_binary_stream(self):
        assert IrAttachment._compute_mimetype({}) == 'application/octet-stream'

    def test_it_comes_back_in_lower_case(self):
        assert IrAttachment._compute_mimetype(
            {'mimetype': 'IMAGE/PNG'}) == 'image/png'


class TestContents:
    """≙ ``_check_contents`` — la degradacion que evita el XSS almacenado."""

    def test_an_svg_from_anyone_becomes_plain_text(self):
        values = IrAttachment._check_contents(
            {'name': 'logo.svg', 'raw': SVG})
        assert values['mimetype'] == 'text/plain'

    def test_an_html_from_anyone_becomes_plain_text(self):
        values = IrAttachment._check_contents({'name': 'nota.html'})
        assert values['mimetype'] == 'text/plain'

    def test_an_office_document_is_not_degraded(self):
        """CONTROL — lleva ``xml`` y la fuente lo exceptua por nombre."""
        values = IrAttachment._check_contents(
            {'name': 'contrato.docx', 'mimetype': DOCX})
        assert values['mimetype'] == DOCX

    def test_a_png_is_not_degraded(self):
        values = IrAttachment._check_contents({'name': 'foto.png'})
        assert values['mimetype'] == 'image/png'

    def test_a_trusted_caller_keeps_the_mimetype(self):
        """CONTROL — sin este caso el argumento seria decorativo."""
        values = IrAttachment._check_contents(
            {'name': 'plantilla.html'}, trusted=True)
        assert values['mimetype'] == 'text/html'

    def test_the_default_is_fail_closed(self):
        """No hace falta pedir la degradacion: es lo que pasa si nadie decide."""
        values = IrAttachment._check_contents({'name': 'x.svg'})
        assert values['mimetype'] == 'text/plain'


class TestToken:
    """≙ ``_generate_access_token`` / ``generate_access_token``."""

    def test_the_token_is_generated_once(self, db):
        card = IrAttachment(name='x.pdf', res_model='res.partner', res_id=1)
        card.save()
        first = card.generate_access_token()
        second = card.generate_access_token()
        assert first == second, 'un token que cambia invalida los enlaces'
        assert len(first) == 36, 'la fuente usa uuid4 en su forma canonica'

    def test_two_attachments_do_not_share_a_token(self, db):
        uno = IrAttachment(name='a.pdf', res_model='res.partner', res_id=1)
        uno.save()
        dos = IrAttachment(name='b.pdf', res_model='res.partner', res_id=2)
        dos.save()
        assert uno.generate_access_token() != dos.generate_access_token()


class TestCircular:
    """≙ ``_check_circular_attachment`` — un adjunto de si mismo."""

    def test_an_attachment_of_itself_is_refused(self, db):
        card = IrAttachment(name='x.pdf', res_model='res.partner', res_id=1)
        card.save()
        card.res_model = 'ir.attachment'
        card.res_id = card.pk
        with pytest.raises(ValidationError):
            card.clean()

    def test_an_attachment_of_ANOTHER_attachment_is_fine(self, db):
        """CONTROL — la fuente prohibe el bucle, no la relacion."""
        uno = IrAttachment(name='a.pdf', res_model='res.partner', res_id=1)
        uno.save()
        dos = IrAttachment(name='b.pdf', res_model='ir.attachment',
                           res_id=uno.pk)
        dos.save()
        dos.clean()


class TestWiring:
    """La guarda cableada — ≙ la llamada desde ``create``/``write``.

    Sin esta clase, ``_check_contents`` seria una funcion correcta que nadie
    invoca: exactamente el defecto que :ref:`h-api-836` registro en
    ``ir_ui_view`` el mismo dia. Qué lo haría fallar: retirar la llamada de
    ``save``.
    """

    def test_an_svg_saved_by_anyone_lands_as_plain_text(self, db):
        card = IrAttachment(name='logo.svg', res_model='res.partner',
                            res_id=1)
        card.save()
        card.refresh_from_db()
        assert card.mimetype == 'text/plain'

    def test_a_trusted_save_keeps_the_mimetype(self, db):
        card = IrAttachment(name='plantilla.html', res_model='res.partner',
                            res_id=1)
        card.save(trusted=True)
        card.refresh_from_db()
        assert card.mimetype == 'text/html'

    def test_a_png_saved_keeps_its_type(self, db):
        """CONTROL — la guarda degrada lo peligroso, no todo."""
        card = IrAttachment(name='foto.png', res_model='res.partner',
                            res_id=1)
        card.save()
        card.refresh_from_db()
        assert card.mimetype == 'image/png'


class TestAclPermission:
    """La condicion de permiso, derivada de la ACL — ≙ ``has_access('write')``.

    La primera version de este porte declaraba que la condicion NO se podia
    portar *"porque la autorizacion vive en la capa DRF"*. Era falso a medias:
    el gate efectivo del producto si es ``HasCapability`` (DEC-11), pero
    ``ir.model.access`` **esta portada como dato**, con su ``perm_write`` por
    modelo y grupo, y consultarla es exactamente lo que hace la fuente.

    Qué lo haría fallar, caso por caso: que ``_can_write_views`` ignore la ACL
    global, que ignore la de grupo, o que responda ``True`` sin usuario.
    """

    def _acl(self, **extra):
        IrModel = apps.get_model('base', 'IrModel')
        IrModelAccess = apps.get_model('base', 'IrModelAccess')
        view_model, _ = IrModel.objects.get_or_create(
            model='ir.ui.view', defaults={'name': 'Vista'})
        data = dict(name='acl de prueba', model_id=view_model,
                    perm_write=True)
        data.update(extra)
        return IrModelAccess.objects.create(**data)

    def test_without_a_user_it_degrades(self, db):
        """CONTROL — una creacion sin peticion detras degrada, no confia."""
        assert IrAttachment._can_write_views(None) is False

    def test_a_global_acl_opens_it_to_everyone(self, db):
        self._acl(group_id=None)
        who = get_user_model().objects.create_user(
            login='acl.global@practicayoruba.mx', password='AclPrueba123!')
        assert IrAttachment._can_write_views(who) is True

    def test_an_acl_of_a_group_opens_it_to_its_members(self, db):
        group = ResGroups.objects.create(name='editores de vista',
                                         user_type='internal')
        self._acl(group_id=group)
        who = get_user_model().objects.create_user(
            login='acl.grupo@practicayoruba.mx', password='AclPrueba123!')
        assert IrAttachment._can_write_views(who) is False, 'sin el grupo, no'
        who.group_ids.add(group)
        assert IrAttachment._can_write_views(who) is True

    def test_a_user_outside_the_group_still_degrades(self, db):
        """CONTROL — la ACL de un grupo no abre el permiso a cualquiera."""
        group = ResGroups.objects.create(name='otros editores',
                                         user_type='internal')
        self._acl(group_id=group)
        fuera = get_user_model().objects.create_user(
            login='acl.fuera@practicayoruba.mx', password='AclPrueba123!')
        values = IrAttachment._check_contents({'name': 'x.svg'},
                                              user=fuera)
        assert values['mimetype'] == 'text/plain'

    def test_the_user_with_the_acl_keeps_the_mimetype(self, db):
        group = ResGroups.objects.create(name='editores con acl',
                                         user_type='internal')
        self._acl(group_id=group)
        dentro = get_user_model().objects.create_user(
            login='acl.dentro@practicayoruba.mx', password='AclPrueba123!')
        dentro.group_ids.add(group)
        values = IrAttachment._check_contents({'name': 'x.svg'},
                                              user=dentro)
        assert values['mimetype'] == 'image/svg+xml'
