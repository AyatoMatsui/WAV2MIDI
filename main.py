from kivy.app import App
from kivy.lang import Builder

from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.audio import SoundLoader
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.config import Config
from kivy.utils import DEPRECATED_CALLERS
Config.set("graphics", "resizable", False)
Config.set("graphics", "width", 600)
Config.set("graphics", "height", 480)

import numpy as np
import librosa

import mido
from mido import Message, MidiFile, MidiTrack, MetaMessage


Window.size = [360,640]
SAMPLE_RATE = 8000

# Create both screens. Please note the root.manager.current: this is how
# you can control the ScreenManager from kv. Each screen has by default a
# property manager that gives you the instance of the ScreenManager used.

Builder.load_file('ui.kv')


class WavListScreen(Screen):
    flag = True
    flag2 = True
    filetext = StringProperty()
    playtext = StringProperty()
    converttext = StringProperty()
    hop_length = NumericProperty() # 1フレーム出力あたりに必要なサンプル量
    disabled = BooleanProperty()
    # tempo_list = [30, 36, 40, 45, 50, 60, 72, 75, 90, 100, 120, 125, 150, 180, 200, 225, 300]
    tempo = NumericProperty() # 音のテンポ
    tempo_index = NumericProperty(100)
    
    color = ListProperty([0.5, 0.5, 0.5, 1.0])
    color2 = ListProperty([0.5, 0.5, 0.5, 1.0])
    color3 = ListProperty([0.5, 0.5, 0.5, 1.0])

    sound = SoundLoader.load('')
    tik = SoundLoader.load('clock_cut.wav')

    def __init__(self, **kwargs):
        super(WavListScreen, self).__init__(**kwargs)
        self.filetext = 'wavfile?'
        self.playtext = 'play'
        self.converttext = 'WAV2MIDI変換'
        self.hop_length = 16 * self.tempo_index
        self.tempo = round(abs(SAMPLE_RATE * 15 / self.hop_length), 2)
        self.disabled = False
        
        print(type(self.hop_length))

    def selected(self, filename):
        try:
            self.sound = SoundLoader.load(filename[0])
            self.filetext = filename[0]
        except IndexError:
            pass
    
    def onClickPlusMinusButton(self, num):          
        self.tempo_index -= num
        self.hop_length = 16 * self.tempo_index
        self.tempo = round(abs(SAMPLE_RATE * 15 / self.hop_length), 2)

    def onClickPlayButton(self):
        print('PlayToggle Changed to', self.flag,'!')

        if self.flag == True:
            if self.sound:
                self.playtext = 'stop'
                self.color = [1.0, 0.3, 0.3, 1.0]
                self.sound.play()
            else:
                self.playtext = 'file not found...'
                self.flag = not self.flag
        else:
            self.playtext = 'play'
            self.color = [0.5, 0.5, 0.5, 1.0]
            if self.sound:
                self.sound.stop()

        self.flag = not self.flag
        
    
    def tiktak(self, *args):
        if self.tik:
            self.tik.play()
        
        
    def onClickClockButton(self):
        print('PlayToggle Changed to', self.flag,'!')

        if self.flag2 == True:
            self.color2 = [1.0, 0.3, 0.3, 1.0]
            self.event = Clock.schedule_interval(self.tiktak, 60/self.tempo)
        else:
            self.color2 = [0.5, 0.5, 0.5, 1.0]
            self.event.cancel()
            
        # self.disabled = not self.disabled
        self.flag2 = not self.flag2
        
    
    def onClickConvertButton(self):
        if self.sound:
            '''
            Convert Wave to Chromagram with Librosa
            '''
            # 変換中はボタンの色とテキストを変換させておく
            self.converttext = '変換中'
            self.color3 = [0.3, 1.0, 0.3, 1.0]
            
            y, sr = librosa.load(self.filetext, sr=SAMPLE_RATE)
            # 各パラメータの値の設定
            # hop_length は5オクターブの場合だと16の整数倍である必要があるらしいです！
            hop_length = self.hop_length # CQTのサンプル数(ここがクロックの速さに応じて可変になる)(デフォルト値は512)(計算方法は紙の計算式にて)           
            fmin = librosa.note_to_hz('C1') # 最低音階
            bins_per_octave = 12 # 1オクターブ12音階
            octaves = 5 # オクターブ数
            n_bins = bins_per_octave * octaves # 音階の個数
            window = 'hamming' # 窓関数のモデル(今回はハミング窓。ハン窓('hann')や三角窓('triang')もあり
            print('hop_length: ', hop_length)
            
            chroma_cqt = np.abs(librosa.cqt(
                y, sr=sr, hop_length=hop_length, fmin=fmin, n_bins=n_bins, 
                bins_per_octave=bins_per_octave, window=window))
            
            # 歯擦音の軽減をするために最後のオクターブを10dBほど軽減する
            # (アンプの状態では0.3倍するだけでおおよそ近くなる)
            for num in range(n_bins - (2*bins_per_octave), n_bins):
                chroma_cqt[num] *= 0.3
            
            pitch_list = [] # 各フレームごとの音階
            midi_list = [] # 音階の長さリスト
            tmp_pitch = 0 # 一時的に保存する音階
            count = 1 # 音階の長さ
            print(type(chroma_cqt), len(chroma_cqt))
            chroma_cqt_T = chroma_cqt.T
            for x in chroma_cqt_T:
                # フレームごとの音階をリスト化する
                pitch_list.append(np.argmax(x))
                
                # 音階化したリストについて、音階の長さを調べ、
                # 音階が続けば長さを加え、違う音程になれば出力する
                if np.argmax(x) == tmp_pitch:
                    count += 1
                else:
                    midi_list.append([tmp_pitch, count])
                    tmp_pitch = np.argmax(x)
                    count = 1
            # 最後の音階を出力する
            midi_list.append([tmp_pitch, count])
            # 最初の音階は高さ0なので排外する
            midi_list.remove(midi_list[0])
            
            
            print('len(pitch_list): ', len(pitch_list))
            print('pitch_list: ', pitch_list)
            print('len(midi_list): ', len(midi_list))
            print('midi_list: ', midi_list)
            print('Convert Done!!!')
            
            
            '''
            Save Midi with Mido
            '''
            
            mid = MidiFile()
            track = MidiTrack()
            mid.tracks.append(track)
            track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(120)))
            for note in midi_list:
                track.append(Message('note_on', note=note[0]+36, velocity=127, time=0))
                track.append(Message('note_off', note=note[0]+36, time=120*note[1]))

            mid.save(self.filetext+'.mid') # 元の音声ファイル名+.mid
            
            # 変換後にボタンの色とテキストを元に戻しておく
            self.converttext = 'WAV2MIDI変換'
            self.color3 = [0.5, 0.5, 0.5, 1.0]
            
        else:
            self.playtext = 'file not found...'


class TestApp(App):

    def build(self):
        # Create the screen manager
        sm = ScreenManager()
        sm.add_widget(WavListScreen(name='wav_list'))

        return sm


if __name__ == '__main__':
    TestApp().run()