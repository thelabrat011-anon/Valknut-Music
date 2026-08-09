"""
lyrics.py

Busca y lee letras sincronizadas en formato .lrc (el mismo nombre que
la canción, con extensión .lrc, en la misma carpeta). Si no hay .lrc
pero existe un .txt con letra simple, la muestra sin sincronizar.
"""

import os
import re

LRC_LINE = re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)')


def find_lyrics_file(song_path):
    base = os.path.splitext(song_path)[0]
    if os.path.exists(base + '.lrc'):
        return base + '.lrc', True
    if os.path.exists(base + '.txt'):
        return base + '.txt', False
    return None, False


def parse_lrc(path):
    """Devuelve una lista de (segundos, texto) ordenada por tiempo."""
    lines = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for raw in f:
                m = LRC_LINE.match(raw.strip())
                if m:
                    minutes = int(m.group(1))
                    seconds = float(m.group(2))
                    text = m.group(3).strip()
                    total = minutes * 60 + seconds
                    lines.append((total, text))
    except Exception:
        pass
    lines.sort(key=lambda x: x[0])
    return lines


def load_lyrics(song_path):
    """Devuelve ('synced', [(seg, texto), ...]) o ('plain', 'texto completo')
    o (None, None) si no hay letra disponible."""
    path, synced = find_lyrics_file(song_path)
    if not path:
        return None, None
    if synced:
        return 'synced', parse_lrc(path)
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return 'plain', f.read()
    except Exception:
        return None, None


def current_line_index(lrc_lines, position_seconds):
    """Índice de la línea que corresponde al momento actual de la canción."""
    idx = -1
    for i, (t, _) in enumerate(lrc_lines):
        if t <= position_seconds:
            idx = i
        else:
            break
    return idx
