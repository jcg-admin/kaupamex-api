"""``ir.attachment`` como recordset — ≙ ``odoo19c:
odoo/addons/base/models/ir_attachment.py`` (``raw``, ``:471``) y su ACL
(``security/ir.model.access.csv:3-4``).

Tres contratos que :class:`~orm.models.BaseModel` le dio al modelo y que
``tools.xml_utils`` consume: la API sobre la clase, ``raw`` como contenido
del archivo y la ACL que el recordset comprueba.
"""

import pytest
from django.contrib.auth import get_user_model

from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.ir_model import IrModelAccess, IrModelData
from addons.base.models.res_groups import ResGroups
from orm.environments import Environment
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 16


@pytest.fixture
def env():
    with Environment(None, SUPERUSER_ID, {}) as environment:
        yield environment


def _user(login):
    return get_user_model().objects.create_user(login=login,
                                                password='Adjunto123!')


def test_the_model_answers_the_recordset_api_on_the_class(env):
    first = env['ir.attachment'].create({'name': 'a.txt', 'raw': b'uno'})
    second = env['ir.attachment'].create({'name': 'b.txt', 'raw': b'dos'})
    found = env['ir.attachment'].search([('name', '=', 'a.txt')])
    assert found == first
    union = env['ir.attachment']
    union |= first
    union |= second
    assert sorted(union.mapped('name')) == ['a.txt', 'b.txt']


def test_raw_is_the_content_of_the_stored_file(env):
    """≙ ``_compute_raw`` / ``_inverse_raw`` (``:266-282``): lo que se escribe
    en ``raw`` es el archivo de ``datas``, y ``save`` deriva de él el tamaño,
    el checksum y el tipo."""
    record = env['ir.attachment'].create({'name': 'probe.bin', 'raw': PNG})
    row = IrAttachment.objects.get(pk=record.id)
    assert row.datas.read() == PNG
    assert row.file_size == len(PNG)
    assert row.mimetype == 'image/png'
    assert record.raw == PNG


def test_only_the_internal_group_may_create_attachments():
    """≙ las dos filas del CSV: ``group_user`` con los cuatro permisos y la
    global en cero. Sin la primera, nadie fuera del superusuario adjunta."""
    data = IrModelData.objects.get(module='base', name='group_user',
                                   model='base.ResGroups')
    internal = _user('adjunto.interno@kaupamex.mx')
    internal.group_ids.add(ResGroups.objects.get(pk=data.res_id))
    outsider = _user('adjunto.fuera@kaupamex.mx')
    label = 'base.IrAttachment'
    assert label in IrModelAccess._get_allowed_models('create', user=internal)
    assert label not in IrModelAccess._get_allowed_models('create',
                                                          user=outsider)
