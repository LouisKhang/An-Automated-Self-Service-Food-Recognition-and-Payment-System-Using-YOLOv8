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
        """Khởi tạo audio manager"""
        self.is_enabled = self._check_pyaudio_available()
        if not self.is_enabled:
            print("⚠️  PyAudio không được cài đặt. Chức năng beep sẽ bị vô hiệu hóa.")
            print("    Để bật: pip install pyaudio")
    
    @staticmethod
    def _check_pyaudio_available():
        """Kiểm tra pyaudio có sẵn không"""
        try:
            import pyaudio
            return True
        except ImportError:
            return False
    
    @staticmethod
    def generate_beep_wave(frequency=440, duration=0.2, volume=0.5, sample_rate=44100):
        """
        Tạo sóng âm thanh beep
        
        Args:
            frequency: Tần số (Hz) - 440 Hz là A4
            duration: Độ dài (giây)
            volume: Âm lượng (0.0 - 1.0)
            sample_rate: Tốc độ lấy mẫu (Hz)
        
        Returns:
            Numpy array của mẫu âm thanh
        """
        samples = np.arange(sample_rate * duration)
        wave_data = np.sin(2 * np.pi * frequency * samples / sample_rate)
        wave_data = (wave_data * volume * 32767).astype(np.int16)
        return wave_data.tobytes()
    
    def play_beep(self, frequency=440, duration=0.2, volume=0.5):
        """
        Phát tiếng beep
        
        Args:
            frequency: Tần số (Hz) - 440 là A4, 600 là cao hơn
            duration: Độ dài (giây)
            volume: Âm lượng (0.0 - 1.0)
        """
        if not self.is_enabled:
            return
        
        # Chạy trong thread riêng để không block UI
        thread = threading.Thread(
            target=self._play_beep_thread,
            args=(frequency, duration, volume),
            daemon=True
        )
        thread.start()
    
    def play_success_beep(self):
        """Phát beep xác nhận phát hiện thành công (2 beep ngắn)"""
        if not self.is_enabled:
            return
        
        thread = threading.Thread(
            target=self._play_success_beep_thread,
            daemon=True
        )
        thread.start()
    
    def _play_beep_thread(self, frequency, duration, volume):
        """Thread để phát beep"""
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
    
    def _play_success_beep_thread(self):
        """Phát 2 beep ngắn để xác nhận"""
        try:
            # Beep 1
            self._play_beep_thread(600, 0.15, 0.6)
            import time
            time.sleep(0.2)
            # Beep 2
            self._play_beep_thread(600, 0.15, 0.6)
        except Exception as e:
            print(f"⚠️  Lỗi phát success beep: {e}")


# Global instance
audio_manager = AudioManager()


def play_beep(frequency=440, duration=0.2, volume=0.5):
    """Helper function - phát beep"""
    audio_manager.play_beep(frequency, duration, volume)


def play_success_beep():
    """Helper function - phát beep xác nhận"""
    audio_manager.play_success_beep()

