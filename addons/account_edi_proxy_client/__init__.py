"""``account_edi_proxy_client`` — vacío a propósito (patrón ``utm/__init__.py``).

La referencia declara aquí ``_create_demo_config_param(env)``, un
``post_init_hook`` que siembra ``account_edi_proxy_client.demo`` en
``ir.config_parameter`` tras instalar el módulo. **Bloqueado**: Django no
tiene un hook post-instalación equivalente a nivel de app (el paralelo más
cercano, una migración de datos con ``RunPython``, es una migración —
``makemigrations``/migraciones nuevas son del orquestador, fuera del
alcance de este agente). Sin este parámetro sembrado, cualquier código que
lo consulte con ``SystemParameter.get_param('account_edi_proxy_client.demo')``
recibe ``None`` en vez de ``'demo'`` — divergencia declarada, no silenciosa.
"""
