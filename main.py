import os
import json
from functools import partial

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import StringProperty, BooleanProperty, NumericProperty, ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window

from audio_engine import AudioPlayer
from library import scan_library, sort_songs, group_by_album, group_by_artist, Song
from lyrics import load_lyrics, current_line_index
from storage import Store

try:
    from jnius import autoclass
    ANDROID = True
except Exception:
    ANDROID = False


# ---------------------------------------------------------------------------
# Estilo
# ---------------------------------------------------------------------------
KV = '''
<RoundedButton@Button>:
    background_color: 0,0,0,0
    background_normal: ''
    color: 1,1,1,1
    bold: True
    canvas.before:
        Color:
            rgba: (0.10,0.55,0.35,1) if self.state == 'normal' else (0.07,0.42,0.27,1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [16]

<TabBtn@ToggleButton>:
    background_color: 0,0,0,0
    background_normal: ''
    color: (1,1,1,1) if self.state == 'down' else (0.55,0.55,0.6,1)
    bold: True
    group: 'nav'
    font_size: '12sp'

<SongRow>:
    orientation: 'horizontal'
    size_hint_y: None
    height: 64
    padding: 12, 6
    spacing: 10
    canvas.before:
        Color:
            rgba: (0.15,0.15,0.17,1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [10]

    BoxLayout:
        orientation: 'vertical'
        Label:
            text: root.title
            color: 1,1,1,1
            bold: True
            font_size: '15sp'
            halign: 'left'
            valign: 'middle'
            text_size: self.size
            shorten: True
        Label:
            text: root.subtitle
            color: 0.6,0.6,0.65,1
            font_size: '11sp'
            halign: 'left'
            valign: 'middle'
            text_size: self.size
            shorten: True

    Button:
        text: '<3' if root.is_fav else '+'
        size_hint_x: None
        width: 40
        background_color: 0,0,0,0
        background_normal: ''
        color: (0.9,0.25,0.35,1) if root.is_fav else (0.55,0.55,0.6,1)
        on_press: root.toggle_fav()

    Button:
        text: '...'
        size_hint_x: None
        width: 34
        background_color: 0,0,0,0
        background_normal: ''
        color: 0.55,0.55,0.6,1
        on_press: root.open_menu()
'''


class SongRow(BoxLayout):
    title = StringProperty('')
    subtitle = StringProperty('')
    is_fav = BooleanProperty(False)
    song = None
    controller = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and touch.is_double_tap is False:
            pass
        return super().on_touch_down(touch)

    def toggle_fav(self):
        if self.controller:
            self.controller.toggle_favorite(self.song)
            self.is_fav = self.controller.store.is_favorite(self.song.path)

    def open_menu(self):
        if self.controller:
            self.controller.open_song_menu(self.song)


# ---------------------------------------------------------------------------
# Controlador central: une audio, cola, biblioteca y persistencia
# ---------------------------------------------------------------------------
class PlayerController:
    def __init__(self, app):
        self.app = app
        self.store = Store(app.user_data_dir)
        self.songs = []
        self.queue = []
        self.queue_index = -1
        self.shuffle = False
        self.repeat = 'off'  # off | one | all
        self.player = AudioPlayer(on_complete=self.on_song_complete)
        self.crossfade_secs = self.store.get_eq().get('crossfade', 4)
        self.current_song = None
        self._poll_event = None

    def load_library(self):
        self.songs = sort_songs(scan_library())
        return self.songs

    def play_list(self, songs, start_index=0):
        self.queue = list(songs)
        self.queue_index = start_index
        self._play_current()

    def _play_current(self):
        if not (0 <= self.queue_index < len(self.queue)):
            return
        song = self.queue[self.queue_index]
        self.current_song = song
        ok = self.player.load(song.path)
        if ok:
            self.player.play()
            self.store.log_play(song.path)
            if self.app.now_playing_screen:
                self.app.now_playing_screen.on_new_song(song)

    def toggle_play_pause(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def next_song(self):
        if not self.queue:
            return
        if self.repeat == 'one':
            self._play_current()
            return
        if self.shuffle:
            import random
            self.queue_index = random.randrange(len(self.queue))
        else:
            self.queue_index += 1
            if self.queue_index >= len(self.queue):
                if self.repeat == 'all':
                    self.queue_index = 0
                else:
                    self.queue_index = len(self.queue) - 1
                    return
        self._play_current()

    def prev_song(self):
        if not self.queue:
            return
        self.queue_index = max(0, self.queue_index - 1)
        self._play_current()

    def on_song_complete(self):
        Clock.schedule_once(lambda dt: self.next_song(), 0)

    def toggle_favorite(self, song):
        self.store.toggle_favorite(song.path)

    def open_song_menu(self, song):
        self.app.open_song_menu(song)

    def add_to_queue(self, song):
        self.queue.append(song)

    def set_volume(self, v):
        self.player.set_volume(v)


# ---------------------------------------------------------------------------
# Pantallas
# ---------------------------------------------------------------------------
class LibraryScreen(Screen):
    def on_pre_enter(self):
        if not hasattr(self, 'built'):
            self.built = True
            self._build_ui()
            self.refresh()

    def _build_ui(self):
        root = BoxLayout(orientation='vertical')

        top = BoxLayout(size_hint_y=None, height=50, padding=(10, 5), spacing=8)
        self.search_input = TextInput(hint_text='Buscar canción o artista', multiline=False,
                                       background_color=(0.18, 0.18, 0.2, 1), foreground_color=(1, 1, 1, 1))
        self.search_input.bind(text=lambda i, v: self.refresh())
        sort_btn = Button(text='Ordenar', size_hint_x=None, width=90,
                           background_color=(0.2, 0.2, 0.22, 1))
        sort_btn.bind(on_press=self.cycle_sort)
        top.add_widget(self.search_input)
        top.add_widget(sort_btn)
        root.add_widget(top)

        self.sort_mode = 'title'
        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=6, padding=(10, 4))
        self.list_box.bind(minimum_height=self.list_box.setter('height'))
        self.scroll.add_widget(self.list_box)
        root.add_widget(self.scroll)

        self.add_widget(root)

    def cycle_sort(self, *a):
        order = ['title', 'artist', 'album', 'date_added']
        i = order.index(self.sort_mode)
        self.sort_mode = order[(i + 1) % len(order)]
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        controller = app.controller
        songs = sort_songs(controller.songs, by=self.sort_mode)
        q = self.search_input.text.strip().lower()
        if q:
            songs = [s for s in songs if q in s.title.lower() or q in s.artist.lower()]

        self.list_box.clear_widgets()
        for s in songs:
            row = SongRow()
            row.title = s.title
            row.subtitle = f'{s.artist} · {s.album}'
            row.song = s
            row.controller = controller
            row.is_fav = controller.store.is_favorite(s.path)
            row.bind(on_touch_up=partial(self._maybe_play, s, songs))
            self.list_box.add_widget(row)

    def _maybe_play(self, song, songs, instance, touch):
        if instance.collide_point(*touch.pos):
            app = App.get_running_app()
            idx = songs.index(song)
            app.controller.play_list(songs, idx)
            app.go_to('nowplaying')


class NowPlayingScreen(Screen):
    title_text = StringProperty('Nada reproduciendo')
    artist_text = StringProperty('')
    lyrics_text = StringProperty('Sin letra disponible')
    position_text = StringProperty('0:00')
    duration_text = StringProperty('0:00')
    play_icon = StringProperty('>')
    fav_icon = StringProperty('+')
    shuffle_state = BooleanProperty(False)
    repeat_state = StringProperty('off')

    def on_pre_enter(self):
        if not hasattr(self, 'built'):
            self.built = True
            self._build_ui()
        Clock.unschedule(self._tick)
        Clock.schedule_interval(self._tick, 0.5)

    def on_leave(self):
        Clock.unschedule(self._tick)

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=20, spacing=10)

        self.art = Label(text='[ ♪ ]', font_size='48sp', size_hint_y=None, height=140,
                          color=(0.3, 0.75, 0.5, 1))
        root.add_widget(self.art)

        self.title_lbl = Label(text=self.title_text, font_size='20sp', bold=True,
                                color=(1, 1, 1, 1), size_hint_y=None, height=32)
        self.artist_lbl = Label(text=self.artist_text, font_size='14sp',
                                 color=(0.6, 0.6, 0.65, 1), size_hint_y=None, height=26)
        root.add_widget(self.title_lbl)
        root.add_widget(self.artist_lbl)

        self.slider = Slider(min=0, max=1, value=0, size_hint_y=None, height=30)
        self.slider.bind(on_touch_up=self._on_seek)
        root.add_widget(self.slider)

        time_row = BoxLayout(size_hint_y=None, height=20)
        self.pos_lbl = Label(text='0:00', color=(0.6, 0.6, 0.65, 1), font_size='11sp')
        self.dur_lbl = Label(text='0:00', color=(0.6, 0.6, 0.65, 1), font_size='11sp')
        time_row.add_widget(self.pos_lbl)
        time_row.add_widget(self.dur_lbl)
        root.add_widget(time_row)

        controls = BoxLayout(size_hint_y=None, height=60, spacing=10)
        prev_btn = Button(text='<<', background_color=(0.15, 0.15, 0.17, 1))
        prev_btn.bind(on_press=lambda i: App.get_running_app().controller.prev_song())
        self.play_btn = Button(text='>', background_color=(0.10, 0.55, 0.35, 1))
        self.play_btn.bind(on_press=self._toggle_play)
        next_btn = Button(text='>>', background_color=(0.15, 0.15, 0.17, 1))
        next_btn.bind(on_press=lambda i: App.get_running_app().controller.next_song())
        controls.add_widget(prev_btn)
        controls.add_widget(self.play_btn)
        controls.add_widget(next_btn)
        root.add_widget(controls)

        vol_row = BoxLayout(size_hint_y=None, height=40, spacing=8)
        vol_row.add_widget(Label(text='Vol', size_hint_x=None, width=36, color=(0.6, 0.6, 0.65, 1)))
        self.vol_slider = Slider(min=0, max=1, value=1)
        self.vol_slider.bind(value=self._on_volume)
        vol_row.add_widget(self.vol_slider)
        root.add_widget(vol_row)

        extra = BoxLayout(size_hint_y=None, height=44, spacing=8)
        self.shuffle_btn = Button(text='Aleatorio', background_color=(0.15, 0.15, 0.17, 1))
        self.shuffle_btn.bind(on_press=self._toggle_shuffle)
        self.repeat_btn = Button(text='Repetir: no', background_color=(0.15, 0.15, 0.17, 1))
        self.repeat_btn.bind(on_press=self._cycle_repeat)
        self.fav_btn = Button(text='+', size_hint_x=None, width=44, background_color=(0.15, 0.15, 0.17, 1))
        self.fav_btn.bind(on_press=self._toggle_fav)
        extra.add_widget(self.shuffle_btn)
        extra.add_widget(self.repeat_btn)
        extra.add_widget(self.fav_btn)
        root.add_widget(extra)

        self.lyrics_lbl = Label(text=self.lyrics_text, color=(0.7, 0.85, 0.75, 1),
                                 size_hint_y=None, height=80, halign='center', valign='middle')
        self.lyrics_lbl.bind(size=lambda i, v: setattr(i, 'text_size', v))
        root.add_widget(self.lyrics_lbl)

        self.add_widget(root)

    def on_new_song(self, song):
        self.title_lbl.text = song.title
        self.artist_lbl.text = f'{song.artist} · {song.album}'
        self.play_btn.text = '||'
        controller = App.get_running_app().controller
        self.fav_btn.text = '<3' if controller.store.is_favorite(song.path) else '+'
        self.fav_btn.color = (0.9, 0.25, 0.35, 1) if controller.store.is_favorite(song.path) else (1, 1, 1, 1)

        kind, data = load_lyrics(song.path)
        self._lrc = data if kind == 'synced' else None
        if kind == 'plain':
            self.lyrics_lbl.text = data[:600]
        elif kind is None:
            self.lyrics_lbl.text = 'Sin letra disponible'
            self._lrc = None
        else:
            self.lyrics_lbl.text = ''

    def _toggle_play(self, *a):
        controller = App.get_running_app().controller
        controller.toggle_play_pause()
        self.play_btn.text = '||' if controller.player.is_playing() else '>'

    def _toggle_shuffle(self, *a):
        controller = App.get_running_app().controller
        controller.shuffle = not controller.shuffle
        self.shuffle_btn.text = 'Aleatorio: si' if controller.shuffle else 'Aleatorio'

    def _cycle_repeat(self, *a):
        controller = App.get_running_app().controller
        order = ['off', 'all', 'one']
        i = order.index(controller.repeat)
        controller.repeat = order[(i + 1) % len(order)]
        labels = {'off': 'Repetir: no', 'all': 'Repetir: lista', 'one': 'Repetir: 1'}
        self.repeat_btn.text = labels[controller.repeat]

    def _toggle_fav(self, *a):
        controller = App.get_running_app().controller
        if controller.current_song:
            controller.toggle_favorite(controller.current_song)
            fav = controller.store.is_favorite(controller.current_song.path)
            self.fav_btn.text = '<3' if fav else '+'
            self.fav_btn.color = (0.9, 0.25, 0.35, 1) if fav else (1, 1, 1, 1)

    def _on_volume(self, instance, value):
        App.get_running_app().controller.set_volume(value)

    def _on_seek(self, instance, touch):
        if instance.collide_point(*touch.pos):
            controller = App.get_running_app().controller
            ms = instance.value * controller.player.get_duration()
            controller.player.seek(ms)

    def _fmt(self, ms):
        s = int(ms / 1000)
        return f'{s // 60}:{s % 60:02d}'

    def _tick(self, dt):
        controller = App.get_running_app().controller
        dur = controller.player.get_duration()
        pos = controller.player.get_position()
        if dur:
            self.slider.max = dur
            self.slider.value = pos
        self.pos_lbl.text = self._fmt(pos)
        self.dur_lbl.text = self._fmt(dur)

        if getattr(self, '_lrc', None):
            idx = current_line_index(self._lrc, pos / 1000)
            if 0 <= idx < len(self._lrc):
                self.lyrics_lbl.text = self._lrc[idx][1]


class PlaylistsScreen(Screen):
    def on_pre_enter(self):
        if not hasattr(self, 'built'):
            self.built = True
            self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=10, spacing=8)
        new_btn = Button(text='+ Nueva lista', size_hint_y=None, height=48,
                          background_color=(0.10, 0.55, 0.35, 1))
        new_btn.bind(on_press=self._new_playlist_popup)
        root.add_widget(new_btn)

        self.scroll = ScrollView()
        self.box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=8, padding=(4, 4))
        self.box.bind(minimum_height=self.box.setter('height'))
        self.scroll.add_widget(self.box)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def refresh(self):
        controller = App.get_running_app().controller
        self.box.clear_widgets()

        smart = [
            ('Favoritos', controller.store.favorite_songs(controller.songs)),
            ('Mas escuchadas', controller.store.most_played(controller.songs)),
            ('Agregadas recientemente', controller.store.recently_added(controller.songs)),
            ('Escuchadas recientemente', controller.store.recently_played(controller.songs)),
        ]
        self.box.add_widget(Label(text='Listas inteligentes', bold=True, color=(1, 1, 1, 1),
                                   size_hint_y=None, height=28, halign='left'))
        for name, songs in smart:
            self.box.add_widget(self._playlist_button(name, songs, deletable=False))

        self.box.add_widget(Label(text='Mis listas', bold=True, color=(1, 1, 1, 1),
                                   size_hint_y=None, height=28, halign='left'))
        for name, paths in controller.store.data['playlists'].items():
            songs = [s for s in controller.songs if s.path in paths]
            self.box.add_widget(self._playlist_button(name, songs, deletable=True))

    def _playlist_button(self, name, songs, deletable):
        row = BoxLayout(size_hint_y=None, height=54, spacing=6)
        btn = Button(text=f'{name} ({len(songs)})', background_color=(0.16, 0.16, 0.18, 1))
        btn.bind(on_press=lambda i: self._play_playlist(songs))
        row.add_widget(btn)
        if deletable:
            del_btn = Button(text='x', size_hint_x=None, width=40,
                              background_color=(0.16, 0.16, 0.18, 1))
            del_btn.bind(on_press=lambda i: self._delete_playlist(name))
            row.add_widget(del_btn)
        return row

    def _play_playlist(self, songs):
        if songs:
            App.get_running_app().controller.play_list(songs, 0)
            App.get_running_app().go_to('nowplaying')

    def _delete_playlist(self, name):
        App.get_running_app().controller.store.remove_playlist(name)
        self.refresh()

    def _new_playlist_popup(self, *a):
        layout = BoxLayout(orientation='vertical', spacing=10, padding=15)
        name_input = TextInput(hint_text='Nombre de la lista', multiline=False, size_hint_y=None, height=44)
        layout.add_widget(name_input)
        btn_row = BoxLayout(size_hint_y=None, height=48, spacing=10)
        save_btn = Button(text='Crear')
        cancel_btn = Button(text='Cancelar')
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(save_btn)
        layout.add_widget(btn_row)
        popup = Popup(title='Nueva lista', content=layout, size_hint=(0.85, 0.35))

        def do_save(i):
            n = name_input.text.strip()
            if n:
                App.get_running_app().controller.store.create_playlist(n)
                self.refresh()
            popup.dismiss()

        save_btn.bind(on_press=do_save)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()


class EqualizerScreen(Screen):
    def on_pre_enter(self):
        if not hasattr(self, 'built'):
            self.built = True
            self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = BoxLayout(orientation='vertical', padding=16, spacing=10)
        root.add_widget(Label(text='Ecualizador', bold=True, font_size='18sp',
                               color=(1, 1, 1, 1), size_hint_y=None, height=32))

        self.info_lbl = Label(text='', color=(0.7, 0.7, 0.75, 1), size_hint_y=None, height=40)
        root.add_widget(self.info_lbl)

        preset_row = BoxLayout(size_hint_y=None, height=42, spacing=6)
        for name in ['Normal', 'Rock', 'Pop', 'Jazz', 'Bass Boost', 'Vocal']:
            b = Button(text=name, font_size='10sp', background_color=(0.16, 0.16, 0.18, 1))
            b.bind(on_press=partial(self._apply_preset, name))
            preset_row.add_widget(b)
        root.add_widget(preset_row)

        self.bands_box = BoxLayout(size_hint_y=None, height=220, spacing=6)
        root.add_widget(self.bands_box)

        cross_row = BoxLayout(size_hint_y=None, height=40, spacing=8)
        cross_row.add_widget(Label(text='Crossfade (seg)', color=(0.7, 0.7, 0.75, 1)))
        self.cross_slider = Slider(min=0, max=10, value=4)
        self.cross_slider.bind(value=self._on_crossfade)
        cross_row.add_widget(self.cross_slider)
        root.add_widget(cross_row)

        self.add_widget(root)

    def refresh(self):
        controller = App.get_running_app().controller
        eq = controller.player.equalizer
        self.bands_box.clear_widgets()
        if eq and eq.available:
            self.info_lbl.text = f'{eq.num_bands} bandas disponibles (dispositivo real)'
            for i in range(eq.num_bands):
                col = BoxLayout(orientation='vertical')
                s = Slider(min=eq.band_range[0], max=eq.band_range[1],
                           value=eq.get_band_level(i), orientation='vertical')
                s.bind(value=partial(self._on_band, i))
                freq_lbl = Label(text=f'{eq.get_center_freq(i)}Hz', font_size='9sp',
                                  size_hint_y=None, height=18, color=(0.6, 0.6, 0.65, 1))
                col.add_widget(s)
                col.add_widget(freq_lbl)
                self.bands_box.add_widget(col)
        else:
            self.info_lbl.text = ('El ecualizador real solo funciona reproduciendo\n'
                                   'una canción en el teléfono (no en escritorio).')

    def _on_band(self, band, instance, value):
        controller = App.get_running_app().controller
        eq = controller.player.equalizer
        if eq:
            eq.set_band_level(band, value)

    def _apply_preset(self, name, *a):
        controller = App.get_running_app().controller
        eq = controller.player.equalizer
        if eq:
            eq.use_preset(name)
            self.refresh()

    def _on_crossfade(self, instance, value):
        controller = App.get_running_app().controller
        controller.crossfade_secs = value


class HistoryScreen(Screen):
    def on_pre_enter(self):
        if not hasattr(self, 'built'):
            self.built = True
            root = BoxLayout(orientation='vertical', padding=10)
            self.scroll = ScrollView()
            self.box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=6)
            self.box.bind(minimum_height=self.box.setter('height'))
            self.scroll.add_widget(self.box)
            root.add_widget(self.scroll)
            self.add_widget(root)
        self.refresh()

    def refresh(self):
        controller = App.get_running_app().controller
        by_path = {s.path: s for s in controller.songs}
        self.box.clear_widgets()
        for entry in controller.store.data['history'][:100]:
            song = by_path.get(entry['path'])
            if song:
                self.box.add_widget(Label(text=f'{song.title} - {song.artist}',
                                           color=(1, 1, 1, 1), size_hint_y=None, height=32))


# ---------------------------------------------------------------------------
# App raíz
# ---------------------------------------------------------------------------
class RootScreen(Screen):
    pass


class MusicApp(App):
    now_playing_screen = None

    def build(self):
        Window.clearcolor = (0.07, 0.07, 0.08, 1)
        Builder.load_string(KV)
        self.controller = PlayerController(self)

        self.sm_inner = ScreenManager(transition=NoTransition())
        self.library_screen = LibraryScreen(name='library')
        self.now_playing_screen = NowPlayingScreen(name='nowplaying')
        self.playlists_screen = PlaylistsScreen(name='playlists')
        self.eq_screen = EqualizerScreen(name='eq')
        self.history_screen = HistoryScreen(name='history')
        for s in (self.library_screen, self.now_playing_screen, self.playlists_screen,
                  self.eq_screen, self.history_screen):
            self.sm_inner.add_widget(s)

        root = BoxLayout(orientation='vertical')
        root.add_widget(self.sm_inner)

        nav = BoxLayout(size_hint_y=None, height=56, spacing=2, padding=2)
        tabs = [('library', 'Biblioteca'), ('nowplaying', 'Reproduciendo'),
                ('playlists', 'Listas'), ('eq', 'EQ'), ('history', 'Historial')]
        for name, label in tabs:
            btn = self._make_tab(name, label)
            nav.add_widget(btn)
        root.add_widget(nav)

        Clock.schedule_once(lambda dt: self._load_library_async(), 0.3)

        outer = ScreenManager()
        rs = RootScreen(name='root')
        rs.add_widget(root)
        outer.add_widget(rs)
        return outer

    def _make_tab(self, name, label):
        from kivy.factory import Factory
        btn = Factory.TabBtn(text=label)
        if name == 'library':
            btn.state = 'down'
        btn.bind(on_press=lambda i: self.go_to(name))
        return btn

    def go_to(self, name):
        self.sm_inner.current = name

    def _load_library_async(self):
        self.controller.load_library()
        self.library_screen.built = False
        if self.library_screen.manager:
            self.library_screen.on_pre_enter()
        else:
            self.library_screen._build_ui() if not hasattr(self.library_screen, 'built') else None

    def open_song_menu(self, song):
        layout = BoxLayout(orientation='vertical', spacing=10, padding=15)

        add_row = BoxLayout(size_hint_y=None, height=44, spacing=6)
        pl_input = TextInput(hint_text='Agregar a lista (nombre)', multiline=False)
        add_row.add_widget(pl_input)
        add_btn = Button(text='Agregar', size_hint_x=None, width=90)
        add_row.add_widget(add_btn)
        layout.add_widget(add_row)

        edit_lbl = Label(text='Editar metadatos', bold=True, color=(1, 1, 1, 1),
                          size_hint_y=None, height=26)
        layout.add_widget(edit_lbl)

        title_in = TextInput(text=song.title, hint_text='Titulo', multiline=False,
                              size_hint_y=None, height=40)
        artist_in = TextInput(text=song.artist, hint_text='Artista', multiline=False,
                               size_hint_y=None, height=40)
        album_in = TextInput(text=song.album, hint_text='Album', multiline=False,
                              size_hint_y=None, height=40)
        layout.add_widget(title_in)
        layout.add_widget(artist_in)
        layout.add_widget(album_in)

        btn_row = BoxLayout(size_hint_y=None, height=48, spacing=10)
        save_btn = Button(text='Guardar cambios')
        close_btn = Button(text='Cerrar')
        btn_row.add_widget(close_btn)
        btn_row.add_widget(save_btn)
        layout.add_widget(btn_row)

        popup = Popup(title=song.title, content=layout, size_hint=(0.9, 0.65))

        def do_add(i):
            name = pl_input.text.strip()
            if name:
                self.controller.store.add_to_playlist(name, song.path)

        def do_save(i):
            try:
                from mutagen.easyid3 import EasyID3
                audio = EasyID3(song.path)
            except Exception:
                try:
                    from mutagen import File as MutagenFile
                    audio = MutagenFile(song.path, easy=True)
                    if audio.tags is None:
                        audio.add_tags()
                except Exception:
                    audio = None
            if audio is not None:
                try:
                    audio['title'] = title_in.text
                    audio['artist'] = artist_in.text
                    audio['album'] = album_in.text
                    audio.save()
                    song.title = title_in.text
                    song.artist = artist_in.text
                    song.album = album_in.text
                except Exception:
                    pass
            self.library_screen.refresh()
            popup.dismiss()

        add_btn.bind(on_press=do_add)
        save_btn.bind(on_press=do_save)
        close_btn.bind(on_press=popup.dismiss)
        popup.open()


if __name__ == '__main__':
    MusicApp().run()
