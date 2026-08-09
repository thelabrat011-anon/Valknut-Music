# Reproductor de Música — Instrucciones

## Archivos del proyecto
- `main.py` — interfaz completa (biblioteca, reproductor, listas, EQ, historial)
- `audio_engine.py` — motor de audio (MediaPlayer nativo de Android + Ecualizador)
- `library.py` — escaneo de archivos de música y metadatos
- `lyrics.py` — lectura de letras sincronizadas (.lrc)
- `storage.py` — listas de reproducción, favoritos, historial (persistente)
- `buildozer.spec` — configuración de compilación
- `icon.png` — ícono (Valknut verde)
- `.github/workflows/build.yml` — compila automáticamente en GitHub

## Cómo compilar (mismo proceso que la app de radio)
1. Crea un repositorio nuevo en GitHub (puede llamarse `music-app` o como quieras).
2. Sube TODOS estos archivos manteniendo la misma estructura de carpetas
   (ojo con `.github/workflows/build.yml`, sigue el mismo truco de crear el
   archivo escribiendo la ruta completa con barras).
3. Ve a la pestaña "Actions" y espera a que termine (puede tardar más que
   la radio, 15-30 min, porque incluye una librería adicional).
4. Descarga el APK desde "Artifacts", desinstala cualquier versión anterior,
   e instala la nueva.

## De dónde saca la música
La app busca canciones en estas carpetas del teléfono:
- `/storage/emulated/0/Music`
- `/storage/emulated/0/Download`
- `/sdcard/Music`

Si tu música está en otra carpeta, dímelo y ajustamos la ruta.

## Letras sincronizadas
Para que aparezcan letras tipo karaoke, necesitas un archivo `.lrc` con el
MISMO nombre que la canción, en la misma carpeta. Por ejemplo:
```
Mi Cancion.mp3
Mi Cancion.lrc
```
Si no tienes archivos `.lrc`, puedes usar un `.txt` con la letra simple
(se mostrará sin sincronizar).

## Puntos que probablemente necesiten ajuste (avisado desde ya)
- **Permisos de almacenamiento**: la primera vez que abras la app, Android
  debería preguntarte por permiso para acceder a tus archivos. Si la
  biblioteca aparece vacía, es la primera sospechosa.
- **Ecualizador real**: solo funciona reproduciendo una canción en el
  teléfono de verdad (no se puede probar en escritorio). Es la parte más
  delicada de todo el proyecto — si falla o no aparece, cuéntame el
  mensaje exacto y lo resolvemos como hicimos con lo del micrófono.
- **Carátulas de álbum**: esta primera versión no extrae la imagen
  incrustada en el archivo (queda pendiente para una siguiente vuelta si
  te interesa).
