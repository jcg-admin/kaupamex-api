# Estilo Python y ubicación de imports

El Python versionado se verifica completo con `make check-style`. No existe
baseline ni allowlist de deuda. Se incluyen código, pruebas, migraciones e
instrumentos y ejecutables con shebang Python, aunque no terminen en `.py`.
`--all` incluye fuentes no versionadas que Git no ignore; `--staged` usa sólo
el contenido y los permisos del índice. Una comprobación del working tree no
acredita que un archivo esté preparado para publicar.

Los modos globales conservan su alcance. El pre-commit admite el incremento
del índice exacto contra HEAD, no una copia diferente del working tree.
GitHub Actions conserva el control global antes del trabajo funcional. `pycodestyle==2.14.0` está fijado en el grupo de desarrollo y en
`uv.lock`. Un fallo conserva un código distinto de cero.
La compilación estática usa una copia temporal y trata `SyntaxWarning` como
error; no importa módulos ni ejecuta cuerpos de instrumentos.

Los imports deben estar en el bloque inicial del módulo, después del
docstring y de `from __future__`, antes de código ejecutable. No se permiten
imports dentro de funciones o clases ni después de definiciones. El control
AST no admite que `noqa` o una supresión del linter oculten esas ubicaciones.
Los bloques de dependencias opcionales (`try` con `ImportError`), anotaciones
(`TYPE_CHECKING`) y plataforma Windows sólo se admiten en ese bloque inicial;
no autorizan imports dentro de funciones ni imports tardíos.

Se aplica el límite de 79 caracteres. W503 no se exige porque PEP 8 recomienda
el salto **antes** del operador binario; no es una excepción por deuda. Las
recomendaciones que no puede comprobar pycodestyle requieren revisión humana.
El control no equivale a aceptación funcional del ORM.

`make ci-verify` ejecuta este gate antes de comprobar la base de datos,
compilar los helpers y ejecutar pytest. Un fallo de estilo impide esas etapas,
también con `make -j`. GitHub utiliza ese mismo target.

Los probes que necesitan modelos inicializados se ejecutan desde el `shell`
de Django, con las conexiones y los recursos autorizados del harness. La
inicialización pertenece al entrypoint, no a un bloque intercalado entre
imports del probe. No se debe sustituir un import por carga dinámica para
eludir la regla.

## Admisión incremental autorizada para commits

`bash scripts/check_python_style.sh --increment --base COMMIT_SHA
--index-tree TREE_SHA --report evidence.json` añade una interfaz explícita de
evaluación. No cambia `--all`, `--staged`, `make check-style` ni
`make ci-verify`. La instrucción de activación autoriza su uso en pre-commit
para publicar commits delimitados en PR pendientes. No autoriza merge ni
aceptación con verificaciones obligatorias fallidas. TASK-API-0478 conserva
la trazabilidad de CI/CD.

Las referencias deben ser SHA completos, no `HEAD` ni abreviaturas. En modo
índice, `COMMIT_SHA` debe coincidir con el HEAD actual y `TREE_SHA` con el árbol
obtenido mediante `git write-tree`. El contenido sin preparar no se evalúa.
Alternativamente, `--candidate COMMIT_SHA` compara un commit descendiente de
la base, sin usar el índice. No se importa ni ejecuta código del candidato.

Se reutilizan pycodestyle 2.14.0, las reglas nativas de imports y compilación
en memoria con SyntaxWarning fatal. La comparación conserva línea, columna,
mensaje, multiplicidad y contexto AST de cada diagnóstico; mover un bloque,
cambiar su cabecera o alterar su unidad lógica invalida la herencia. Las
correspondencias ambiguas fallan cerradas. Archivos nuevos o renombrados se
verifican estrictamente; renombres editados se tratan como baja y alta. Los
ejecutables Python sin extensión también se incluyen. No se siguen symlinks
ni se permite ocultar Python retirando su clasificación.

Cambios de política/verificadores requieren revisión independiente y
cualificación. `--qualify-checkers` ejecuta los controles contractuales
positivos/negativos del candidato exacto, exige correspondencia con el índice
y conserva JUnit y comandos; no acepta una declaración de PASS externa. Sólo
cubre las superficies de admisión aprobadas, nunca workflows o protecciones.
Supresiones reales en fuentes cambiadas se rechazan; las cadenas de fixtures
no pueden ocultar diagnósticos nativos. Se rehúsa la comparación si cambia HEAD, el índice o
un verificador durante el control. El alcance cualificado por archivo se limita
a 4 MiB y 20.000 líneas; excederlo es ERROR, no una exclusión silenciosa.

El JSON conserva revisiones, blobs, comando, hashes de verificadores, resultados
y códigos: 0 admite sólo el incremento; 1 rechaza infracciones introducidas;
2 indica evidencia insuficiente o comparación no cualificada. Las infracciones
heredadas permanecen visibles y pueden conservar style_exit=1 aunque la
admisión sea PASS. Conformidad global, CI, contrato, integración y aceptación
quedan NOT_EVALUATED por este comando, sin sobrescribir sus resultados reales.
No se guarda un baseline ni se modifica automáticamente ningún estado TASK.

El hook fija HEAD y el árbol del índice con Git, llama el modo incremental y
guarda el resultado en el hogar existente de evidencia CI. Los demás gates
permanecen. La conformidad global no se ejecuta por cada commit ni se declara
PASS: permanece consultable mediante make check-style y CI. Para cambios de
verificadores, la cualificación en el hook vincula todos los archivos y
pruebas necesarios al árbol candidato; un desfase falla cerrado.
