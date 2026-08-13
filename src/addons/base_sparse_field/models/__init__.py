from addons.base_sparse_field.models import fields  # noqa: F401
from addons.base_sparse_field.models import sparse_fields_test  # noqa: F401

# `ir_model_fields` NO se importa aquí: cuelga campos y métodos sobre
# `base.IrModelFields` con `add_to_class`/`chain_method`, y en tiempo de import
# el registro de modelos aún no está poblado (`AppRegistryNotReady`). Lo
# importa `apps.py` desde `ready()`, que es cuando ya lo está — mismo criterio
# que `l10n_mx/models/__init__.py`.
