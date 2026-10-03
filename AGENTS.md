# AGENTS.md — Buscador de plata en Wallapop

Contexto para agentes de IA (Claude Code, Codex, Cursor…) y para quien retome el proyecto.

## Qué es

Herramienta personal para **detectar oportunidades de compra de monedas de plata en Wallapop**.
Cada noche descarga los anuncios, descarta réplicas y anuncios que no son monedas, estima los
gramos de plata fina de cada uno y calcula cuánto se paga **respecto al valor de fundición**
(precio spot). Una web local muestra rankings (top 20 por defecto).

La métrica clave es `premium_pct = (precio / valor_fundición − 1) × 100`. El precio absoluto
engaña: una moneda de 5 g a 10 € es más cara que una onza a 50 €.

Idioma del proyecto: **español** (código con identificadores en inglés, comentarios, docs, UI y
mensajes de log en español). El usuario trabaja en Windows 10 con PowerShell.

## Arquitectura

```
Programador de tareas de Windows (03:30)
  └─ scripts/ejecutar_batch.ps1 ─► python main.py batch
        ├─ plata/spot.py      precio spot XAG (gold-api.com, fallback Yahoo) + USD→EUR (frankfurter.dev)
        ├─ plata/wallapop.py  API de búsqueda de Wallapop, una búsqueda por keyword de config.KEYWORDS
        ├─ plata/analyzer.py  heurísticas: réplica, accesorio, comprador, peso, ley, cantidad
        └─ plata/db.py        SQLite en data/plata.db
python main.py web ─► plata/web.py (Flask) + plata/templates/index.html — lee SQLite en cada petición
```

| Fichero | Responsabilidad |
|---|---|
| `main.py` | **Punto de entrada único**. Subcomandos `batch` y `web`. |
| `plata/config.py` | Keywords, límites de precio/páginas, retardo, umbral de "sospechoso". Todo sobreescribible por variables de entorno `PLATA_*`. |
| `plata/wallapop.py` | Cliente HTTP con reintentos/backoff. |
| `plata/analyzer.py` | Función pura `analyze(title, description) -> Analysis`. Es donde está casi toda la lógica y donde más se itera. |
| `plata/batch.py` | Orquesta: spot → descarga → análisis → upsert → marca inactivos. También `--reanalyze`. |
| `plata/db.py` | Esquema SQLite (`CREATE IF NOT EXISTS`) y `connect()` como context manager (hace commit al salir). |
| `plata/web.py` | Vistas: `oportunidades`, `baratas`, `nuevos`, `bajadas`, `sospechosos`, `descartados`; `POST /item/<id>/descartar|restaurar`; JSON en `/api/ranking` y `/item/<id>/historial`. |
| `tests/test_analyzer.py` | Tests del analizador con textos reales de anuncios. |
| `scripts/programar_tarea.ps1` | Registra la tarea diaria `BuscadorPlataWallapop`. |

## Comandos

```powershell
pip install -r requirements.txt
python main.py batch                  # ejecución completa (~15-30 min, ~1 petición/s)
python main.py batch --max-pages 3    # prueba rápida (~1 min)
python main.py batch --reanalyze      # recalcula el análisis de lo guardado, sin descargar
python main.py web [--port 5000] [--host 127.0.0.1]
python -m pytest -q                   # tests
```

Para pruebas sin tocar la BD real: `PLATA_DB=<ruta temporal>/test.db python main.py batch --max-pages 3`.
En la consola de Windows conviene `PYTHONIOENCODING=utf-8` (hay emojis en los anuncios).

## API de Wallapop (no documentada)

- `GET https://api.wallapop.com/api/v3/search` con cabeceras de navegador + `X-DeviceOS: 0`. Sin login.
- Parámetros usados: `keywords`, `order_by=price_low_to_high`, `min_sale_price`, `max_sale_price`,
  `latitude`, `longitude`, `category_id=18000` (Coleccionismo y arte; sin él salen libros, joyas,
  CDs…). **Ojo:** `category_ids` (plural) no filtra.
- Respuesta: `data.section.payload.items[]` (≈40 por página) con `id`, `title`, `description`
  completa, `price.amount`, `images`, `location`, `shipping`, `reserved`, `web_slug`, `created_at`/`modified_at` (ms).
- Paginación: `meta.next_page` es un token JWT que ya lleva todos los filtros; la siguiente
  petición se hace **solo** con `?next_page=<token>`.
- URL pública del anuncio: `https://es.wallapop.com/item/<web_slug>`.
- La búsqueda es nacional; las coordenadas solo afectan a la distancia.
- Uso personal y a ritmo pausado. Si la API cambia, el batch registra `status='error'` en `runs`
  y la web muestra un aviso con los datos anteriores.

## Modelo de datos (SQLite)

- `items`: un registro por anuncio. Campos crudos + resultado del análisis (`is_replica`,
  `replica_reason`, `is_wanted`, `is_accessory`, `weight_g`, `purity`, `quantity`, `fine_grams`,
  `estimate_source`, `confidence`, `notes`, `melt_value_eur`, `eur_per_fine_g`, `premium_pct`).
  `first_seen`/`last_seen` = `started_at` de la ejecución; `active=0` si no apareció en la última;
  `dismissed=1` lo pone el usuario desde la web y **se conserva** entre ejecuciones;
  `prev_price` guarda el precio anterior tras un cambio (se mantiene hasta el siguiente cambio).
- `price_history(item_id, price, seen_at)`: solo cuando cambia el precio.
- `runs`: una fila por ejecución con spot del día, contadores y error.

El esquema se crea con `CREATE TABLE IF NOT EXISTS`: **añadir una columna nueva requiere
migración** (`ALTER TABLE items ADD COLUMN …`) para las BD existentes; no basta con editar `SCHEMA`.

## Analizador: orden de decisión

1. Normaliza (minúsculas, sin acentos), elimina **spam SEO** (`tags`, `palabras clave:`,
   `no leer`, hashtags… hasta el final del texto).
2. Flags de exclusión: `is_wanted` (compradores, también disfrazados en la descripción),
   `is_accessory` (cápsulas, tubos, estuches, billetes, lotería, joyas… en el título, salvo
   "con estuche"), `is_replica` (réplica, bañada, plateada, color plata, otros metales, "es de oro";
   respeta negaciones como "no es réplica").
3. Cantidad: patrones del título; en la descripción solo "lote de N". Se anula si hay indicios de
   **precio por unidad** ("c/u", "precio por unidad", "hay más unidades", "€/cada"…).
4. Peso, por prioridad:
   1. **Explícito** (g, kg, oz, fracciones de onza) + ley (porcentaje, `ley 0,xxx`, 999/925/900…).
      Sin ley: solo si el título dice plata; se asume 999 en onzas/kilos (confianza media) o 900
      en el resto (confianza **baja**).
   2. **Moneda conocida** (`KNOWN_COINS`): en el título, o en los primeros 250 caracteres de la
      descripción solo si el título es genérico de plata y no es lote.
   3. **Bullion 1 oz**, solo en el título. Nombres fuertes (Maple Leaf, Krugerrand…) bastan; los
      ambiguos (Britannia, Libertad…) exigen "onza/oz" y que no sea moneda pequeña (dime, penny…).
5. Lotes bajan un nivel la confianza.

`premium_pct < config.SUSPICIOUS_PREMIUM_PCT` (−70 %) va a la pestaña "Demasiado buenos": casi
siempre es precio por unidad, réplica no declarada o peso mal leído. **No bajar el umbral a −50 %**:
vender un 12 € o un 2000 pesetas a valor facial (≈ −50/−60 %) es la oportunidad real más típica.

## Convenciones y cómo trabajar

- **Cada cambio de heurística va con su test** en `tests/test_analyzer.py`, usando el texto real
  del anuncio que lo motivó. Después: `python -m pytest -q` y `python main.py batch --reanalyze`.
- Para validar con datos reales, consultar la BD y mirar el top de `oportunidades` y de
  `sospechosos` buscando falsos positivos; ese ha sido el ciclo de mejora del analizador.
- Preferir falsos negativos a falsos positivos: un anuncio sin estimar no hace daño; uno mal
  estimado ensucia el top 20.
- **Editar regex con la herramienta de edición, no con `sed` ni con sustituciones de cadenas en
  Python vía heredoc**: los `\b` acabaron convertidos en caracteres de control (backspace) y los
  tests fallaban sin motivo aparente.
- Sin dependencias pesadas: `requests` + `flask`. No añadir navegador headless salvo que la API deje
  de funcionar.
- `data/` y `logs/` no se versionan.

## Limitaciones conocidas

- Sets conmemorativos de quiosco ("plata pura", numerados) y medallas bañadas no declaradas
  pueden colarse: el usuario los descarta desde la web.
- Monedas con dos metales o lotes mezclados (oro + plata) no se separan.
- El valor numismático no se tiene en cuenta: solo valor de la plata.
- La ejecución completa recorre hasta `MAX_PAGES_PER_KEYWORD` × 19 keywords; "moneda plata" sola
  da ~4.400 anuncios.

## Ideas pendientes

- Alertas (Telegram/email) cuando entra en el top un anuncio nuevo o una bajada por debajo de X %.
- Clasificación con LLM (p. ej. Claude Haiku) solo de los ~100 mejores candidatos para confirmar
  réplica/peso/ley, guardando el resultado en caché por `id` + `modified_at`.
- Ejecución incremental (`order_by=newest` hasta encontrar anuncios ya vistos) varias veces al día.
- Histórico de precio por tipo de moneda (mediana de €/g) para detectar anuncios por debajo del
  mercado de Wallapop, no solo del spot.
- Valoración de reputación del vendedor y distancia/envío.
