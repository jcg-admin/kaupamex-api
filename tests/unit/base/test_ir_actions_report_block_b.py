"""Bloque B de ``ir.actions.report``: resolución de reportes y adjuntos.

Los doce símbolos que la fuente declara entre ``associated_view`` y
``_prepare_local_attachments``, portados con su nombre y su firma en el pase
de la tarea #170. Cada uno se mide contra lo que la referencia declara, no
contra lo que el porte anterior hacía.

Cuatro de ellos dependían de mecanismos que no existían y que este pase
construyó: el evaluador general (``tools.safe_eval``, tarea #140),
``get_base_url`` (``orm.models.BaseUrlMixin``), ``_for_xml_id`` /
``_get_action_dict`` (``IrActionsBase``) y los dos de origen remoto de
``IrAttachment``. Declararlos como divergencia era el camino barato.
"""
import inspect

import pytest

from addons.base.models.ir_actions_report import IrActionsReport
from addons.base.models.ir_attachment import IrAttachment
from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.report_paperformat import ReportPaperformat
from orm import registry
from exceptions import ValidationError

pytestmark = pytest.mark.django_db


def _report(**fields):
    fields.setdefault('name', 'Reporte')
    fields.setdefault('model', 'res.partner')
    fields.setdefault('report_name', 'base.report_x')
    fields.setdefault('report_type', 'qweb-pdf')
    return IrActionsReport.objects.create(**fields)


class TestTheAttachmentIsResolvedByEvaluatingItsExpression:
    """``retrieve_attachment`` — la mitad que antes no se portaba."""

    def test_the_stored_expression_names_the_attachment(self):
        report = _report(attachment="'INV_%s.pdf' % object.name")
        partner = IrAttachment.objects.create(
            name='INV_ACME.pdf', res_model='res.partner', res_id=7)
        found = report.retrieve_attachment(_Record(pk=7, name='ACME'))
        assert found == partner

    def test_the_conditional_expression_of_the_reference_branches_both_ways(
            self):
        """La forma canónica del campo, medida en sus DOS ramas.

        Con una sola rama el caso no discriminaba: anulando el evaluador, el
        texto crudo tampoco encuentra adjunto y el ``None`` sale igual. La
        rama que sí lo distingue es la que **encuentra** algo, porque exige
        que la expresión se haya evaluado de verdad.
        """
        expression = ("(object.state in ('open', 'paid')) and "
                      "((object.name or 'Invoice').replace('/', '') + '.pdf')")
        report = _report(attachment=expression)

        paid = IrAttachment.objects.create(
            name='INV2026001.pdf', res_model='res.partner', res_id=3)
        assert report.retrieve_attachment(
            _Record(pk=3, name='INV/2026/001', state='paid')) == paid

        assert report.retrieve_attachment(
            _Record(pk=1, name='INV/1', state='draft')) is None

    def test_without_expression_there_is_nothing_to_look_for(self):
        assert _report(attachment='').retrieve_attachment(
            _Record(pk=1, name='x')) is None

    def test_the_expression_runs_under_the_same_guards_as_anywhere_else(self):
        # Control de que el evaluador es el acotado y no un `eval` pelado.
        report = _report(attachment="object.__class__")
        with pytest.raises(NameError, match='forbidden name'):
            report.retrieve_attachment(_Record(pk=1, name='x'))

    def test_it_does_not_find_an_attachment_of_another_record(self):
        report = _report(attachment="'FIJO.pdf'")
        IrAttachment.objects.create(
            name='FIJO.pdf', res_model='res.partner', res_id=99)
        assert report.retrieve_attachment(_Record(pk=7, name='x')) is None


class TestThePaperFormat:
    """``get_paperformat`` y ``get_paperformat_by_xmlid``."""

    def test_the_one_of_the_report_wins(self):
        formato = ReportPaperformat.objects.create(name='A4 propio')
        report = _report(paperformat_id=formato)
        assert report.get_paperformat() == formato

    def test_without_one_of_its_own_it_falls_back_to_the_company(self):
        # Sin compañía activa la cadena termina en None, que es la forma que
        # toma aquí el `env.company.paperformat_id` de la fuente cuando no hay
        # compañía. Lo que se mide es que NO revienta y no inventa un formato.
        assert _report().get_paperformat() is None

    def test_the_signature_no_longer_takes_a_company(self):
        # El `company=None` era nuestro y su nota era falsa: la compañía
        # activa se lee del entorno. La firma es la de la fuente.
        firma = inspect.signature(IrActionsReport.get_paperformat)
        assert list(firma.parameters) == ['self']

    def test_an_empty_xmlid_falls_back_to_the_company(self):
        assert _report().get_paperformat_by_xmlid('') is None


class TestTheLayoutAndTheUrl:
    """``_get_layout`` y ``_get_report_url``."""

    def test_an_unseeded_layout_resolves_to_none_without_raising(self):
        assert _report()._get_layout() is None

    def test_the_parameter_wins_over_the_base_url(self):
        SystemParameter.objects.create(key='report.url',
                                       value='https://reports.example')
        registry.clear_cache('stable')
        assert _report()._get_report_url() == 'https://reports.example'

    def test_without_the_parameter_it_falls_back_to_the_base_url(self):
        SystemParameter.objects.create(key='web.base.url',
                                       value='https://base.example')
        registry.clear_cache('stable')
        assert _report()._get_report_url() == 'https://base.example'

    def test_get_base_url_reaches_every_model_not_just_this_one(self):
        # `get_base_url` cuelga de BaseModel en la fuente: si aquí sólo lo
        # tuviera el reporte, el porte seria del metodo y no del mecanismo.
        SystemParameter.objects.create(key='web.base.url', value='https://x')
        registry.clear_cache('stable')
        assert IrAttachment(name='a').get_base_url() == 'https://x'


class TestResolvingAReportFromAReference:
    """``_get_report_from_name`` y ``_get_report``, con sus cuatro ramas."""

    def test_the_underscore_came_back(self):
        # Sin él el símbolo quedaba promovido a API pública.
        assert hasattr(IrActionsReport, '_get_report_from_name')
        assert not hasattr(IrActionsReport, 'get_report_from_name')

    def test_it_finds_the_report_by_its_template_name(self):
        report = _report(report_name='base.uno')
        assert IrActionsReport._get_report_from_name('base.uno') == report

    def test_an_integer_reference_is_a_primary_key(self):
        report = _report()
        assert IrActionsReport._get_report(report.pk) == report

    def test_a_record_reference_comes_back_as_itself(self):
        report = _report()
        assert IrActionsReport._get_report(report) == report

    def test_a_record_of_another_model_is_refused_by_type(self):
        other = IrAttachment.objects.create(name='no soy un reporte')
        with pytest.raises(ValueError, match='Expected report of type'):
            IrActionsReport._get_report(other)

    def test_a_string_reference_falls_back_to_the_template_name(self):
        report = _report(report_name='base.dos')
        assert IrActionsReport._get_report('base.dos') == report

    def test_a_reference_that_resolves_to_nothing_raises(self):
        with pytest.raises(ValueError, match='report not found'):
            IrActionsReport._get_report('base.no_existe')


class TestTheReportsWhoseDomainAcceptsARecord:
    """``get_valid_action_reports`` — el porte, no el filtro por grupos."""

    def test_a_report_without_a_domain_is_always_valid(self):
        report = _report(model='res.partner', domain='')
        assert report.pk in IrActionsReport.get_valid_action_reports(
            'res.partner', [])

    def test_a_report_with_a_domain_no_record_satisfies_is_left_out(self):
        report = _report(model='res.partner',
                         domain="[('name', '=', 'no existe nadie asi')]")
        assert report.pk not in IrActionsReport.get_valid_action_reports(
            'res.partner', [])

    def test_the_signature_is_the_one_of_the_reference(self):
        firma = inspect.signature(IrActionsReport.get_valid_action_reports)
        assert list(firma.parameters) == ['model', 'record_ids']

    def test_it_is_a_different_method_from_the_group_filter(self):
        # `valid_reports_for` filtra por `group_ids` y es NUESTRO; hasta este
        # pase su docstring lo presentaba como el porte de aquél.
        assert IrActionsReport.get_valid_action_reports is not \
            IrActionsReport.valid_reports_for
        assert '**Nuestro.**' in IrActionsReport.valid_reports_for.__doc__


class TestTheRemoteAttachmentsAreBroughtLocal:
    """``_prepare_local_attachments`` y los dos métodos que consume."""

    def test_a_remote_attachment_is_recognised_by_its_three_marks(self):
        remoto = IrAttachment(url='https://x/y.png', file_size=0)
        assert remoto._is_remote_source()

    @pytest.mark.parametrize('url,file_size', [
        ('', 0),                       # sin url
        ('https://x/y.png', 4096),     # ya bajado
        ('data:image/png;base64,AA', 0),  # esquema que no se va a buscar
    ])
    def test_each_of_the_three_marks_is_necessary(self, url, file_size):
        assert not IrAttachment(url=url, file_size=file_size)._is_remote_source()

    def test_migrating_a_binary_attachment_is_a_no_op(self):
        assert IrAttachment(type='binary')._migrate_remote_to_local() is None

    def test_migrating_a_url_attachment_is_refused(self):
        with pytest.raises(ValidationError, match='migrated to local'):
            IrAttachment(url='https://x', type='url')._migrate_remote_to_local()

    def test_it_keeps_the_local_ones_and_drops_the_remote_it_cannot_migrate(
            self):
        local = IrAttachment.objects.create(name='local', file_size=10)
        remoto = IrAttachment.objects.create(
            name='remoto', url='https://x/y', file_size=0, type='url')
        quedan = IrActionsReport._prepare_local_attachments([local, remoto])
        assert quedan == [local]

    def test_the_failure_to_migrate_does_not_stop_the_rest(self):
        # El `except` de la fuente registra y sigue: un adjunto que no se
        # puede migrar no debe tumbar el dibujado de los demás.
        roto = IrAttachment.objects.create(
            name='roto', url='https://x/y', file_size=0, type='url')
        local = IrAttachment.objects.create(name='ok', file_size=1)
        assert IrActionsReport._prepare_local_attachments(
            [roto, local, roto]) == [local]


class TestTheActionForTheClient:
    """``report_action`` y ``_action_configure_external_report_layout``."""

    def test_it_carries_the_four_fields_of_the_report(self):
        report = _report(report_file='base.archivo')
        action = report.report_action([], config=False)
        assert action['type'] == 'ir.actions.report'
        assert action['report_name'] == report.report_name
        assert action['report_type'] == report.report_type
        assert action['report_file'] == report.report_file
        assert action['name'] == report.name

    @pytest.mark.parametrize('docids,esperados', [
        (7, [7]),
        ([1, 2], [1, 2]),
    ])
    def test_the_records_to_print_land_in_the_active_ids(self, docids,
                                                         esperados):
        action = _report().report_action(docids, config=False)
        assert action['context']['active_ids'] == esperados

    def test_without_records_the_context_carries_no_active_ids(self):
        action = _report().report_action([], config=False)
        assert 'active_ids' not in action['context']

    def test_the_data_travels_verbatim(self):
        action = _report().report_action([], data={'k': 'v'}, config=False)
        assert action['data'] == {'k': 'v'}


class TestTheAssociatedView:
    """``associated_view`` — sus dos guardas de la fuente."""

    def test_without_a_seeded_action_it_returns_false(self):
        assert _report().associated_view() is False

    def test_a_report_name_without_a_dot_returns_false(self):
        # La segunda guarda: `len(report_name.split('.')) < 2`.
        assert _report(report_name='sinpunto').associated_view() is False


class _Record:
    """Doble de registro para las expresiones de ``attachment``."""

    def __init__(self, **fields):
        self.__dict__.update(fields)
