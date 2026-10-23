"""La referencia a res_users debe quedar dentro del grafo de migraciones Django."""
from django.conf import settings
from django.db.migrations.loader import MigrationLoader


def test_testorm_follows_the_user_table_migration():
    loader = MigrationLoader(None)
    assert 'test_orm' in loader.migrated_apps
    plan = loader.graph.forwards_plan(('test_orm', '0001_initial'))
    user_app = settings.AUTH_USER_MODEL.split('.')[0]
    assert plan.index((user_app, '0001_initial')) < plan.index(('test_orm', '0001_initial'))
    state = loader.project_state([('test_orm', '0001_initial')])
    discussion = state.apps.get_model('test_orm', 'TestOrmDiscussion')
    field = discussion._meta.get_field('moderator')
    assert field.remote_field.model._meta.db_table == 'res_users'
    assert field.db_constraint
