# Onzas de plata en Wallapop

Cada noche revisa Wallapop en busca de **monedas bullion de plata de 1 onza** (Maple Leaf,
Filarmónica, Krugerrand, Panda, Silver Eagle, Britannia, Kookaburra, Libertad…), descarta réplicas
y todo lo que no es una onza de inversión, y las ordena según lo que pagas **frente al precio de la
plata** (spot).

- **Web:** [ssanga.github.io/buscador-plata-wallapop](https://ssanga.github.io/buscador-plata-wallapop/#view=oportunidades&conf=media&limit=20)
- **Repositorio:** https://github.com/ssanga/buscador-plata-wallapop

```
GitHub Actions (cada noche, 02:17 UTC)
  ├─ rama data: estado.json.gz ──► data/estado.json   (memoria entre noches: nuevas, bajadas, vendidas)
  ├─ python main.py batch    ├─ API de búsqueda de Wallapop (15 búsquedas de onzas, por tramos de precio)
  │                          └─ precio spot: gold-api.com + frankfurter.dev (gratis, sin clave)
  ├─ python main.py export ──► site/data.json          (aquí se aplica el analizador)
  ├─ data/estado.json ──► rama data (un único commit, se reescribe cada noche)
  └─ site/ (index.html + data.json) ──► GitHub Pages
```

Todo es estático y no hay base de datos: el estado es un fichero JSON y la web es un único
`index.html` que descarga `data.json` y filtra y ordena en el navegador.

## Qué cuenta como "onza"

Entra:
- Monedas bullion de 1 oz: Maple Leaf, Filarmónica, Krugerrand, Kookaburra, Arca de Noé,
  Elefante de Somalia, Silver Eagle, Panda (30 g), Britannia, Libertad, Koala, Canguro, Lunar,
  Buffalo, Eagle, y onzas genéricas de plata 999 ("onza troy de plata", "1 oz plata").
- Lotes y tubos de onzas ("Tubo de 25 Maple", "Lote 10 Filarmónicas"), con su precio por onza.
  Si el lote sale por debajo de un 35 % del valor de la plata, se entiende que el precio es por
  unidad.

Se descarta:
- Réplicas, bañadas, chapadas, doradas, plateadas, "color plata", otros metales. Se respetan las
  negaciones: "no es réplica" no descarta.
- Monedas que no son bullion: pesetas, duros, "paquitos", francos, reales, euros conmemorativos,
  dólares antiguos (half dollar, Morgan…), centavos.
- Fracciones (1/2, 1/4, 1/10 oz), monedas de varias onzas, kilos y lingotes, y pesos en gramos que
  no son de una onza.
- Ley inferior a 999 (925, 900…), accesorios (cápsulas, tubos vacíos, estuches), anuncios de
  compra y cosas que solo comparten nombre ("Toronto Maple Leafs").

Cada onza lleva una **confianza** (alta / media / baja) según lo claro que sea el anuncio. Por
defecto la web muestra media o superior.

## La web

| Vista | Contenido |
|---|---|
| **Oportunidades** | Ordenadas por sobreprecio sobre el spot. Negativo = más barata que la plata que contiene. |
| **Nuevas** | Aparecidas en la última actualización. |
| **Bajadas** | El vendedor ha rebajado el precio. |
| **Demasiado buenas** | Más de un 30 % por debajo del spot: casi siempre réplicas no declaradas, precios por unidad o errores. |
| **Descartadas** | Las que has ocultado con ✕. Se guardan en tu navegador (localStorage). |

Hay filtros por tipo de moneda, precio máximo por onza, confianza, "con envío" y "incluir lotes",
y búsqueda por título. Los filtros quedan en la URL, así que se pueden guardar como marcador.
Tiene modo claro y oscuro.

## Puesta en marcha en GitHub (una sola vez)

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Actions → Batch nocturno → Run workflow**. Con `max_pages = 3` hace una prueba rápida de unos
   minutos; sin `max_pages` hace la carga completa.
3. A partir de ahí se ejecuta solo cada noche. Si falla, GitHub te manda un email y la web sigue
   mostrando los datos anteriores con un aviso.

Notas:
- El estado vive en la rama `data` como `estado.json.gz`. Para descargarlo:
  `git fetch origin data && git show origin/data:estado.json.gz | gunzip > data/estado.json`.
  Para subir un estado local (sobrescribe el de producción), consulta "Operaciones en producción"
  en [AGENTS.md](AGENTS.md).
- En repos públicos, GitHub desactiva los workflows programados tras 60 días sin actividad. Avisa
  por email antes y se reactiva con un clic en la pestaña Actions.
- El workflow `Tests` pasa los tests en cada push.

## Uso en local

```powershell
pip install -r requirements.txt
python main.py batch                  # descarga y actualiza data/estado.json
python main.py web                    # http://127.0.0.1:5000 (la misma web, con tus datos)
```

| Comando | Para qué |
|---|---|
| `python main.py batch --max-pages 3` | prueba rápida |
| `python main.py export` | genera `site/data.json` |
| `python -m pytest` | tests del analizador |

Como el análisis se hace al exportar, un cambio en `plata/analyzer.py` se ve con solo recargar la
web local: no hace falta volver a descargar nada.

Si prefieres ejecutarlo en tu PC en lugar de en GitHub, `scripts\programar_tarea.ps1` lo registra
en el Programador de tareas de Windows (03:30 por defecto).

## Configuración

En `plata/config.py` (o por variable de entorno): búsquedas, `PLATA_MIN_PRICE` (15 €),
`PLATA_MAX_PRICE` (2000 €), `PLATA_MAX_PAGES` (páginas por búsqueda), `PLATA_DELAY` (segundos
entre peticiones), `PLATA_SUSPICIOUS` (−30 %) y `PLATA_STATE` (ruta del estado).

## Aviso

Usa la API pública de la propia web de Wallapop, a ritmo pausado (1 petición por segundo). Es para
uso personal. Las condiciones de Wallapop no permiten la extracción automatizada y la API puede
cambiar sin aviso; en ese caso la ejecución queda marcada como fallida y la web lo indica.
