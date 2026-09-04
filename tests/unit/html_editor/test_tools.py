"""``html_editor.tools`` — vídeo incrustado e historia divergente."""
import pytest
from django.core.exceptions import ValidationError
from io import BytesIO
from PIL import Image

from addons.html_editor import tools

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestTheFivePlatformsAreRecognised:
    @pytest.mark.parametrize('url, platform, video_id', [
        ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'youtube',
         'dQw4w9WgXcQ'),
        ('https://youtu.be/dQw4w9WgXcQ', 'youtube', 'dQw4w9WgXcQ'),
        ('https://player.vimeo.com/video/123456', 'vimeo', '123456'),
        ('https://www.dailymotion.com/video/x7tgad0', 'dailymotion',
         'x7tgad0'),
        ('https://www.instagram.com/p/ABCdef123/', 'instagram', 'ABCdef123'),
        ('https://www.facebook.com/watch/?v=123456789', 'facebook',
         '123456789'),
    ])
    def test_it_names_the_platform_and_extracts_the_id(self, url, platform,
                                                       video_id):
        source = tools.get_video_source_data(url)
        assert source is not None, url
        assert source[0] == platform
        assert source[1] == video_id

    @pytest.mark.parametrize('url', ['', None, 'no es una url',
                                     'ftp://example.com/x'])
    def test_an_invalid_url_gives_none(self, url):
        assert tools.get_video_source_data(url) is None

    def test_an_invalid_url_produces_the_error_dict_not_an_exception(self):
        data = tools.get_video_url_data('no es una url')
        assert data['error'] is True
        assert data['message']


class TestTheEmbedUrlCarriesThePlaybackRules:
    def test_youtube_autoplay_also_mutes_and_enables_the_js_api(self):
        data = tools.get_video_url_data(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ', autoplay=True)
        assert data['params']['autoplay'] == 1
        assert data['params']['mute'] == 1
        assert data['params']['enablejsapi'] == 1

    def test_youtube_loop_needs_the_playlist_to_be_the_video_itself(self):
        data = tools.get_video_url_data(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ', loop=True)
        assert data['params']['loop'] == 1
        assert data['params']['playlist'] == 'dQw4w9WgXcQ'

    def test_vimeo_always_sets_do_not_track(self):
        data = tools.get_video_url_data(
            'https://player.vimeo.com/video/123456')
        assert data['params']['dnt'] == 1

    def test_the_start_time_of_zero_is_normalised(self):
        data = tools.get_video_url_data(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            start_from='00:00')
        assert data['params']['start'] == '0'

    def test_the_embed_code_is_an_iframe_with_the_embed_url(self):
        code = tools.get_video_embed_code(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        assert '<iframe' in str(code)
        assert 'youtube' in str(code)

    def test_the_embed_code_of_an_invalid_url_is_none(self):
        assert tools.get_video_embed_code('no es una url') is None


class TestTheImageProcessSeam:
    """``image_process`` se construyó aquí (divergencia 2 del módulo)."""

    def test_content_that_is_not_an_image_gives_none(self):
        assert tools._image_process(b'no soy una imagen') is None

    def test_a_real_png_survives_the_round_trip(self):

        buf = BytesIO()
        Image.new('RGB', (2, 2), 'red').save(buf, 'PNG')
        out = tools._image_process(buf.getvalue())
        assert out is not None
        assert Image.open(BytesIO(out)).size == (2, 2)


class _Record:
    """Doble de registro: lo que ``handle_history_divergence`` consulta."""

    _name = 'html_editor.converter.test'

    def __init__(self, pk=7, stored=''):
        self.pk = pk
        self._stored = stored

    def __getattr__(self, name):
        if name == 'html':
            return self._stored
        raise AttributeError(name)


class TestTheDivergenceGuard:
    """La guarda que impide pisar en silencio lo que otro acaba de guardar."""

    def test_a_field_absent_from_the_values_is_left_alone(self):
        vals = {'otro': 'x'}
        tools.handle_history_divergence(_Record(), 'html', vals)
        assert vals == {'otro': 'x'}

    def test_during_module_installation_it_does_nothing(self):
        vals = {'html': '<p data-last-history-steps="1,2">x</p>'}
        before = dict(vals)
        tools.handle_history_divergence(_Record(), 'html', vals,
                                        install_module=True)
        assert vals == before

    def test_without_incoming_history_it_only_notifies(self):
        vals = {'html': '<p>sin historia</p>'}
        tools.handle_history_divergence(_Record(), 'html', vals)
        assert vals['html'] == '<p>sin historia</p>'

    def test_the_stored_value_keeps_only_the_last_step_id(self):
        vals = {'html': '<p data-last-history-steps="1,2,3">x</p>'}
        tools.handle_history_divergence(_Record(), 'html', vals)
        assert vals['html'] == '<p data-last-history-steps="3">x</p>'

    def test_a_history_that_does_not_contain_the_server_one_is_rejected(self):
        """El caso por el que existe la guarda.

        El servidor tiene el paso ``9``; el cliente llega con una historia que
        no lo contiene, así que editó desde una copia anterior. Guardar
        borraría lo del otro **sin avisar a nadie**.
        """
        record = _Record(stored='<p data-last-history-steps="8,9">servidor</p>')
        vals = {'html': '<p data-last-history-steps="1,2">cliente</p>'}
        with pytest.raises(ValidationError):
            tools.handle_history_divergence(record, 'html', vals)

    def test_a_history_that_does_contain_it_is_accepted(self):
        record = _Record(stored='<p data-last-history-steps="8,9">servidor</p>')
        vals = {'html': '<p data-last-history-steps="9,10">cliente</p>'}
        tools.handle_history_divergence(record, 'html', vals)
        assert vals['html'] == '<p data-last-history-steps="10">cliente</p>'

    def test_an_old_document_without_the_attribute_is_not_checked(self):
        # La fuente lo dice: "Do not check old documents without
        # data-last-history-steps".
        record = _Record(stored='<p>documento viejo</p>')
        vals = {'html': '<p data-last-history-steps="1">cliente</p>'}
        tools.handle_history_divergence(record, 'html', vals)
        assert vals['html'] == '<p data-last-history-steps="1">cliente</p>'
