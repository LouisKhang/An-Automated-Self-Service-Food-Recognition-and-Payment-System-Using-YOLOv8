"""
Audio utilities - Phát tín hiệu âm thanh (beep) để thông báo
"""

import threading
import numpy as np
import wave
import io


class AudioManager:
    """Quản lý âm thanh - phát beep thông báo"""
    
    def __init__(self):
        self.is_enabled = self._check_pyaudio_available()
        self._beep_lock = threading.Lock()  # FIX: chỉ 1 stream tại 1 thời điểm
        if not self.is_enabled:
            print("⚠️  PyAudio không được cài đặt. Chức năng beep sẽ bị vô hiệu hóa.")
            print("    Để bật: pip install pyaudio")
    
    @staticmethod
    def _check_pyaudio_available():
        try:
            import pyaudio
            return True
        except ImportError:
            return False
    
    @staticmethod
    def generate_beep_wave(frequency=440, duration=0.2, volume=0.5, sample_rate=44100):
        samples = np.arange(sample_rate * duration)
        wave_data = np.sin(2 * np.pi * frequency * samples / sample_rate)
        wave_data = (wave_data * volume * 32767).astype(np.int16)
        return wave_data.tobytes()
    
    def play_beep(self, frequency=440, duration=0.2, volume=0.5):
        if not self.is_enabled:
            return
        thread = threading.Thread(
            target=self._play_beep_thread,
            args=(frequency, duration, volume),
            daemon=True
        )
        thread.start()
    
    def play_success_beep(self):
        if not self.is_enabled:
            return
        thread = threading.Thread(
            target=self._play_success_beep_thread,
            daemon=True
        )
        thread.start()
    
    def _play_beep_thread(self, frequency, duration, volume):
        # FIX: acquire non-blocking — bỏ qua nếu đang có beep khác chạy
        if not self._beep_lock.acquire(blocking=False):
            return
        try:
            if not self.is_enabled:
                return
            import pyaudio
            sample_rate = 44100
            wave_data = self.generate_beep_wave(frequency, duration, volume, sample_rate)
            p = pyaudio.PyAudio()
            try:
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=sample_rate,
                    output=True
                )
                stream.write(wave_data)
                stream.stop_stream()
                stream.close()
            finally:
                p.terminate()
        except Exception as e:
            print(f"⚠️  Lỗi phát beep: {e}")
        finally:
            self._beep_lock.release()  # FIX: luôn release dù có lỗi
    
    def _play_success_beep_thread(self):
        # FIX: acquire non-blocking — bỏ qua nếu đang beep
        if not self._beep_lock.acquire(blocking=False):
            return
        try:
            import pyaudio, time
            sample_rate = 44100

            def _play_once(freq, dur, vol):
                wave_data = self.generate_beep_wave(freq, dur, vol, sample_rate)
                p = pyaudio.PyAudio()
                try:
                    stream = p.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=sample_rate,
                        output=True
                    )
                    stream.write(wave_data)
                    stream.stop_stream()
                    stream.close()
                finally:
                    p.terminate()

            _play_once(600, 0.15, 0.6)
            time.sleep(0.2)
            _play_once(600, 0.15, 0.6)
        except Exception as e:
            print(f"⚠️  Lỗi phát success beep: {e}")
        finally:
            self._beep_lock.release()


# Global instance
audio_manager = AudioManager()


def play_beep(frequency=440, duration=0.2, volume=0.5):
    audio_manager.play_beep(frequency, duration, volume)


def play_success_beep():
    audio_manager.play_success_beep()