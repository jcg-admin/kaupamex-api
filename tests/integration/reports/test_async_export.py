"""
Tests — Async report export (D-19, DEC-REP-01 superseded by threading job).

UC-REP-05 declares a ``rows > 5000`` branch. There is no Celery/Redis in
the project (DEC-REP-01 alt 1 was blocked on that), so async export follows
the sanctioned no-Celery pattern already used by apps.backups: a job record
model + a threading.Thread worker that generates the file and updates the
record, while the endpoint returns 202 immediately. A status endpoint exposes
the job state and, when DONE, a time-limited signed download URL (~1h,
FR-RPT-04.02 esc 2-4) that streams the file. Only the requesting admin may
read their job / download.

The thread worker (_run_export_job) is exercised synchronously for
determinism, mirroring tests/integration/backups/test_backups.py.
"""
import os

import pytest
from unittest import mock

from django.core import signing

from apps.reports import views as reports_views
from apps.reports.models import ExportJob

pytestmark = pytest.mark.integration

BASE = '/api/v2/admin/reports/'


def _jobs_url(job_id):
    return f'{BASE}export/jobs/{job_id}/'


def _download_url(token):
    return f'{BASE}export/download/{token}/'


class TestAsyncExportTrigger:
    """>threshold returns 202 + job_id and spawns a job (thread mocked)."""

    def test_large_export_returns_202_and_job_id(self, admin_client, db):
        # Force the row count over the async threshold and stop the worker
        # thread from touching the DB/filesystem during the request test.
        with mock.patch.object(reports_views, 'count_export_rows',
                               return_value=reports_views._EXPORT_ASYNC_THRESHOLD + 1), \
                mock.patch.object(reports_views, '_run_export_job'):
            res = admin_client.get(f'{BASE}sales/export/?period=30d&format=csv')
        assert res.status_code == 202, res.content
        body = res.json()
        assert 'job_id' in body
        assert body['status'] == ExportJob.STATUS_PENDING
        job = ExportJob.objects.get(pk=body['job_id'])
        assert job.status == ExportJob.STATUS_PENDING
        assert job.params.get('format') == 'csv'
        assert job.params.get('slug') == 'sales'

    def test_small_export_still_sync_csv(self, admin_client, db):
        # <= threshold keeps the existing synchronous streaming behavior.
        res = admin_client.get(f'{BASE}sales/export/?period=30d&format=csv')
        assert res.status_code == 200
        assert res['Content-Type'].startswith('text/csv')


class TestAsyncExportWorker:
    """_run_export_job executed synchronously transitions the job to DONE."""

    def test_worker_generates_file_and_marks_done(self, db, admin_user):
        job = ExportJob.objects.create(
            requested_by=admin_user,
            params={'slug': 'sales', 'format': 'csv', 'days': 30},
        )
        reports_views._run_export_job(job.pk)
        job.refresh_from_db()
        assert job.status == ExportJob.STATUS_DONE
        assert job.file_path
        assert os.path.exists(job.file_path)
        os.remove(job.file_path)

    def test_worker_marks_error_on_failure(self, db, admin_user):
        job = ExportJob.objects.create(
            requested_by=admin_user,
            params={'slug': 'sales', 'format': 'csv', 'days': 30},
        )
        with mock.patch.object(reports_views, 'build_sales_payload',
                               side_effect=RuntimeError('boom')):
            reports_views._run_export_job(job.pk)
        job.refresh_from_db()
        assert job.status == ExportJob.STATUS_ERROR
        assert 'boom' in job.error_detail


class TestExportJobStatusEndpoint:
    """GET .../export/jobs/<id>/ — status + signed download URL when DONE."""

    def test_status_pending(self, admin_client, db, admin_user):
        job = ExportJob.objects.create(
            requested_by=admin_user,
            params={'slug': 'sales', 'format': 'csv', 'days': 30},
        )
        res = admin_client.get(_jobs_url(job.pk))
        assert res.status_code == 200
        body = res.json()
        assert body['status'] == ExportJob.STATUS_PENDING
        assert body.get('download_url') in (None, '')

    def test_status_done_exposes_working_download_url(self, admin_client, db,
                                                      admin_user):
        job = ExportJob.objects.create(
            requested_by=admin_user,
            params={'slug': 'sales', 'format': 'csv', 'days': 30},
        )
        reports_views._run_export_job(job.pk)
        job.refresh_from_db()
        try:
            res = admin_client.get(_jobs_url(job.pk))
            assert res.status_code == 200
            body = res.json()
            assert body['status'] == ExportJob.STATUS_DONE
            url = body['download_url']
            assert url
            dl = admin_client.get(url)
            assert dl.status_code == 200
            assert dl['Content-Type'].startswith('text/csv')
            content = b''.join(dl.streaming_content) if dl.streaming else dl.content
            assert content  # non-empty file streamed back
        finally:
            if job.file_path and os.path.exists(job.file_path):
                os.remove(job.file_path)

    def test_status_non_owner_forbidden(self, admin_client, db):
        # A different admin owns the job → requesting admin cannot see it.
        User = ExportJob._meta.get_field('requested_by').related_model
        other = User.objects.create_user(
            username='otheradmin', email='other@practicayoruba.mx',
            password='OtherPass123!', is_staff=True,
        )
        job = ExportJob.objects.create(
            requested_by=other,
            params={'slug': 'sales', 'format': 'csv', 'days': 30},
        )
        res = admin_client.get(_jobs_url(job.pk))
        assert res.status_code in (403, 404)

    def test_status_requires_admin(self, auth_client, db, admin_user):
        job = ExportJob.objects.create(
            requested_by=admin_user,
            params={'slug': 'sales', 'format': 'csv', 'days': 30},
        )
        res = auth_client.get(_jobs_url(job.pk))
        assert res.status_code == 403


class TestExportDownloadToken:
    """Download view validates the signed, time-limited token."""

    def test_invalid_token_rejected(self, admin_client, db):
        res = admin_client.get(_download_url('not-a-valid-token'))
        assert res.status_code in (400, 404)

    def test_expired_token_rejected(self, admin_client, db, admin_user):
        job = ExportJob.objects.create(
            requested_by=admin_user,
            params={'slug': 'sales', 'format': 'csv', 'days': 30},
        )
        reports_views._run_export_job(job.pk)
        job.refresh_from_db()
        try:
            token = reports_views._sign_job_token(job.pk)
            # Token older than max_age (1h) must be rejected.
            with mock.patch.object(
                signing.TimestampSigner, 'unsign',
                side_effect=signing.SignatureExpired('expired'),
            ):
                res = admin_client.get(_download_url(token))
            assert res.status_code in (400, 404)
        finally:
            if job.file_path and os.path.exists(job.file_path):
                os.remove(job.file_path)

    def test_download_non_owner_forbidden(self, admin_client, db, admin_user):
        User = ExportJob._meta.get_field('requested_by').related_model
        other = User.objects.create_user(
            username='otheradmin2', email='other2@practicayoruba.mx',
            password='OtherPass123!', is_staff=True,
        )
        job = ExportJob.objects.create(
            requested_by=other,
            params={'slug': 'sales', 'format': 'csv', 'days': 30},
        )
        reports_views._run_export_job(job.pk)
        job.refresh_from_db()
        try:
            token = reports_views._sign_job_token(job.pk)
            res = admin_client.get(_download_url(token))
            assert res.status_code in (403, 404)
        finally:
            if job.file_path and os.path.exists(job.file_path):
                os.remove(job.file_path)
