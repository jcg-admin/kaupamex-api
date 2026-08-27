"""El rastro de auditoría restringido, ahora operable — tarea #611.

Adaptación de ``addons/account/tests/test_audit_trail.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3).

**Por qué este archivo no existía antes.** ``addons/account/models/mail_message.py``
portó la guarda completa y quedó **inerte**: ``restrictive_audit_trail`` y
``posted_before`` no existían, así que ``account_audit_log_restricted`` devolvía
siempre ``False`` y no había nada que ejercitar. Los dos campos aterrizaron en
este pase, y estos casos son lo que lo demuestra: cada uno falla si se retira
uno de los dos.

**Qué se adapta y qué no.** La referencia ejercita cinco casos de borrado
(``test_can_unlink_draft``, ``test_cant_unlink_posted``, ``test_cant_unlink_message``,
``test_cant_unown_message``, ``test_cant_unlink_tracking_value``) más el contenido
del preview. Aquí se cubren los que la guarda portada realmente decide —
``_except_audit_log`` y el ``save()`` de ``MailMessage``— más la restricción de
empresa que la fuente declara ``@api.constrains``. Los de ``tracking_value_ids``
quedan fuera: ese modelo tiene su propia guarda en la referencia
(``mail_tracking_value.py``), que es otro archivo y otro porte.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from addons.account.models import (
    AccountAccount,
    AccountJournal,
    AccountMove,
    AccountMoveLine,
)
from addons.base.models import ResCompany
from addons.mail.models import MailMessage
from exceptions import UserError, ValidationError


@pytest.fixture
def company(db):
    return ResCompany.objects.create(code='audit', name='Audit Trail SA')


@pytest.fixture
def setup(db, company):
    journal = AccountJournal.objects.create(
        name='Ventas', code='AUD', type='sale', company=company)
    income = AccountAccount.objects.create(
        code='401', name='Ventas', account_type='income', company=company)
    return company, journal, income


def _balanced_move(company, journal, account):
    """Un asiento balanceado, listo para ``post()`` — ≙ ``create_move`` (:24-37)."""
    move = AccountMove.objects.create(
        move_type='out_invoice', date=timezone.now().date(),
        journal=journal, company=company)
    AccountMoveLine.objects.create(
        move=move, account=account, balance=Decimal('100.00'))
    AccountMoveLine.objects.create(
        move=move, account=account, balance=Decimal('-100.00'))
    return move


def _chatter_message(move):
    """El mensaje del chatter que documenta ese asiento."""
    return MailMessage.objects.create(
        model='account.move', res_id=move.pk,
        message_type='notification', body='<p>asiento creado</p>')


def test_posted_before_starts_false(setup):
    """Un asiento recién creado nunca estuvo publicado."""
    company, journal, income = setup
    move = _balanced_move(company, journal, income)
    assert move.posted_before is False


def test_post_marks_posted_before(setup):
    """``post()`` lo pone en el mismo write que ``state`` — ≙ ``odoo19c:
    account_move.py:5714-5717``."""
    company, journal, income = setup
    move = _balanced_move(company, journal, income)
    move.post()
    move.refresh_from_db()
    assert move.state == 'posted'
    assert move.posted_before is True


def test_posted_before_never_goes_back_to_false(setup):
    """Volver a borrador NO desmarca ``posted_before`` — es lo que distingue un
    borrador que nunca existió contablemente de uno que sí."""
    company, journal, income = setup
    move = _balanced_move(company, journal, income)
    move.post()
    move.state = 'draft'
    move.save(update_fields=['state'])
    move.refresh_from_db()
    assert move.state == 'draft'
    assert move.posted_before is True


def test_can_unlink_draft_message(setup):
    """≙ ``test_can_unlink_draft`` (:51-53). Con el rastro activo pero el
    asiento nunca publicado, el borrado se permite."""
    company, journal, income = setup
    company.restrictive_audit_trail = True
    company.save(update_fields=['restrictive_audit_trail'])
    message = _chatter_message(_balanced_move(company, journal, income))

    message._except_audit_log()   # no levanta


def test_cannot_unlink_posted_message(setup):
    """≙ ``test_cant_unlink_posted`` (:55-60) y ``test_cant_unlink_message``
    (:62-68). Publicado + rastro activo → la guarda levanta."""
    company, journal, income = setup
    company.restrictive_audit_trail = True
    company.save(update_fields=['restrictive_audit_trail'])
    move = _balanced_move(company, journal, income)
    move.post()
    message = _chatter_message(move)

    with pytest.raises(UserError, match='rastro de auditoría'):
        message._except_audit_log()


def test_without_restrictive_trail_nothing_is_blocked(setup):
    """El interruptor apagado deja pasar aunque el asiento esté publicado —
    es el ``setUpClass`` de la referencia (``restrictive_audit_trail = False``,
    :21) y la razón de que el resto de la suite de account no se vea afectada."""
    company, journal, income = setup
    assert company.restrictive_audit_trail is False
    move = _balanced_move(company, journal, income)
    move.post()
    message = _chatter_message(move)

    message._except_audit_log()   # no levanta


def test_cannot_unown_posted_message(setup):
    """≙ ``test_cant_unown_message`` (:70-76). Mutar ``res_id`` para sacar el
    mensaje del asiento es la misma evasión que borrarlo."""
    company, journal, income = setup
    company.restrictive_audit_trail = True
    company.save(update_fields=['restrictive_audit_trail'])
    move = _balanced_move(company, journal, income)
    move.post()
    message = _chatter_message(move)

    message.res_id = 0
    with pytest.raises(UserError, match='rastro de auditoría'):
        message.save()


def test_restrictive_audit_trail_can_be_turned_off(setup):
    """``force_restrictive_audit_trail`` devuelve False para toda empresa
    (``odoo19c: company.py:347-349``), así que apagar el rastro se permite."""
    company, journal, income = setup
    company.restrictive_audit_trail = True
    company.save(update_fields=['restrictive_audit_trail'])

    company.restrictive_audit_trail = False
    company.save(update_fields=['restrictive_audit_trail'])   # no levanta

    company.refresh_from_db()
    assert company.restrictive_audit_trail is False


def test_localization_forcing_the_trail_blocks_turning_it_off(setup, monkeypatch):
    """≙ ``_check_audit_trail_restriction`` (``odoo19c: company.py:319-322``).

    El gancho existe **para que una localización lo redefina**; ninguna lo hace
    hoy (medido: 0 hits de ``force_restrictive_audit_trail`` en
    ``addons/l10n_mx/``). Se simula esa redefinición para ejercitar la rama que
    de otro modo sería inalcanzable — el mismo criterio con que la referencia
    prueba una restricción que su propio árbol no dispara.
    """
    company, journal, income = setup
    monkeypatch.setattr(
        ResCompany, 'force_restrictive_audit_trail', property(lambda self: True))

    company.restrictive_audit_trail = False
    with pytest.raises(ValidationError, match='localización'):
        company.save(update_fields=['restrictive_audit_trail'])
