# Primera construcción del .deb — tarea #966

Fecha: 2026-08-29T02:59:35 · Ubuntu 24.04.4 LTS · debhelper 13.14.1 · lintian 2.117.0

## Resultado

`dpkg-buildpackage -us -uc -b` → exit 0. Produce
`kaupamex-api_0.1.0-1_amd64.deb` (3 479 370 B, 2835 entradas,
Installed-Size 22 594 kB) y su `.ddeb` de símbolos.

Lintian: **0 errores**, 37 avisos (34 `script-not-executable`,
`unusual-interpreter python`, `recursive-privilege-change`,
`initial-upload-closes-no-bugs`).

## Lo que la construcción destapó (H-API-894)

Tres defectos que ninguna lectura del árbol habría mostrado:

1. `Architecture: all` era falso — el paquete lleva dos ELF x86-64.
2. `Build-Depends:` no declaraba la cadena de compilación del motor PDF.
3. `Depends:` declaraba **`libpng16-16`, que no existe en Ubuntu 24.04**.

## Archivos

- `dpkg-buildpackage.log` — la construcción completa.
- `lintian.txt` — la salida del verificador.
- `contenido.txt` — las 2835 entradas del paquete.
- `control-construido.txt` — el control que dpkg-gencontrol emitió.

El `.deb` **no se versiona**: es un artefacto reproducible de 3.5 MB. Se
reconstruye con `dpkg-buildpackage -us -uc -b` desde la raíz del repo.
