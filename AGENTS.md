# AGENTS.md — Onzas de plata en Wallapop

Contexto para agentes de IA (Claude Code, Codex, Cursor…) y para quien retome el proyecto.

- Repositorio (público): https://github.com/ssanga/buscador-plata-wallapop
- Web (GitHub Pages): https://ssanga.github.io/buscador-plata-wallapop/

## Qué es

Herramienta personal para **detectar oportunidades de compra de monedas bullion de plata de
1 onza en Wallapop**. Cada noche descarga los anuncios, descarta réplicas y todo lo que no es una
onza de inversión, y calcula cuánto se paga por onza **respecto al spot**. Una web estática en
GitHub Pages muestra los rankings.

Alcance decidido por el usuario: **solo onzas bullion populares** (Maple Leaf, Filarmónica, Panda,
Eagle, Britannia, Krugerrand, Kookaburra…). No interesan pesetas, duros, "paquitos", francos ni
monedas de colección en general. Antes se estimaba la plata de cualquier moneda; se abandonó.

Métrica clave: `premium_pct = (precio / (onzas_finas × spot_eur_oz) − 1) × 100`.

Idioma del proyecto: **español** (identificadores en inglés; comentarios, docs, UI y logs en
español). El usuario trabaja en Windows 10 con PowerShell.

## Arquitectura

Producción = **GitHub Actions + GitHub Pages** (gratis, repo público). **No hay base de datos**: el
usuario pidió quitar SQLite; el estado es un JSON.

```
.github/workflows/batch-nocturno.yml  (cron 02:17 UTC + ejecución manual con input max_pages)
  1. pytest                                        si el analizador está roto, no se tocan los datos
  2. rama data: estado.json.gz ─► data/estado.json memoria entre ejecuciones
  3. python main.py batch                          (continue-on-error: la web se publica igualmente)
        ├─ plata/spot.py      spot XAG (gold-api.com, fallback Yahoo) + USD→EUR (frankfurter.dev)
        ├─ plata/wallapop.py  API de búsqueda, por tramos de precio
        └─ plata/state.py     carga/guarda data/estado.json (escritura atómica)
  4. python main.py export ─► site/data.json       aquí se ejecuta el analizador
  5. data/estado.json ─► rama data (repo nuevo de un solo commit + push -f: el repo no crece)
  6. site/ ─► GitHub Pages (upload-pages-artifact + deploy-pages)
  7. si el batch falló, el job termina en rojo (email de GitHub)
```

Decisión de diseño: **el estado solo guarda datos crudos y seguimiento; el análisis se calcula al
exportar**. Mejorar `analyzer.py` se aplica a todo en la siguiente exportación, sin reprocesar ni
migrar nada (ya no existe `--reanalyze`).

| Fichero | Responsabilidad |
|---|---|
| `main.py` | **Punto de entrada único**. Subcomandos `batch`, `export` y `web`. |
| `plata/config.py` | Keywords, límites de precio/páginas, retardo, umbral de "sospechosa", retención. Variables de entorno `PLATA_*`. |
| `plata/wallapop.py` | Cliente HTTP con reintentos/backoff y búsqueda por tramos de precio. |
| `plata/state.py` | Formato de `estado.json`, `load()`/`save()`, `last_ok_run()`. |
| `plata/batch.py` | Spot → descarga → `merge()` (nuevas, cambios de precio, inactivas, olvido a los 30 días) → guarda. Siempre guarda, también si falla (registra el run con `status='error'`). |
| `plata/analyzer.py` | `analyze(title, description) -> Analysis` (pura) y `evaluate(analysis, precio, spot)` → métricas. Aquí está casi toda la lógica. |
| `plata/export.py` | `build(state)` → dict para la web: solo anuncios activos que son objetivo, más KPIs e histórico del spot. |
| `plata/web.py` | Flask local: `/` sirve `site/index.html` y `/data.json` llama a `export.build` al vuelo. |
| `site/index.html` | La web completa (HTML + CSS + JS vanilla, sin build). |
| `tests/test_analyzer.py` | Tests del analizador con textos reales de anuncios. |
| `.github/workflows/tests.yml` | pytest en cada push/PR (y manual). |
| `scripts/*.ps1` | Alternativa: ejecutar el batch en el PC con el Programador de tareas de Windows. |

## Comandos

```powershell
pip install -r requirements.txt
python main.py batch                  # ejecución completa (~1 petición/s)
python main.py batch --max-pages 3    # prueba rápida (~1-2 min)
python main.py export [--out site/data.json]
python main.py web [--port 5000] [--host 127.0.0.1]
python -m pytest -q
```

Para pruebas sin tocar el estado real: `PLATA_STATE=<ruta temporal>/estado.json python main.py batch --max-pages 3`.
En la consola de Windows conviene `PYTHONIOENCODING=utf-8` (hay emojis en los anuncios).

## API de Wallapop (no documentada)

- `GET https://api.wallapop.com/api/v3/search` con cabeceras de navegador + `X-DeviceOS: 0`. Sin login.
- Parámetros usados: `keywords`, `order_by=price_low_to_high`, `min_sale_price`, `max_sale_price`,
  `latitude`, `longitude`, `category_id=18000` (Coleccionismo y arte; sin él salen libros, joyas,
  CDs…). **Ojo:** `category_ids` (plural) no filtra.
- Respuesta: `data.section.payload.items[]` (≈40 por página) con `id`, `title`, `description`
  completa, `price.amount`, `images`, `location`, `shipping`, `reserved`, `web_slug`,
  `created_at`/`modified_at` (ms).
- Paginación: `meta.next_page` es un token JWT con todos los filtros; la siguiente petición va
  **solo** con `?next_page=<token>`.
- **Tramos de precio**: con búsquedas amplias, 120 páginas solo cubrían de 3 a 15 € ("moneda
  plata"). Por eso `search()` relanza la búsqueda cada `BAND_PAGES` (50) páginas con
  `min_sale_price` = último precio visto (salvo que todo el tramo tenga el mismo precio). Los
  duplicados del solape se eliminan en `fetch_all`.
- URL pública del anuncio: `https://es.wallapop.com/item/<web_slug>`.
- La búsqueda es nacional; las coordenadas solo afectan a la distancia.
- Wallapop acepta las peticiones desde GitHub Actions (comprobado el 2026-10-03).

## Formato de `data/estado.json`

```
{ "version": 1,
  "runs":  [{started_at, finished_at, status: ok|error, items_seen, items_new, spot_usd_oz, usd_eur, spot_eur_oz, error}],
  "items": {"<id>": {id, title, description, price, url, image, city, region, shippable, reserved,
                     created_at, modified_at, keywords, first_seen, last_seen, active, prev_price,
                     history: [[ts, precio], ...]}} }
```

- `first_seen`/`last_seen` = `started_at` de la ejecución; `active=false` si no apareció en la última.
- `prev_price` = precio anterior tras un cambio (se mantiene hasta el siguiente cambio).
- Se borran los anuncios que llevan más de `FORGET_AFTER_DAYS` (30) sin aparecer; se guardan los
  últimos `RUNS_TO_KEEP` (90) runs.
- Si cambia el formato, subir `VERSION` y migrar en `state.load()`.

## Analizador: orden de decisión

1. Normaliza (minúsculas, sin acentos) y elimina el **spam SEO** de la descripción (`tags`,
   `palabras clave:`, `no leer`, hashtags… hasta el final).
2. **Descartes** (`excluded` con el motivo), en este orden: réplica/no plata (respeta negaciones
   como "no es réplica"; incluye bañada, plateada, dorada, otros metales, "es de oro"), anuncio de
   compra, accesorio (cápsulas, tubos vacíos, lingotes, billetes… salvo "con cápsula" o "tubo de
   25"), moneda no bullion (`NOT_BULLION`: pesetas, duros, francos, half dollar…), fracción o
   múltiplo de onza (1/2, 5 oz, kilo, gramos que no son de una onza) y ley < 999 en el título.
3. **Tipo de moneda** (`COIN_TYPES`, en orden; acepta plural). Cada tipo exige una pista además del
   nombre (`needs`):
   - `plata`: nombres inequívocos (Maple Leaf, Krugerrand…), con "plata/oz/999" en cualquier sitio.
     Un "Krugerrand" sin mención a la plata suele ser de oro.
   - `titulo`: Panda, con "plata/oz/onza" en el título.
   - `onza`: nombres ambiguos (Britannia, Libertad, Lunar, Eagle…), con "onza/oz" en el título.
   - `NAME_CLASH` bloquea homónimos ("Toronto Maple Leafs", "Maple Leaf Rag"…).
   - Si no hay tipo pero el título dice "1 oz / onza de plata" → "Onza genérica".
4. **Confianza**: alta = nombre inequívoco + confirmación (1 oz, onza, 999, 31,1); media/baja según
   el caso; los lotes bajan un nivel.
5. **Cantidad**: patrones del título ("lote 10", "tubo de 25", "5 onzas", "10 x 1 oz"); en la
   descripción solo "lote de N" (y no "lote de 300 €"). Se anula si hay indicios de precio por
   unidad.
6. `evaluate()`: si un lote sale más de un 35 % por debajo del spot, se trata como precio por
   unidad.

En la web, `premium_pct < SUSPICIOUS_PREMIUM_PCT` (−30 %) va a "Demasiado buenas": una onza bullion
casi nunca se vende tan por debajo del spot.

## La web (`site/index.html`)

- Vistas: oportunidades, nuevas, bajadas, demasiado buenas, descartadas. Chips por tipo de
  moneda, filtros (precio máx. por onza, confianza, envío, incluir lotes, texto) y orden. Todo en el
  hash de la URL. Descartes y tema en `localStorage` (siempre con try/catch).
- KPIs: spot con sparkline (un punto por día), mejor onza, onzas en venta, última actualización.
- Colores: tokens CSS en `:root`, modo oscuro con valores propios (media query + `data-theme`).
  Sobreprecio con escala divergente (azul por debajo del spot, rojo por encima, gris en 0); el
  número va siempre en color de texto, no en el de la escala.
- Todo texto de Wallapop es de terceros: se escapa siempre con `esc()` y las URL solo se aceptan
  si empiezan por `https://`.
- Para revisarla sin navegador: `msedge --headless=new --screenshot=… --window-size=1400,1500
  --virtual-time-budget=6000 http://127.0.0.1:5000/` (Edge headless no baja de ~500 px de ancho;
  para móvil, meter la página en un iframe de 390 px).

## Convenciones y cómo trabajar

- **Cada cambio de heurística va con su test**, usando el texto real del anuncio que lo motivó.
- Ciclo de mejora: descargar datos reales, pasar el analizador y revisar el principio del ranking y
  "Demasiado buenas" buscando falsos positivos.
- Preferir falsos negativos a falsos positivos: una onza que se escapa no hace daño; un falso
  positivo ensucia el top.
- **Editar regex con la herramienta de edición, nunca con `sed` ni con sustituciones de cadenas en
  Python vía heredoc**: los `\b` se convierten en caracteres de control (backspace) y los tests
  fallan sin motivo aparente. Ha pasado dos veces.
- Sin dependencias pesadas: `requests` + `flask` (+ `pytest`).
- `data/`, `logs/` y `site/data.json` no se versionan. El estado de producción está en la rama
  `data`; no hacer merge de esa rama.
- El repo es público: no guardar datos personales de vendedores (no se guarda `user_id`) ni secretos.

## Limitaciones conocidas

- Si Wallapop bloquea algún día las IP de GitHub Actions, el batch fallará con HTTP 403/429; la
  alternativa es ejecutar en el PC (`scripts/programar_tarea.ps1`) y subir solo `site/data.json`.
- GitHub desactiva los cron de repos públicos tras 60 días sin actividad (avisa por email).
- "Onza genérica" mezcla bullion con onzas de colección (Star Wars, Marvel…) que llevan mucho
  sobreprecio; salen al final del ranking, pero ocupan sitio.
- No se distingue la Britannia anterior a 2013 (ley 958) de la actual (999).
- El valor numismático no se tiene en cuenta: solo el de la plata.

## Ideas pendientes

- Alertas (Telegram/email) cuando aparece una onza por debajo de X % del spot.
- Clasificación con LLM (p. ej. Claude Haiku) solo de los mejores candidatos para confirmar
  réplica/tipo, en caché por `id` + `modified_at`.
- Ejecución incremental (`order_by=newest` hasta encontrar anuncios ya vistos) varias veces al día.
- Precio de referencia por tipo de moneda (mediana de Wallapop) además del spot.
- Gráfica del histórico de precio de cada anuncio (los datos ya están en `history`).
