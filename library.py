"""
library.py

Escanea el almacenamiento del teléfono en busca de archivos de audio,
lee sus metadatos (título, artista, álbum, año, género) usando mutagen,
y ofrece funciones de ordenamiento.
"""

import os
import time

AUDIO_EXTS = ('.mp3', '.flac', '.ogg', '.wav', '.m4a', '.aac')

DEFAULT_SEARCH_DIRS = [
    '/storage/emulated/0/Music',
    '/storage/emulated/0/Download',
    '/sdcard/Music',
]


class Song:
    def __init__(self, path):
        self.path = path
        self.title = os.path.splitext(os.path.basename(path))[0]
        self.artist = 'Desconocido'
        self.album = 'Desconocido'
        self.genre = ''
        self.year = ''
        self.duration = 0
        self.bitrate = 0
        self.format = os.path.splitext(path)[1].replace('.', '').upper()
        self.size = 0
        try:
            self.size = os.path.getsize(path)
            self.date_added = os.path.getmtime(path)
        except Exception:
            self.date_added = 0
        self._read_metadata()

    def _read_metadata(self):
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(self.path, easy=True)
            if audio is not None:
                if audio.get('title'):
                    self.title = audio['title'][0]
                if audio.get('artist'):
                    self.artist = audio['artist'][0]
                if audio.get('album'):
                    self.album = audio['album'][0]
                if audio.get('genre'):
                    self.genre = audio['genre'][0]
                if audio.get('date'):
                    self.year = audio['date'][0][:4]
                if audio.info:
                    self.duration = int(audio.info.length * 1000)
                    self.bitrate = getattr(audio.info, 'bitrate', 0)
        except Exception:
            pass

    def to_dict(self):
        return {
            'path': self.path, 'title': self.title, 'artist': self.artist,
            'album': self.album, 'genre': self.genre, 'year': self.year,
            'duration': self.duration, 'bitrate': self.bitrate,
            'format': self.format, 'size': self.size, 'date_added': self.date_added,
        }


def scan_library(extra_dirs=None):
    """Recorre las carpetas conocidas (y cualquier extra) buscando audio."""
    dirs = list(DEFAULT_SEARCH_DIRS)
    if extra_dirs:
        dirs.extend(extra_dirs)

    songs = []
    seen = set()
    for base in dirs:
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for f in files:
                if f.lower().endswith(AUDIO_EXTS):
                    full = os.path.join(root, f)
                    if full in seen:
                        continue
                    seen.add(full)
                    try:
                        songs.append(Song(full))
                    except Exception:
                        continue
    return songs


def sort_songs(songs, by='title'):
    key_funcs = {
        'title': lambda s: s.title.lower(),
        'artist': lambda s: s.artist.lower(),
        'album': lambda s: s.album.lower(),
        'date_added': lambda s: -s.date_added,
        'year': lambda s: s.year or '',
    }
    return sorted(songs, key=key_funcs.get(by, key_funcs['title']))


def group_by_album(songs):
    albums = {}
    for s in songs:
        albums.setdefault(s.album, []).append(s)
    return albums


def group_by_artist(songs):
    artists = {}
    for s in songs:
        artists.setdefault(s.artist, []).append(s)
    return artists
