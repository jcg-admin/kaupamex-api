"""Controles independientes en memoria: Consumer, diagnóstico, bucket y clave."""
import ast
import inspect
import subprocess
import sys
import textwrap
import django
import pytest

django.setup()
from orm import fields as field_module, environments, registry
from django.apps import apps

model = apps.get_model('base', 'ResGroups')
mode = sys.argv[1]
base = 'tests/unit/orm/test_res_groups_compute_contract.py'
if mode == 'consumer':
    source = subprocess.check_output(['git', 'show', 'b1b6f59b:src/addons/base/models/res_groups.py'], text=True)
    cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'ResGroups')
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_compute_full_name')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<old Consumer>', 'exec'), vars(sys.modules[model.__module__]), namespace)
    model._compute_full_name = namespace['_compute_full_name']
    selected = [base+'::test_compute_assigns_instead_of_returning', base+'::test_first_and_second_reads_compute_once']
elif mode in ('diagnostic', 'instance-cache'):
    source = textwrap.dedent(inspect.getsource(field_module.FieldDescriptor.__get__))
    if mode == 'diagnostic':
        source = source.replace("f'{instance._meta.label}({record_id!r},).{field.name}'", "f'{instance}.{field.name}'")
        selected = [base+'::test_return_without_assignment_raises_without_recursive_label']
    else:
        source = source.replace(' and not contextual_compute:', ':')
        selected = [base+'::test_context_buckets_do_not_reuse_the_instance_label']
    namespace = {}
    exec(compile(source, '<single descriptor mutation>', 'exec'), vars(field_module), namespace)
    field_module.FieldDescriptor.__get__ = namespace['__get__']
elif mode == 'context-key':
    source = textwrap.dedent(inspect.getsource(environments.Environment.cache_key))
    source = source.replace('self.registry.field_depends_context[field]', '(field._depends_context or ())')
    namespace = {}
    exec(compile(source, '<old context key>', 'exec'), vars(environments), namespace)
    environments.Environment.cache_key = namespace['cache_key']
    selected = [base+'::test_cache_key_uses_dependencies_derived_from_the_compute']
else:
    raise ValueError(mode)
registry.field_depends_context.clear()
print('Negative control in memory only:', mode, flush=True)
raise SystemExit(pytest.main(['--confcutdir=tests/unit/orm','-o','addopts=','--tb=short','-q',*selected]))
