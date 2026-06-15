# SteamNewsVideos - mejoras aplicadas

## Que hace este proyecto

El pipeline correcto si trabaja con Steam:

1. `scrapper.py` busca lanzamientos recientes en Steam por rango de fechas.
2. `scrapper2.py` entra a cada pagina de Steam y guarda descripcion, tags, reviews y media oficial.
3. `analytics.py` calcula score con reviews de Steam, viewers de Twitch y presencia en `popularupcoming`.
4. `folderpreparation.py` descarga media de los juegos seleccionados en `currentgames`.
5. `scriptcreator.py` genera intro, descripcion por juego y outro.
6. `narratorlocal.py` o `narratoreleven.py` generan narracion.
7. `editor.py` compone el video vertical final.

## Problemas detectados en el video actual

- El video ya usa clips oficiales, pero no comunica el ranking visualmente.
- No hay portada con promesa clara del video.
- No aparecen nombre del juego, posicion, score, reviews, precio ni tags.
- No hay subtitulos; en mobile sin audio se pierde casi todo el contexto.
- El scoring existe, pero el espectador no ve por que un juego esta por encima de otro.

## Mejoras implementadas

- Credenciales movidas a variables de entorno de usuario: `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `ELEVENLABS_API_KEY`.
- `editor.py` ahora puede renderizar overlays visuales:
  - titulo de intro para formato Top Steam releases,
  - ranking por juego,
  - chips de precio, reviews, rating, Twitch y score,
  - tags principales,
  - subtitulos aproximados desde `description.txt`,
  - outro con lista resumida del ranking.
- Salida configurable con `STEAM_VIDEO_OUTPUT`, por ejemplo `STEAM_VIDEO_OUTPUT=video_final_enhanced.mp4`.

## Siguiente mejora recomendada

Cambiar el score para usar crecimiento relativo:

- reviews recientes por dia desde lanzamiento,
- tendencia de Twitch por ventana temporal, no solo viewers actuales,
- Steam tags ponderados por audiencia,
- descuento/precio como dato visual, no como criterio fuerte,
- filtro para evitar juegos con poca media o trailers de baja calidad.

