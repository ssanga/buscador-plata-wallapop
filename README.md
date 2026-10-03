# Buscador de plata en Wallapop

Descarga cada noche los anuncios de monedas de plata de Wallapop, descarta réplicas, estima
cuántos gramos de plata fina tiene cada anuncio y los ordena según lo que pagas **respecto al
valor de la plata que contienen**. Una web local muestra los rankings.

```
Programador de tareas (03:30) ─► main.py batch ─► SQLite (data/plata.db) ◄─ main.py web (Flask)
                                   │  ├─ API de búsqueda de Wallapop (19 búsquedas, categoría Coleccionismo)
                                   │  ├─ precio spot: gold-api.com + frankfurter.dev (gratis, sin clave)
                                   │  └─ analyzer: réplicas, peso, ley, lotes
```

## Puesta en marcha

```powershell
pip install -r requirements.txt
python main.py batch                  # primera carga (unos minutos)
python main.py web                    # http://127.0.0.1:5000
powershell -ExecutionPolicy Bypass -File scripts\programar_tarea.ps1   # ejecución diaria a las 03:30
```

Otros comandos:

| Comando | Para qué |
|---|---|
| `python main.py batch --max-pages 3` | prueba rápida |
| `python main.py batch --reanalyze` | recalcula el análisis de lo ya guardado (tras tocar `analyzer.py`) sin volver a descargar |
| `python -m pytest` | tests del analizador |

## La web

| Pestaña | Contenido |
|---|---|
| **Mejor €/g de plata** | El ranking principal: ordenado por sobreprecio sobre el valor de fundición. `-40 %` significa que pagas un 40 % menos de lo que vale la plata. |
| **Más baratas** | Precio absoluto, sin réplicas ni accesorios. |
| **Nuevos hoy** | Aparecidos en la última ejecución. |
| **Bajadas de precio** | El vendedor ha rebajado desde la última vez. |
| **Demasiado buenos** | Más de un 70 % por debajo del valor de la plata: casi siempre precio por unidad de un lote, réplica no declarada o peso mal leído. Conviene echarles un vistazo de vez en cuando. |
| **Descartados** | Los que has ocultado con «descartar» (no vuelven a salir aunque sigan publicados). |

También hay un endpoint JSON: `/api/ranking?view=oportunidades&max_price=50&min_conf=alta`.

## Cómo estima la plata

Para cada anuncio, en este orden:

1. **Peso explícito** en título o descripción (`27 g`, `1 oz`, `1/2 onza`, `0,5 kg`) + **ley** (`925`, `ley 0,900`, `plata 999`, `64 % de plata`, `sterling`…). Si falta la ley, se asume 999 en onzas/kilos de inversión y 900 en el resto, con confianza baja.
2. **Moneda conocida**: 2000 pesetas, 12/30/10 € FNMT, 100 pesetas 1966, duros, 1 y 2 pesetas antiguas, 8 reales, thaler, cincuentín, Morgan, half dollar…
3. **Bullion**: Maple Leaf, Filarmónica, Krugerrand… = 1 oz 999.
4. **Lotes**: «lote de 10», «5 monedas» multiplican, salvo que diga «precio por unidad», «c/u», «hay más unidades»…

**Réplicas y no-plata** (excluidas): réplica, copia, reproducción, bañada, chapada, plateada, color plata, alpaca, cobre… respetando negaciones («no es réplica»). También se excluyen accesorios (cápsulas, tubos, estuches), billetes, lotería, joyería, anuncios de compra («compro…») y el spam de palabras clave al final de la descripción («Tags (no leer): …»).

La **confianza** (`alta` / `media` / `baja`) indica cuánto fiarse de los gramos estimados. Por defecto la web enseña `media` o superior.

Todo es heurístico: **antes de comprar, mira siempre las fotos y pregunta el peso al vendedor**.

## Configuración

En `plata/config.py` (o por variable de entorno): palabras de búsqueda, `PLATA_MIN_PRICE` (3 €),
`PLATA_MAX_PRICE` (400 €), `PLATA_MAX_PAGES` (páginas por búsqueda), `PLATA_DELAY` (segundos entre
peticiones), `PLATA_SUSPICIOUS` (−70 %), `PLATA_DB`.

## Aviso

Usa la API pública que usa la propia web de Wallapop, a ritmo pausado (1 petición/s). Es para uso
personal; las condiciones de Wallapop no permiten la extracción automatizada, y la API puede cambiar
sin aviso (en ese caso la ejecución queda marcada como fallida y la web lo indica).
