Investigación de SOLO LECTURA sobre la referencia Odoo 19 Community. No modifiques ningún archivo, no hagas commits, no ejecutes migraciones ni pytest, no escribas en bases de datos.

Referencia: R=/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0 (commit de odoo-tools: ejecuta `git -C /home/user/odoo-tools rev-parse --short HEAD` y cítalo). Usa sólo `git show`, `grep`, `sed -n`, `cat`; nunca `git checkout` dentro de odoo-tools.

Preguntas (responde cada una con archivo:línea y el comando usado):
1. En `$R/addons/account/models/account_journal.py`: los valores exactos de `_name`, `_inherit`, `_description`, `_order`, `_check_company_auto` (si existe) y líneas.
2. Para cada modelo de `_inherit` del diario (espera `portal.mixin`, `mail.thread`, `mail.activity.mixin`, `mail.alias.mixin.optional`; confirma la lista real): archivo donde se define en la referencia (`grep -rn "_name = '<modelo>'" $R/addons $R/odoo/addons`), si es `AbstractModel`, y qué campos y métodos aporta que el diario USE (busca en account_journal.py usos de `alias_`, `message_`, `activity_`, `access_url`, `_compute_access_url`, `_alias_get_creation_values`, `_get_alias_*`). Lista concretamente qué símbolos de cada mixin consume account.journal.
3. Cómo interpreta el ORM de la referencia `_name` + `_inherit` con lista (extensión vs. herencia nueva): cita `$R/odoo/orm/model_classes.py` o `models.py` (busca `_inherit`), con las líneas que deciden si se crea un modelo nuevo que hereda de los mixins.
4. Condiciones de `unlink` / `@api.ondelete` del diario en `account` y en addons que lo extiendan (`grep -rn "_inherit = 'account.journal'\|_inherit = \[\"account.journal\"\|_inherit = \"account.journal\"" $R/addons | head`, y en esos archivos busca `ondelete`/`unlink`).
5. Los consumidores principales de `payment_method_line_id` de account.payment en la referencia: lista archivo:línea de `account_payment.py` donde se lee o escribe.

Entrega: un informe estructurado (markdown) con una sección por pregunta, cada afirmación con su evidencia (comando + salida resumida + archivo:línea). Señala explícitamente lo que no pudiste medir. Máximo ~900 palabras.