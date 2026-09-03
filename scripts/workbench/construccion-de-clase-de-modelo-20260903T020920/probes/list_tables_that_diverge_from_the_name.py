import django; django.setup()
from orm import registry
for name, cls in registry.MODELS_BY_NAME.items():
    esperado = name.replace('.', '_')
    real = getattr(cls, '_table', None)
    if real != esperado:
        print(f'{name}: _table={real!r} esperado={esperado!r} '
              f'db_table={cls._meta.db_table!r} '
              f'declara_table={"_table" in cls.__dict__}')
