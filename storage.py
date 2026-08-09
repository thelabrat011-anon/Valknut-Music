"""
storage.py

Persistencia simple en JSON dentro de la carpeta privada de la app:
listas de reproducción, favoritos, historial de escucha y ajustes
(orden preferido, estado del EQ, etc).
"""

import json
import os
import time


class Store:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.file = os.path.join(data_dir, 'library_data.json')
        self.data = {
            'playlists': {},       # {nombre: [rutas...]}
            'favorites': [],       # [rutas...]
            'history': [],         # [{'path':..., 'ts':...}, ...]
            'play_counts': {},     # {ruta: veces reproducida}
            'eq_settings': {'preset': 'Normal', 'bands': {}, 'crossfade': 4},
        }
        self.load()

    def load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, 'r') as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception:
                pass

    def save(self):
        try:
            with open(self.file, 'w') as f:
                json.dump(self.data, f)
        except Exception:
            pass

    # -- Playlists ------------------------------------------------------
    def create_playlist(self, name):
        self.data['playlists'].setdefault(name, [])
        self.save()

    def add_to_playlist(self, name, path):
        self.data['playlists'].setdefault(name, [])
        if path not in self.data['playlists'][name]:
            self.data['playlists'][name].append(path)
        self.save()

    def remove_playlist(self, name):
        self.data['playlists'].pop(name, None)
        self.save()

    # -- Favoritos --------------------------------------------------------
    def toggle_favorite(self, path):
        favs = self.data['favorites']
        if path in favs:
            favs.remove(path)
        else:
            favs.append(path)
        self.save()

    def is_favorite(self, path):
        return path in self.data['favorites']

    # -- Historial y conteo de reproducciones --------------------------
    def log_play(self, path):
        self.data['history'].insert(0, {'path': path, 'ts': time.time()})
        self.data['history'] = self.data['history'][:300]
        self.data['play_counts'][path] = self.data['play_counts'].get(path, 0) + 1
        self.save()

    def play_count(self, path):
        return self.data['play_counts'].get(path, 0)

    # -- Smart playlists (reglas simples) -------------------------------
    def most_played(self, songs, limit=30):
        counts = self.data['play_counts']
        ranked = sorted(songs, key=lambda s: counts.get(s.path, 0), reverse=True)
        return [s for s in ranked if counts.get(s.path, 0) > 0][:limit]

    def recently_added(self, songs, limit=30):
        ranked = sorted(songs, key=lambda s: s.date_added, reverse=True)
        return ranked[:limit]

    def recently_played(self, songs, limit=30):
        by_path = {s.path: s for s in songs}
        seen = set()
        result = []
        for entry in self.data['history']:
            p = entry['path']
            if p in by_path and p not in seen:
                seen.add(p)
                result.append(by_path[p])
            if len(result) >= limit:
                break
        return result

    def favorite_songs(self, songs):
        favs = set(self.data['favorites'])
        return [s for s in songs if s.path in favs]

    # -- EQ ---------------------------------------------------------------
    def save_eq(self, preset, bands, crossfade):
        self.data['eq_settings'] = {'preset': preset, 'bands': bands, 'crossfade': crossfade}
        self.save()

    def get_eq(self):
        return self.data['eq_settings']
