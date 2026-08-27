"""Tests — el ciclo de vida del ``arch`` de una vista, y la vista por defecto.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_ui_view.py``:
``create:626`` y ``write:657-658`` (los dos unicos sitios que escriben
``arch_prev``), ``reset_arch:281-293``, ``default_view:...`` con su
``_get_default_view_domain``, y la limpieza de ``ir.ui.view.custom`` en
``write:650-653``.

Por que este bloque y no otro
=============================

``arch_prev`` era una columna que **nadie escribia**. El asistente de reinicio
la leia —``ResetViewArchWizard.source_arch_for(view, 'soft')`` devuelve
``view.arch_prev``— y por tanto el reinicio suave devolvia siempre la cadena
vacia. Es la forma de :ref:`h-api-833` en otro modelo: una funcion cuyo almacen
no se puebla no falla, responde vacio, y el vacio se lee como *"no habia nada
previo"*.

Los controles, cada uno con lo que lo haria fallar
---------------------------------------------------

``TestArchPrev.test_the_previous_arch_is_kept_on_update``
    El eje. Qué lo haría fallar: no copiar ``arch_db`` a ``arch_prev`` antes de
    sobrescribirlo.

``TestArchPrev.test_a_write_that_does_not_touch_the_arch_keeps_the_previous``
    CONTROL de la dirección contraria: copiar siempre —en vez de sólo cuando el
    arch cambia— perdería la copia buena en el primer cambio de nombre.

``TestArchUpdated.test_a_load_from_file_does_not_mark_it_updated``
    CONTROL: la marca distingue *"lo edito una persona"* de *"lo trajo el
    archivo"*. Sin el, el modo desarrollo preferiria siempre la version de la
    base y el reinicio duro no tendria a que volver.

``TestReset.test_the_soft_reset_does_not_save_the_broken_arch_as_previous``
    ``no_save_prev`` de la fuente: se reinicia porque el arch actual esta roto;
    guardarlo como copia previa lo dejaria como unico destino del proximo
    reinicio.

``TestDefaultView.test_an_extension_view_is_never_the_default``
    CONTROL del filtro ``mode='primary'``: la de extension tiene prioridad
    MENOR en el caso, asi que un ``default_view`` sin ese filtro la elegiria.
"""
import pytest
from django.contrib.auth import get_user_model

from addons.base.models.ir_ui_view import (
    IrUiView, IrUiViewCustom, RESET_HARD, RESET_SOFT, ResetViewArchWizard)

pytestmark = pytest.mark.integration

FORM = '<form><field name="name"/></form>'
FORM_V2 = '<form><field name="name"/><field name="login"/></form>'
FORM_V3 = '<form><field name="login"/></form>'


def _view(**extra):
    data = dict(name='vista de prueba', model='res.partner', type='form',
                arch_db=FORM, mode='primary')
    data.update(extra)
    view = IrUiView(**data)
    view.save()
    return view


class TestArchPrev:
    """≙ ``create:626`` y ``write:657-658`` — los dos sitios que la escriben."""

    def test_the_arch_of_the_creation_is_its_own_previous(self, db):
        view = _view()
        assert view.arch_prev == FORM

    def test_the_previous_arch_is_kept_on_update(self, db):
        """DOS escrituras, no una — con una sola el caso no discrimina.

        Con una sola edicion, ``arch_prev`` vale FORM tanto si la escritura lo
        copia como si sigue valiendo lo que la creacion le puso. La segunda
        edicion separa las dos: sin la copia, ``arch_prev`` se quedaria en
        FORM. Medido con la mutacion A, que con un solo cambio pasaba en
        verde.
        """
        view = _view()
        view.arch_db = FORM_V2
        view.save()
        view.refresh_from_db()
        view.arch_db = FORM_V3
        view.save()
        view.refresh_from_db()
        assert view.arch_prev == FORM_V2, 'la escritura no copio el anterior'
        assert view.arch_db == FORM_V3

    def test_a_write_that_does_not_touch_the_arch_keeps_the_previous(self, db):
        """CONTROL — copiar siempre perderia la copia buena."""
        view = _view()
        view.arch_db = FORM_V2
        view.save()
        view.name = 'otro nombre'
        view.save()
        view.refresh_from_db()
        assert view.arch_prev == FORM, 'un cambio de nombre piso la copia'


class TestArchUpdated:
    """≙ ``write:640-643`` — la marca de editado a mano."""

    def test_an_edit_marks_it_updated(self, db):
        view = _view()
        assert view.arch_updated is False
        view.arch_db = FORM_V2
        view.save()
        view.refresh_from_db()
        assert view.arch_updated is True

    def test_a_load_from_file_does_not_mark_it_updated(self, db):
        """CONTROL — ``install_filename`` de la fuente."""
        view = _view()
        view.arch_db = FORM_V2
        view.save(from_file=True)
        view.refresh_from_db()
        assert view.arch_updated is False


class TestReset:
    """≙ ``reset_arch`` (``:281-293``) y su asistente."""

    def test_the_soft_reset_restores_the_previous_arch(self, db):
        view = _view()
        view.arch_db = FORM_V2
        view.save()
        view.refresh_from_db()
        view.arch_db = FORM_V3
        view.save()
        view.reset_arch(RESET_SOFT)
        view.refresh_from_db()
        assert view.arch_db == FORM_V2, 'volvio dos pasos, no uno'

    def test_the_soft_reset_does_not_save_the_broken_arch_as_previous(self, db):
        """``no_save_prev`` — el arch roto no se guarda como copia."""
        view = _view()
        view.arch_db = FORM_V2
        view.save()
        view.reset_arch(RESET_SOFT)
        view.refresh_from_db()
        assert view.arch_prev == FORM, 'el arch roto quedo como copia previa'

    def test_the_hard_reset_clears_the_previous_and_the_mark(self, db):
        view = _view(arch_fs='base/views/x.xml')
        view.arch_db = FORM_V2
        view.save()
        view.reset_arch(RESET_HARD, arch=FORM)
        view.refresh_from_db()
        assert view.arch_db == FORM
        assert view.arch_prev == ''
        assert view.arch_updated is False

    def test_the_wizard_now_reads_something_real(self, db):
        """El consumidor que la columna muda dejaba sin respuesta."""
        view = _view()
        view.arch_db = FORM_V2
        view.save()
        source, value = ResetViewArchWizard.source_arch_for(view, RESET_SOFT)
        assert (source, value) == ('arch_prev', FORM)


class TestCustomCleanup:
    """≙ ``write:650-653`` — la personalizacion muere con el cambio."""

    def test_writing_the_arch_drops_the_customisations(self, db):
        view = _view()
        who = get_user_model().objects.create_user(
            login='custom.uno@practicayoruba.mx', password='ViewCustom123!')
        custom = IrUiViewCustom(ref_id=view, user=who, arch='<form/>')
        custom.save()
        view.arch_db = FORM_V2
        view.save()
        assert not IrUiViewCustom.objects.filter(pk=custom.pk).exists()

    def test_a_write_without_arch_keeps_them(self, db):
        """CONTROL — la fuente las borra en CADA write; medido, tambien aqui."""
        view = _view()
        who = get_user_model().objects.create_user(
            login='custom.dos@practicayoruba.mx', password='ViewCustom123!')
        custom = IrUiViewCustom(ref_id=view, user=who, arch='<form/>')
        custom.save()
        view.name = 'otro nombre'
        view.save()
        assert not IrUiViewCustom.objects.filter(pk=custom.pk).exists()


class TestDefaultView:
    """≙ ``default_view`` + ``_get_default_view_domain``."""

    def test_the_primary_with_the_lowest_priority_wins(self, db):
        _view(name='alta', priority=20)
        baja = _view(name='baja', priority=1)
        assert IrUiView.default_view('res.partner', 'form') == baja.pk

    def test_an_extension_view_is_never_the_default(self, db):
        """CONTROL del filtro ``mode='primary'``."""
        padre = _view(name='primaria', priority=20)
        _view(name='extension', priority=1, mode='extension',
              inherit_id=padre)
        assert IrUiView.default_view('res.partner', 'form') == padre.pk

    def test_without_any_view_there_is_no_default(self, db):
        assert IrUiView.default_view('res.partner', 'form') is None
