import sys
import os
import subprocess
import json
from tkinter import filedialog, messagebox

from io import StringIO

class NullWriter(StringIO):
    def write(self, s):
        pass  

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

import customtkinter as ctk
import threading
import re
from pathlib import Path
import pygame
import time
import queue
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from pydub.effects import normalize, high_pass_filter, compress_dynamic_range
import tempfile
import torch
import torchaudio
from demucs import pretrained
from demucs.apply import apply_model

class MusicStemTool(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Music Stem Separator (Demucs)")
        self.geometry("950x800")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        self.output_dir = self.load_config().get("output_dir", os.path.join(os.path.expanduser("~"), "MusicStems"))
        self.is_processing = False
        self.current_theme = "dark"
        self.current_stems = {}
        self.playing = False
        self.paused = False
        self.audio_length = 0
        self.current_position = 0
        self.sr = None
        self.stem_audio = {}
        self.play_mode = None  
        self.local_file = None
        
        self.update_queue = queue.Queue()
        
        pygame.mixer.init()
        pygame.mixer.set_num_channels(32)
        
        self._temp_mixed_file = None
        
        self.setup_ui()
        self.process_updates()
        
    def format_time(self, s):
        m, sec = divmod(int(s), 60)
        return f"{m}:{sec:02d}"
        
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_config(self):
        config = {"output_dir": self.output_dir}
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except:
            pass
        
    def process_updates(self):
        updated = False
        while True:
            try:
                msg = self.update_queue.get_nowait()
                updated = True
                msg_type = msg['type']
                if msg_type == 'progress':
                    self.progress_bar.set(msg['percent'] / 100)
                    self.progress_info.configure(text=msg['info_text'])
                elif msg_type == 'info':
                    self.progress_info.configure(text=msg['text'])
                elif msg_type == 'btn_disable':
                    self.download_btn.configure(state="disabled", text=msg['text'])
                elif msg_type == 'btn_enable':
                    self.download_btn.configure(state="normal", text=msg['text'])
                elif msg_type == 'create_player':
                    if self.play_mode == "stems":
                        self.create_stem_player_ui()
                    self.player_section.pack(fill="x", pady=(0, 15))
                elif msg_type == 'reset_progress':
                    self.progress_bar.set(0)
                elif msg_type == 'player_progress':
                    pos = msg['position']
                    total = self.audio_length if self.audio_length > 0 else 1
                    self.time_label.configure(text=f"{self.format_time(pos)} / {self.format_time(self.audio_length)}")
                    try:
                        self.player_seek_slider.set(pos / total)
                    except:
                        pass
            except queue.Empty:
                break
        if updated:
            self.update_idletasks()
        self.after(50, self.process_updates)
        
    def stop_playback(self):
        if self.play_mode == "stems":
            self.stop_stems()
        elif self.play_mode == "local":
            self.stop_local()
        
    def setup_ui(self):
        main_frame = ctk.CTkFrame(self, corner_radius=0)
        main_frame.pack(fill="both", expand=True)
        
        header_frame = ctk.CTkFrame(main_frame, fg_color=("gray85", "gray20"), corner_radius=0)
        header_frame.pack(fill="x", pady=0)
        
        title_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_container.pack(fill="x", padx=20, pady=15)
        
        title = ctk.CTkLabel(
            title_container, 
            text="🎵 Music Stem Separator (Demucs)",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title.pack(side="left")
        
        self.theme_btn = ctk.CTkButton(
            title_container,
            text="☀️ Light Mode",
            width=100,
            height=35,
            command=self.toggle_theme,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.theme_btn.pack(side="right")
        
        scroll_frame = ctk.CTkScrollableFrame(main_frame, corner_radius=0)
        scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        content = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        url_section = self.create_section(content, "🔗 Source URL(s)")
        
        self.url_entry = ctk.CTkTextbox(
            url_section,
            height=80,
            font=ctk.CTkFont(size=13),
            corner_radius=10
        )
        self.url_entry.pack(fill="x", padx=15, pady=(5, 10))
        self.url_entry.insert("1.0", "Paste YouTube/SoundCloud URLs here (one per line for batch)")
        
        quality_section = self.create_section(content, "🎚️ Audio Quality")
        
        self.quality_var = ctk.StringVar(value="320")
        quality_container = ctk.CTkFrame(quality_section, fg_color="transparent")
        quality_container.pack(fill="x", padx=15, pady=(5, 15))
        
        qualities = [("128kbps", "128", "📻"), ("192kbps", "192", "📀"), ("320kbps", "320", "💎")]
        
        for label, value, icon in qualities:
            ctk.CTkRadioButton(
                quality_container,
                text=f"{icon} {label}",
                variable=self.quality_var,
                value=value,
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(side="left", expand=True, padx=5)
        
        mode_section = self.create_section(content, "⚙️ Processing Mode")
        
        self.mode_var = ctk.StringVar(value="download_separate")
        mode_container = ctk.CTkFrame(mode_section, fg_color="transparent")
        mode_container.pack(fill="x", padx=15, pady=(5, 15))
        
        modes = [
            ("Download + Separate", "download_separate", "🎼"),
            ("Download Only", "download_only", "📥")
        ]
        
        for label, value, icon in modes:
            ctk.CTkRadioButton(
                mode_container,
                text=f"{icon} {label}",
                variable=self.mode_var,
                value=value,
                font=ctk.CTkFont(size=13)
            ).pack(side="left", expand=True, padx=5)
        
        self.stem_section = self.create_section(content, "✂️ Stem Separation")
        
        stems_container = ctk.CTkFrame(self.stem_section, fg_color="transparent")
        stems_container.pack(fill="x", padx=15, pady=(5, 10))
        
        self.stem_mode_var = ctk.StringVar(value="2")
        
        stem_options = [
            ("2 Stems", "2", "🎤 Vocals + Instrumental"),
            ("4 Stems", "4", "🎼 Vocals, Drums, Bass, Other")
        ]
        
        for label, value, desc in stem_options:
            ctk.CTkRadioButton(
                stems_container,
                text=f"{label}  •  {desc}",
                variable=self.stem_mode_var,
                value=value,
                font=ctk.CTkFont(size=13)
            ).pack(anchor="w", pady=3)
        
        dir_section = self.create_section(content, "📁 Output Location")
        
        dir_container = ctk.CTkFrame(dir_section, fg_color="transparent")
        dir_container.pack(fill="x", padx=15, pady=(5, 15))
        
        self.dir_label = ctk.CTkLabel(
            dir_container,
            text=self.output_dir,
            font=ctk.CTkFont(size=12),
            anchor="w",
            fg_color=("gray80", "gray25"),
            corner_radius=8,
            height=35
        )
        self.dir_label.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(
            dir_container,
            text="📂 Browse",
            width=120,
            height=35,
            command=self.select_directory
        ).pack(side="right")
        
        progress_section = self.create_section(content, "📊 Download Progress")
        
        self.progress_bar = ctk.CTkProgressBar(
            progress_section,
            height=25,
            corner_radius=10
        )
        self.progress_bar.pack(fill="x", padx=15, pady=(5, 10))
        self.progress_bar.set(0)
        
        self.progress_info = ctk.CTkLabel(
            progress_section,
            text="Ready to download",
            font=ctk.CTkFont(size=13)
        )
        self.progress_info.pack(padx=15, pady=(0, 15))
        
        self.player_section = self.create_section(content, "🎧 Stem Player")
        self.player_section.pack_forget()
        
        button_container = ctk.CTkFrame(content, fg_color="transparent")
        button_container.pack(fill="x", pady=(10, 0))
        
        self.download_btn = ctk.CTkButton(
            button_container,
            text="▶ Start Processing",
            font=ctk.CTkFont(size=18, weight="bold"),
            height=55,
            corner_radius=15,
            command=self.start_processing,
            fg_color=("#2CC985", "#2FA572")
        )
        self.download_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))
        
        self.open_folder_btn = ctk.CTkButton(
            button_container,
            text="📁 Open Folder",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=55,
            width=180,
            corner_radius=15,
            command=self.open_output_folder
        )
        self.open_folder_btn.pack(side="right", padx=5)
        
        watermark = ctk.CTkLabel(
            content,
            text="dat514 - Demucs Edition v1.1",
            font=ctk.CTkFont(size=10),
            text_color="gray50"
        )
        watermark.pack(side="right", anchor="se", pady=(5, 0))
        
    def create_section(self, parent, title):
        section = ctk.CTkFrame(parent, corner_radius=15)
        section.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            section,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        ).pack(anchor="w", padx=15, pady=(15, 10))
        
        return section
    
    def toggle_theme(self):
        if self.current_theme == "dark":
            ctk.set_appearance_mode("light")
            self.theme_btn.configure(text="🌙 Dark Mode")
            self.current_theme = "light"
        else:
            ctk.set_appearance_mode("dark")
            self.theme_btn.configure(text="☀️ Light Mode")
            self.current_theme = "dark"
        
    def select_directory(self):
        directory = filedialog.askdirectory(initialdir=self.output_dir, title="Select output directory")
        if directory:
            self.output_dir = directory
            self.dir_label.configure(text=directory)
            self.save_config()
    
    def sanitize_filename(self, filename):
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.strip()
        return filename
            
    def update_progress(self, percent, speed="", eta=""):
        info_text = f"Progress: {percent:.1f}%"
        if speed:
            info_text += f"  |  Speed: {speed}"
        if eta:
            info_text += f"  |  ETA: {eta}"
        self.update_queue.put({'type': 'progress', 'percent': percent, 'info_text': info_text})
        
    def update_info(self, text):
        self.update_queue.put({'type': 'info', 'text': text})
        
    def disable_btn(self, text):
        self.update_queue.put({'type': 'btn_disable', 'text': text})
        
    def enable_btn(self, text):
        self.update_queue.put({'type': 'btn_enable', 'text': text})
        
    def reset_progress(self):
        self.update_queue.put({'type': 'reset_progress'})
        
    def check_dependencies(self):
        try:
            subprocess.run(["yt-dlp", "--version"], 
                         capture_output=True, check=True)
        except:
            return False, "yt-dlp not found. Install with: pip install yt-dlp"
        
        try:
            subprocess.run(["ffmpeg", "-version"], 
                         capture_output=True, check=True)
        except:
            return False, "FFmpeg not found. Install from https://ffmpeg.org"
        
        try:
            import demucs
            pretrained.get_model('htdemucs')
        except Exception as e:
            return False, f"Demucs not available: {str(e)}. Install: pip install demucs[torch]"
        
        return True, "OK"
        
    def separate_stems(self, audio_file):
        try:
            self.update_info("Starting stem separation with Demucs... (This may take a while)")
            
            stem_count = self.stem_mode_var.get()
            song_name = Path(audio_file).stem
            song_name = self.sanitize_filename(song_name)
            output_path = os.path.join(self.output_dir, song_name)
            os.makedirs(output_path, exist_ok=True)
            
            y, sample_rate = librosa.load(audio_file, sr=None, mono=False)
            if len(y.shape) == 1:
                y = np.stack([y, y])
            if sample_rate != 44100:
                y = librosa.resample(y, orig_sr=sample_rate, target_sr=44100)
                sample_rate = 44100
            waveform = torch.from_numpy(y).float()
            
            is_two_stems = stem_count == "2"
            
            if is_two_stems:
                model = pretrained.get_model('mdx_extra')
                stem_mapping = {'no_vocals': 'instrumental'}
            else:
                model = pretrained.get_model('htdemucs')
                stem_mapping = {}
            
            device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            model.to(device)
            model.eval()
            waveform = waveform.to(device)
            
            with torch.no_grad():
                sources = apply_model(model, waveform.unsqueeze(0), device=device, split=True, overlap=0.25, progress=True)[0]
            
            self.current_stems = {}
            subfolder = os.path.join(output_path, "separated 4 stems" if not is_two_stems else "separated 2 stems")
            os.makedirs(subfolder, exist_ok=True)
            
            stem_order = model.sources
            for i, stem in enumerate(stem_order):
                source_waveform = sources[i].cpu()
                
                stem_file = os.path.join(subfolder, f"{stem}.wav")
                sf.write(stem_file, source_waveform.numpy().T, sample_rate)
                
                mapped_stem = stem_mapping.get(stem, stem)
                self.current_stems[mapped_stem] = stem_file
            
            self.post_process_stems(subfolder, list(self.current_stems.keys()))
            
            self.update_info("✅ Stem separation completed!")
            self.load_stems(self.current_stems)
            
        except Exception as e:
            raise Exception(f"Stem separation error: {str(e)}")
    
    def post_process_stems(self, output_path, stems):
        for stem in stems:
            stem_file = os.path.join(output_path, f"{stem}.wav")
            if os.path.exists(stem_file):
                audio = AudioSegment.from_wav(stem_file)
                audio = high_pass_filter(audio, cutoff=80)
                audio = compress_dynamic_range(audio)
                audio = normalize(audio)
                audio.export(stem_file, format="wav")
    
    def load_stems(self, stems_dict):
        self.stem_audio = {}
        if stems_dict:
            first_path = list(stems_dict.values())[0]
            _, self.sr = librosa.load(first_path, sr=None)
            for stem, path in stems_dict.items():
                y, sr_check = librosa.load(path, sr=None)
                if sr_check != self.sr:
                    raise ValueError(f"Sample rate mismatch for {stem}")
                self.stem_audio[stem] = (y, self.sr)
            self.audio_length = len(next(iter(self.stem_audio.values()))[0]) / self.sr
            self.play_mode = "stems"
            self.update_queue.put({'type': 'create_player'})
    
    def open_local_audio(self):
        filetypes = [
            ("Audio files", "*.mp3 *.wav *.flac *.ogg"),
            ("MP3 files", "*.mp3"),
            ("WAV files", "*.wav")
        ]
        file_path = filedialog.askopenfilename(title="Select local audio file", filetypes=filetypes)
        if file_path:
            self.stop_playback()
            self.local_file = file_path
            self.play_mode = "local"
            try:
                audio = AudioSegment.from_file(file_path)
                self.audio_length = len(audio) / 1000.0
            except Exception as e:
                messagebox.showerror("Error", f"Could not load audio file: {str(e)}")
                return
            self.create_local_player_ui()
    
    def create_local_player_ui(self):
        for widget in self.player_section.winfo_children()[1:]:
            widget.destroy()
        
        player_frame = ctk.CTkFrame(self.player_section, fg_color="transparent")
        player_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        ctk.CTkLabel(
            player_frame, 
            text=os.path.basename(self.local_file), 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        control_frame = ctk.CTkFrame(player_frame, fg_color=("gray85", "gray20"), corner_radius=10)
        control_frame.pack(fill="x", pady=(10, 5))
        
        btn_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        self.play_btn = ctk.CTkButton(
            btn_frame,
            text="▶ Play",
            width=110,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#2CC985", "#2FA572"),
            command=self.play_local
        )
        self.play_btn.pack(side="left", padx=5)
        
        self.pause_btn = ctk.CTkButton(
            btn_frame,
            text="⏸ Pause",
            width=110,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.toggle_local_pause,
            state="disabled"
        )
        self.pause_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="⏹ Stop",
            width=110,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#E74C3C", "#C0392B"),
            command=self.stop_local,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)
        
        master_vol_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        master_vol_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        ctk.CTkLabel(
            master_vol_frame, 
            text="🔊 Volume:", 
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left", padx=(0, 10))
        
        self.master_volume = ctk.CTkSlider(
            master_vol_frame,
            from_=0,
            to=100,
            command=self.update_local_volume
        )
        self.master_volume.set(70)
        self.master_volume.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.master_vol_label = ctk.CTkLabel(
            master_vol_frame,
            text="70%",
            width=50,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.master_vol_label.pack(side="left")
        
        time_frame = ctk.CTkFrame(player_frame, fg_color="transparent")
        time_frame.pack(fill="x", pady=(5, 0))
        
        self.time_label = ctk.CTkLabel(
            time_frame,
            text="0:00 / 0:00",
            font=ctk.CTkFont(size=12)
        )
        self.time_label.pack(pady=(0, 5))
        
        self.player_seek_slider = ctk.CTkSlider(
            time_frame,
            from_=0,
            to=1,
            command=self.seek_to_position
        )
        self.player_seek_slider.pack(fill="x")
        self.player_seek_slider.set(0)
    
    def play_local(self):
        if self.playing:
            return
        try:
            pygame.mixer.music.load(self.local_file)
            vol = self.master_volume.get() / 100.0
            pygame.mixer.music.set_volume(vol)
            pygame.mixer.music.play()
            self.playing = True
            self.paused = False
            self.play_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal", text="⏸ Pause")
            self.stop_btn.configure(state="normal")
            threading.Thread(target=self.update_local_position, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"Could not play audio: {str(e)}")
    
    def update_local_position(self):
        while self.playing:
            pos_ms = pygame.mixer.music.get_pos()
            pos = pos_ms / 1000.0 if pos_ms >= 0 else self.current_position
            if self.play_mode == "local":
                self.update_queue.put({'type': 'player_progress', 'position': pos})
                if not self.paused and pos >= self.audio_length - 0.1:
                    self.stop_local()
                    break
            time.sleep(0.2)
    
    def update_local_volume(self, value):
        vol = float(value) / 100.0
        pygame.mixer.music.set_volume(vol)
        self.master_vol_label.configure(text=f"{int(value)}%")
    
    def toggle_local_pause(self):
        if not self.playing:
            return
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
            self.pause_btn.configure(text="⏸ Pause")
        else:
            pygame.mixer.music.pause()
            self.paused = True
            self.pause_btn.configure(text="▶ Resume")
    
    def stop_local(self):
        pygame.mixer.music.stop()
        self.playing = False
        self.paused = False
        self.update_queue.put({'type': 'player_progress', 'position': 0})
        self.play_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="⏸ Pause")
        self.stop_btn.configure(state="disabled")
    
    def create_stem_player_ui(self):
        for widget in self.player_section.winfo_children()[1:]:
            widget.destroy()
        
        player_frame = ctk.CTkFrame(self.player_section, fg_color="transparent")
        player_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        self.stem_vars = {}
        self.stem_volumes = {}
        colors = {
            'vocals': '#00D4FF',
            'drums': '#FF6B6B',
            'bass': '#4ECDC4',
            'other': '#95E1D3',
            'instrumental': '#A8E6CF'
        }
        
        stems_grid = ctk.CTkFrame(player_frame, fg_color="transparent")
        stems_grid.pack(fill="x", pady=(0, 10))
        
        for i, (stem_name, stem_path) in enumerate(self.current_stems.items()):
            stem_frame = ctk.CTkFrame(stems_grid, fg_color=colors.get(stem_name, 'gray30'), corner_radius=10)
            stem_frame.pack(fill="x", pady=3)
            
            left_frame = ctk.CTkFrame(stem_frame, fg_color="transparent")
            left_frame.pack(side="left", fill="x", expand=True)
            
            var = ctk.BooleanVar(value=True)
            self.stem_vars[stem_name] = var
            
            icon = '🎤' if 'vocal' in stem_name.lower() else '🥁' if 'drum' in stem_name.lower() else '🎸' if 'bass' in stem_name.lower() else '🎼'
            ctk.CTkCheckBox(
                left_frame,
                text=f"{icon} {stem_name.title()}",
                variable=var,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=self.on_stem_toggle
            ).pack(side="left", padx=15, pady=10)
            
            vol_frame = ctk.CTkFrame(stem_frame, fg_color="transparent")
            vol_frame.pack(side="right", padx=15)
            
            ctk.CTkLabel(vol_frame, text="🔊", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 5))
            
            vol_slider = ctk.CTkSlider(
                vol_frame,
                from_=0,
                to=100,
                width=120,
                command=lambda v, s=stem_name: self.update_stem_volume(s, v)
            )
            vol_slider.set(100)
            vol_slider.pack(side="left")
            self.stem_volumes[stem_name] = vol_slider
        
        control_frame = ctk.CTkFrame(player_frame, fg_color=("gray85", "gray20"), corner_radius=10)
        control_frame.pack(fill="x", pady=(10, 5))
        
        btn_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        self.play_btn = ctk.CTkButton(
            btn_frame,
            text="▶ Play",
            width=110,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#2CC985", "#2FA572"),
            command=self.play_stems
        )
        self.play_btn.pack(side="left", padx=5)
        
        self.pause_btn = ctk.CTkButton(
            btn_frame,
            text="⏸ Pause",
            width=110,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.toggle_pause,
            state="disabled"
        )
        self.pause_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(
            btn_frame,
            text="⏹ Stop",
            width=110,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#E74C3C", "#C0392B"),
            command=self.stop_stems,
            state="disabled"
        )
        self.stop_btn.pack(side="left", padx=5)
        
        master_vol_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        master_vol_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        ctk.CTkLabel(
            master_vol_frame, 
            text="🔊 Master Volume:", 
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left", padx=(0, 10))
        
        self.master_volume = ctk.CTkSlider(
            master_vol_frame,
            from_=0,
            to=100,
            command=self.update_master_volume
        )
        self.master_volume.set(70)
        self.master_volume.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.master_vol_label = ctk.CTkLabel(
            master_vol_frame,
            text="70%",
            width=50,
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.master_vol_label.pack(side="left")
        
        time_frame = ctk.CTkFrame(player_frame, fg_color="transparent")
        time_frame.pack(fill="x", pady=(5, 0))
        
        self.time_label = ctk.CTkLabel(
            time_frame,
            text="0:00 / 0:00",
            font=ctk.CTkFont(size=12)
        )
        self.time_label.pack(pady=(0, 5))
        
        self.player_seek_slider = ctk.CTkSlider(
            time_frame,
            from_=0,
            to=1,
            command=self.seek_to_position
        )
        self.player_seek_slider.pack(fill="x")
        self.player_seek_slider.set(0)
    
    def on_stem_toggle(self):
        if self.playing and self.play_mode == "stems":
            self._render_and_play_from(self.current_position)
    
    def update_stem_volume(self, stem, value):
        if self.playing and self.play_mode == "stems":
            threading.Thread(target=lambda: self._render_and_play_from(self.current_position), daemon=True).start()
    
    def update_master_volume(self, value):
        vol = float(value)
        self.master_vol_label.configure(text=f"{int(vol)}%")
        pygame.mixer.music.set_volume(vol / 100.0)
    
    def _render_mixed_to_tempfile(self):
        if not self.stem_audio:
            return None
        max_len = max(len(y) for y, _ in self.stem_audio.values())
        sr = self.sr
        mixed = np.zeros(max_len, dtype=np.float32)
        for stem, (y, _) in self.stem_audio.items():
            enabled = self.stem_vars.get(stem, ctk.BooleanVar(value=True)).get()
            vol = self.stem_volumes.get(stem, None).get() / 100.0 if self.stem_volumes.get(stem) is not None else 1.0
            if enabled and vol > 0:
                if len(y) < max_len:
                    padded = np.zeros(max_len, dtype=np.float32)
                    padded[:len(y)] = y
                    mixed += padded * vol
                else:
                    mixed += y[:max_len] * vol
        max_abs = np.max(np.abs(mixed)) if mixed.size > 0 else 1.0
        if max_abs > 0:
            mixed = mixed / max_abs * 0.9  
        clipped = np.clip(mixed, -1.0, 1.0)
        stereo = np.column_stack((clipped, clipped))
        int16 = (stereo * 32767).astype(np.int16)
        raw_bytes = int16.tobytes()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp_path = tmp.name
        tmp.close()
        seg = AudioSegment(
            data=raw_bytes,
            sample_width=2,
            frame_rate=sr,
            channels=2
        )
        seg.export(tmp_path, format="wav")
        return tmp_path

    def _render_and_play_from(self, start_seconds=0.0):
        try:
            pygame.mixer.music.stop()
            if self._temp_mixed_file and os.path.exists(self._temp_mixed_file):
                try:
                    os.remove(self._temp_mixed_file)
                except:
                    pass
                self._temp_mixed_file = None
            tmp_path = self._render_mixed_to_tempfile()
            if not tmp_path:
                messagebox.showerror("Error", "No stems available to render.")
                return
            self._temp_mixed_file = tmp_path
            try:
                pygame.mixer.music.load(self._temp_mixed_file)
                vol = self.master_volume.get() / 100.0 if hasattr(self, 'master_volume') else 0.7
                pygame.mixer.music.set_volume(vol)
                try:
                    pygame.mixer.music.play(start=start_seconds)
                except TypeError:
                    pygame.mixer.music.play()
                self.playing = True
                self.paused = False
                self.play_btn.configure(state="disabled")
                self.pause_btn.configure(state="normal", text="⏸ Pause")
                self.stop_btn.configure(state="normal")
                self.current_position = start_seconds
                threading.Thread(target=self.update_local_position, daemon=True).start()
            except Exception as e:
                raise
        except Exception as e:
            messagebox.showerror("Error", f"Playback error: {str(e)}")
    
    def play_stems(self):
        if self.playing or self.play_mode != "stems":
            return
        if not self.current_stems:
            return
        if not self.stem_audio:
            return
        self.current_position = 0.0
        self._render_and_play_from(0.0)
    
    def seek_to_position(self, value):
        new_pos = float(value) * self.audio_length
        self.current_position = new_pos
        if self.play_mode == "stems" and self.playing:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.load(self._temp_mixed_file)
                pygame.mixer.music.play(start=new_pos)
            except Exception:
                pygame.mixer.music.stop()
                pygame.mixer.music.play()
        elif self.play_mode == "local":
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.load(self.local_file)
                pygame.mixer.music.play(start=new_pos)
                self.playing = True
                self.paused = False
                self.play_btn.configure(state="disabled")
                self.pause_btn.configure(state="normal", text="⏸ Pause")
                self.stop_btn.configure(state="normal")
                threading.Thread(target=self.update_local_position, daemon=True).start()
            except Exception as e:
                print("Seek error (local):", e)
    
    def toggle_pause(self):
        if not self.playing or self.play_mode != "stems":
            return
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
            self.pause_btn.configure(text="⏸ Pause")
        else:
            pygame.mixer.music.pause()
            self.paused = True
            self.pause_btn.configure(text="▶ Resume")
    
    def stop_stems(self):
        pygame.mixer.music.stop()
        self.playing = False
        self.paused = False
        self.current_position = 0.0
        if self._temp_mixed_file and os.path.exists(self._temp_mixed_file):
            try:
                os.remove(self._temp_mixed_file)
            except:
                pass
            self._temp_mixed_file = None
        self.update_queue.put({'type': 'player_progress', 'position': 0})
        if hasattr(self, 'play_btn'):
            self.play_btn.configure(state="normal")
        if hasattr(self, 'pause_btn'):
            self.pause_btn.configure(state="disabled", text="⏸ Pause")
        if hasattr(self, 'stop_btn'):
            self.stop_btn.configure(state="disabled")
    
    def download_audio(self, url, quality):
        song_id = re.sub(r'[^a-zA-Z0-9]', '_', url.split('/')[-1]) if '/' in url else 'audio'
        temp_subdir = os.path.join(self.output_dir, f"temp_{song_id}")
        os.makedirs(temp_subdir, exist_ok=True)
        
        cmd = [
            "yt-dlp",
            "-f", f"bestaudio[abr<={quality}]/best",
            "--audio-format", "mp3",
            "--audio-quality", f"{quality}K",
            "--postprocessor-args", "-ar 44100",
            "-o", os.path.join(temp_subdir, "%(title)s.%(ext)s"),
            "--verbose",  
            url
        ]
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  
                universal_newlines=True,  
                bufsize=1  
            )
            
            full_output = []  
            percent = 0
            
            for line in process.stdout:
                line = line.strip()
                full_output.append(line)
                self.update_info(line)  
                
                if "%" in line:
                    percent_match = re.search(r'(\d+(?:\.\d+)?)%', line)
                    if percent_match:
                        percent = float(percent_match.group(1))
                        self.update_progress(percent)
                elif "download" in line.lower():
                    self.update_info(line)
            
            process.wait()
            
            if process.returncode != 0:
                log_file = os.path.join(temp_subdir, f"temp_{song_id}_log.txt")
                try:
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write("\n".join(full_output))
                except Exception as log_err:
                    self.update_info(f"Warning: Could not save log: {log_err}")
                error_msg = "\n".join(full_output[-20:])  
                raise Exception(f"yt-dlp failed (code {process.returncode}):\n{error_msg}\nFull log saved to {log_file}")
            
        except Exception as e:
            raise Exception(f"Subprocess error: {e}")
        
        extensions = ['.mp3', '.m4a', '.webm', '.opus', '.flac', '.wav', '.mka']
        files = [f for f in os.listdir(temp_subdir) if any(f.lower().endswith(ext) for ext in extensions) and not f.startswith('.')]
        
        if not files:
            raise Exception(f"No audio file downloaded. Check temp dir: {temp_subdir}. Available files: {os.listdir(temp_subdir)}")
        
        latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(temp_subdir, f)))
        downloaded_path = os.path.join(temp_subdir, latest_file)
        
        final_name = self.sanitize_filename(Path(latest_file).stem) + Path(latest_file).suffix
        final_path = os.path.join(self.output_dir, final_name)
        os.rename(downloaded_path, final_path)
        
        for item in os.listdir(temp_subdir):
            os.remove(os.path.join(temp_subdir, item))
        os.rmdir(temp_subdir)
        
        self.update_info(f"Downloaded: {final_name}")
        return final_path
    
    def process(self):
        try:
            self.disable_btn("⏳ Processing...")
            self.reset_progress()
            
            success, message = self.check_dependencies()
            if not success:
                raise Exception(message)
            
            urls_text = self.url_entry.get("1.0", "end").strip()
            urls = [u.strip() for u in urls_text.split('\n') if u.strip() and u.startswith('http')]
            
            if not urls:
                raise Exception("⚠️ Please enter valid URL(s)")
            
            quality = self.quality_var.get()
            mode = self.mode_var.get()
            
            total = len(urls)
            for idx, url in enumerate(urls, 1):
                self.update_info(f"Processing {idx}/{total}: Downloading...")
                self.reset_progress()
                
                audio_file = self.download_audio(url, quality)
                self.update_progress(100)
                
                if mode == "download_separate":
                    self.update_info(f"Processing {idx}/{total}: Separating stems...")
                    self.separate_stems(audio_file)
            
            self.update_info("🎉 All processing completed!")
            messagebox.showinfo("✅ Success", f"Processed {total} track(s) successfully!")
            
        except Exception as e:
            self.update_info("❌ Error")
            messagebox.showerror("❌ Error", str(e))
            
        finally:
            self.enable_btn("▶ Start Processing")
            self.reset_progress()
            self.is_processing = False
    
    def start_processing(self):
        if not self.is_processing:
            self.is_processing = True
            thread = threading.Thread(target=self.process, daemon=True)
            thread.start()
    
    def open_output_folder(self):
        if os.path.exists(self.output_dir):
            if sys.platform == "win32":
                os.startfile(self.output_dir)
            elif sys.platform == "darwin":
                subprocess.run(["open", self.output_dir])
            else:
                subprocess.run(["xdg-open", self.output_dir])

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()  

    app = MusicStemTool()
    app.mainloop()