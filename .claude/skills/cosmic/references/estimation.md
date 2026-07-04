# Estimación temprana (early sizing)

> Cuando los FUR no tienen granularidad para identificar cada movimiento. NO fuerces una
> medición parcial: estima y marca `[ESTIMACIÓN TEMPRANA]`. Fuente:
> [manual/early-sizing-practitioners-guide.md](manual/early-sizing-practitioners-guide.md) +
> tutoriales [M1](manual/tutorial-early-sizing-m1-techniques.md)/[M2](manual/tutorial-early-sizing-m2-selection.md)/[M3](manual/tutorial-early-sizing-m3-nfr.md).

## Técnicas (elegir según detalle disponible — M2 selección)

| Técnica | Cuándo | Cómo |
|---------|--------|------|
| **Average Functional Process** | conoces nº de procesos funcionales, no sus movimientos | nº procesos × CFP promedio (calibrado) |
| **Equal-size bands** | puedes clasificar procesos por tamaño | clasificar en Small/Medium/Large y aplicar CFP de banda |
| **Analogía** | hay un sistema/medición previa parecida | escalar desde el análogo |
| **Fixed-size / scaled** | muy poco detalle | rangos amplios documentando incertidumbre |

## Benchmarks genéricos (ilustrativos — calibrar)

`cosmices` (manual): Small ≈ 3.9 CFP, Medium ≈ 6.9 CFP (referenciales). **Calibra con tus datos**
(ver [calibration.md](calibration.md)). Toda estimación es **SPECULATIVE** hasta medición real (I-012).

## NFR

Los requisitos no funcionales **no aportan CFP**, pero afectan esfuerzo. Tratamiento:
[manual/tutorial-early-sizing-m3-nfr.md](manual/tutorial-early-sizing-m3-nfr.md).

---
**Última actualización:** 2026-06-03T03:44:23Z
