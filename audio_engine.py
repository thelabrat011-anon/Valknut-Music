"""
audio_engine.py

Envuelve android.media.MediaPlayer (via pyjnius) para tener control total
sobre la reproducción y poder enganchar un Equalizer nativo de Android
(android.media.audiofx.Equalizer), algo que no es posible con el
reproductor simple de Kivy (SoundLoader).

En escritorio (donde pyjnius no existe) cae a un modo simulado para que
la interfaz se pueda revisar sin romperse, pero el audio real y el EQ
solo funcionan en un teléfono Android.
"""

try:
    from jnius import autoclass
    ANDROID = True
except Exception:
    ANDROID = False


class EqualizerController:
    """Envuelve android.media.audiofx.Equalizer."""

    PRESETS = ['Normal', 'Rock', 'Pop', 'Jazz', 'Bass Boost', 'Vocal']

    def __init__(self, session_id):
        self.available = False
        self.eq = None
        self.num_bands = 0
        self.band_range = (-1500, 1500)
        if not ANDROID:
            return
        try:
            Equalizer = autoclass('android.media.audiofx.Equalizer')
            self.eq = Equalizer(0, session_id)
            self.eq.setEnabled(True)
            self.num_bands = self.eq.getNumberOfBands()
            r = self.eq.getBandLevelRange()
            self.band_range = (r[0], r[1])
            self.available = True
        except Exception as e:
            self.available = False
            self.error = str(e)

    def set_band_level(self, band, level_millibel):
        if self.available:
            try:
                self.eq.setBandLevel(band, int(level_millibel))
            except Exception:
                pass

    def get_band_level(self, band):
        if self.available:
            try:
                return self.eq.getBandLevel(band)
            except Exception:
                return 0
        return 0

    def get_center_freq(self, band):
        if self.available:
            try:
                return self.eq.getCenterFreq(band) // 1000  # Hz
            except Exception:
                return 0
        return 0

    def use_preset(self, name):
        """Aplica un preset simple ajustando bandas manualmente,
        ya que los presets nativos de Android varían por fabricante."""
        if not self.available:
            return
        curve = {
            'Normal':      [0, 0, 0, 0, 0],
            'Rock':        [500, 300, -200, 200, 400],
            'Pop':         [-100, 200, 400, 200, -100],
            'Jazz':        [300, 100, -100, 100, 300],
            'Bass Boost':  [800, 500, 0, 0, 0],
            'Vocal':       [-200, 0, 400, 400, -100],
        }.get(name, [0, 0, 0, 0, 0])

        bands = min(self.num_bands, len(curve))
        for i in range(bands):
            self.set_band_level(i, curve[i])

    def release(self):
        if self.available:
            try:
                self.eq.release()
            except Exception:
                pass


class AudioPlayer:
    """Reproductor de audio. Usa android.media.MediaPlayer si está
    disponible; si no (escritorio), simula el comportamiento básico."""

    def __init__(self, on_complete=None):
        self.on_complete = on_complete
        self.player = None
        self.equalizer = None
        self._duration = 0
        self._path = None
        self._is_playing = False

        if ANDROID:
            self.MediaPlayer = autoclass('android.media.MediaPlayer')

    def load(self, path):
        self.release()
        self._path = path
        if ANDROID:
            try:
                self.player = self.MediaPlayer()
                self.player.setDataSource(path)
                self.player.prepare()
                self._duration = self.player.getDuration()

                def _on_complete(mp):
                    self._is_playing = False
                    if self.on_complete:
                        self.on_complete()

                self.player.setOnCompletionListener(_on_complete)

                session_id = self.player.getAudioSessionId()
                self.equalizer = EqualizerController(session_id)
                return True
            except Exception as e:
                self.player = None
                self.error = str(e)
                return False
        else:
            # Modo escritorio: sin audio real, solo para revisar la UI.
            self._duration = 180000
            return True

    def play(self):
        if ANDROID and self.player:
            self.player.start()
        self._is_playing = True

    def pause(self):
        if ANDROID and self.player:
            self.player.pause()
        self._is_playing = False

    def stop(self):
        if ANDROID and self.player:
            try:
                self.player.stop()
            except Exception:
                pass
        self._is_playing = False

    def seek(self, ms):
        if ANDROID and self.player:
            self.player.seekTo(int(ms))

    def set_volume(self, level_0_to_1):
        v = max(0.0, min(1.0, level_0_to_1))
        if ANDROID and self.player:
            self.player.setVolume(v, v)

    def get_position(self):
        if ANDROID and self.player:
            try:
                return self.player.getCurrentPosition()
            except Exception:
                return 0
        return 0

    def get_duration(self):
        return self._duration

    def is_playing(self):
        if ANDROID and self.player:
            try:
                return self.player.isPlaying()
            except Exception:
                return False
        return self._is_playing

    def release(self):
        if self.equalizer:
            self.equalizer.release()
            self.equalizer = None
        if ANDROID and self.player:
            try:
                self.player.release()
            except Exception:
                pass
        self.player = None
