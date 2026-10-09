# Ideas para la web

Propuestas del 2026-10-04. Hechas (✅): la 1, la 3, la 4 y la 8. Descartada: la 5. Recomendación para seguir: la 2.
Solo tocan `plata/export.py` y `site/index.html`, no el batch.

## Las que más rentan

1. ✅ **Precio objetivo y alerta visual.** El usuario fija un umbral (p. ej. "por debajo de −5 %") y
   esas tarjetas se resaltan, con un contador en el título de la pestaña ("(3) Onzas de plata").
   Umbral en `localStorage`. Es la versión barata de las alertas por Telegram, sin backend.
2. **Gráfica de precio de cada anuncio.** Al pulsar una tarjeta se abre un panel con el histórico
   (`history` ya está en el estado), los días que lleva publicado y las rebajas. Un vendedor que ha
   bajado tres veces tiene prisa por vender, y eso sirve para negociar. Hay que exportar `history` y
   `first_seen` en `data.json` (vigilar el tamaño).
3. ✅ **Precio de referencia por tipo de moneda.** Junto al "−7 % vs. plata", mostrar también "−12 %
   vs. mediana de Maple en Wallapop" (mediana del €/oz por `coin_type`, calculada en el export).
   Separa una buena oferta de una moneda que en Wallapop siempre está cara.

## Comodidad

4. ✅ **Favoritos ⭐**, además de los descartes ✕, en `localStorage`. Avisaría si un favorito baja de
   precio o desaparece (vendido).
5. ~~**Calculadora de compra.**~~ Descartada.
6. **Filtro por distancia o provincia** para comprar en mano sin envío (`city` y `region` ya se
   guardan).

## Contexto de mercado

7. **Gráfica del spot a 30/90 días**, en lugar de solo la sparkline, y el sobreprecio medio del
   mercado a lo largo del tiempo, para saber si Wallapop está barato o caro en general.
8. ✅ **Vendidas recientemente.** Anuncios que desaparecieron (`active=false`) con su último precio.
   Es la mejor pista del precio real de venta de cada moneda. Ojo: se olvidan a los 30 días
   (`FORGET_AFTER_DAYS`).
