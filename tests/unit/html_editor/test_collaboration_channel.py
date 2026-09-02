"""``models/ir_websocket`` — la guarda de acceso del canal de coedición.

Es la superficie de **seguridad** de este addon: el canal
``editor_collaboration:<modelo>:<campo>:<id>`` transporta el contenido del
campo, así que suscribirse a él sin poder leer el registro es leerlo.

Los casos de abajo están escritos para **poder fallar** cuando la guarda
desaparece (sub-patrón D de ``metrica-decide-la-conclusion.md``): apuntan a un
registro que **existe** y a un campo que **existe**, para que el rechazo lo
produzca la guarda y no la ausencia del objeto. La evidencia de esa medición
—con la guarda anulada a mano— vive en
``scripts/evidence/neutering-html-editor-collaboration-channel-*.txt``.
"""
import pytest
from addons.bus.models import ir_websocket as bus_ws
from django.db import DEFAULT_DB_ALIAS
from orm.environments import user_scope

from addons.html_editor.models.ir_websocket import (
    EDITOR_COLLABORATION,
    EDITOR_COLLABORATION_CHANNEL_REGEX,
    editor_collaboration_channel,
)
from addons.html_editor.models.test_models import Html_EditorConverterTest

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def record(db):
    """Un registro **que existe** y con un campo HTML **que existe**."""
    return Html_EditorConverterTest.objects.create(html='<p>secreto</p>')


@pytest.fixture
def actor(db):
    from addons.base.models import ResUsers
    return ResUsers.objects.create_user(login='html-editor-probe@kaupamex.test')


class TestTheChannelIsComposedInOnePlace:
    def test_the_string_carries_the_five_parts_of_the_source_tuple(self):
        channel = editor_collaboration_channel('res.partner', 'comment', 42)
        assert channel == '%s:%s:res.partner:comment:42' % (
            DEFAULT_DB_ALIAS, EDITOR_COLLABORATION)

    def test_the_res_id_is_normalised_to_an_integer(self):
        assert editor_collaboration_channel('a.b', 'c', '42').endswith(':42')

    def test_the_pattern_is_the_one_of_the_source(self):
        import re
        match = re.match(EDITOR_COLLABORATION_CHANNEL_REGEX,
                         'editor_collaboration:res.partner.bank:comment:9')
        assert match is not None
        assert match[1] == 'res.partner.bank'
        assert match[2] == 'comment'
        assert match[3] == '9'


class TestTheGuardOnlyAddsWhatTheActorCanReadAndWrite:
    """Los cinco desenlaces del recorrido de la fuente."""

    def _channels(self, asked, user=None):
        return bus_ws.build_bus_channel_list(
            list(asked), user=user, authenticated=user is not None)

    def test_without_an_actor_no_collaboration_channel_is_added(self, record):
        asked = ['editor_collaboration:html_editor.converter.test:html:%d'
                 % record.pk]
        out = self._channels(asked)
        assert not [c for c in out if c.startswith(DEFAULT_DB_ALIAS + ':')]

    def test_an_unknown_model_is_discarded_in_silence(self, actor):
        with user_scope(actor.pk):
            out = self._channels(
                ['editor_collaboration:no.existe.este.modelo:html:1'],
                user=actor)
        assert not [c for c in out if c.startswith(DEFAULT_DB_ALIAS + ':')]

    def test_an_existing_model_with_a_missing_row_is_discarded(self, actor):
        # El modelo existe; la fila no. La fuente hace `continue`.
        with user_scope(actor.pk):
            out = self._channels(
                ['editor_collaboration:html_editor.converter.test:html:999999'],
                user=actor)
        assert not [c for c in out if c.startswith(DEFAULT_DB_ALIAS + ':')]

    def test_a_channel_that_is_not_a_collaboration_one_passes_through(self,
                                                                      actor):
        with user_scope(actor.pk):
            out = self._channels(['un_canal_cualquiera'], user=actor)
        assert 'un_canal_cualquiera' in out

    def test_the_broadcast_channel_is_always_there(self, actor):
        with user_scope(actor.pk):
            out = self._channels([], user=actor)
        assert bus_ws.BROADCAST_CHANNEL in out

    def test_the_asked_channels_are_never_lost(self, actor, record):
        asked = ['propio_1', 'propio_2']
        with user_scope(actor.pk):
            out = self._channels(asked, user=actor)
        assert set(asked) <= set(out)


class TestTheGuardIsWhatDecides:
    """El control que discrimina — el que cae si la guarda se retira.

    ``check_access`` sobre un registro que **existe**, con un campo que
    **existe** y un actor que **existe**. Si el confinamiento desapareciera,
    este caso pasaría a añadir el canal, y por eso su aserción es sobre la
    ausencia del canal y no sobre la ausencia del registro.
    """

    def test_an_actor_without_access_does_not_get_the_channel(self, actor,
                                                              record):
        channel = editor_collaboration_channel(
            'html_editor.converter.test', 'html', record.pk)
        with user_scope(actor.pk):
            out = bus_ws.build_bus_channel_list(
                ['editor_collaboration:html_editor.converter.test:html:%d'
                 % record.pk],
                user=actor, authenticated=True)
        assert channel not in out, (
            'la guarda de acceso no rechazó el canal: si este caso pasa a '
            'fallar, es que el confinamiento de `_build_bus_channel_list` '
            'dejó de decidir')
