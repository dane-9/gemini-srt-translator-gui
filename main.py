import sys
import os
import json
import re
import subprocess
import signal
import time
import argparse
import queue
import threading
import requests

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTreeView, QLineEdit, QLabel, QFileDialog, QMessageBox,
    QComboBox, QProgressBar, QDialog, QFormLayout,
    QSpinBox, QDoubleSpinBox, QCheckBox, QDialogButtonBox, QMenu, QTextEdit,
    QToolButton, QFrame, QStackedWidget, QStyle, QListWidget, QListWidgetItem,
    QStyledItemDelegate, QStyleOptionViewItem
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QIcon, QKeySequence, QFont, QPixmap, QPainter, QLinearGradient, QColor, QPen, QFontMetrics
from PySide6.QtCore import Qt, QThread, Slot, QObject, Signal, QTimer, QItemSelectionModel, QRect, QModelIndex
from window import FramelessWidget

def is_compiled():
    result = os.path.normcase(os.path.splitext(sys.argv[0])[1]) == '.exe'
    return result

def get_executable_path():
    exe_path = os.path.abspath(sys.argv[0])
    return exe_path
    
def get_app_directory():
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    return app_dir

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)
    
def get_persistent_path(relative_path):
    try:
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)
    
def setup_ffmpeg_path():
    if is_compiled():
        try:
            ffmpeg_exe_name = "ffmpeg.exe" if os.name == 'nt' else "ffmpeg"
            ffmpeg_exe = get_resource_path(ffmpeg_exe_name)
            
            if os.path.exists(ffmpeg_exe):
                ffmpeg_dir = os.path.dirname(ffmpeg_exe)
                current_path = os.environ.get('PATH', '')
                if ffmpeg_dir not in current_path:
                    os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
                    
                os.environ['FFMPEG_BINARY'] = ffmpeg_exe
                return True
            
            app_dir = get_app_directory()
            ffmpeg_alt = os.path.join(app_dir, ffmpeg_exe_name)
            if os.path.exists(ffmpeg_alt):
                ffmpeg_dir = os.path.dirname(ffmpeg_alt)
                current_path = os.environ.get('PATH', '')
                if ffmpeg_dir not in current_path:
                    os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
                os.environ['FFMPEG_BINARY'] = ffmpeg_alt
                return True
                
        except Exception as e:
            print(f"Error setting up bundled ffmpeg: {e}")
    
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False

def load_svg(svg_path, color="#A0A0A0", size=None):
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()

        svg_content = re.sub(r'<path\s+d=', f'<path fill="{color}" d=', svg_content)
        svg_content = re.sub(r'<path\s+fill="[^"]*"\s+d=', f'<path fill="{color}" d=', svg_content)

        svg_bytes = svg_content.encode('utf-8')
        pixmap = QPixmap()
        pixmap.loadFromData(svg_bytes, 'SVG')
        
        if size is not None:
            device_ratio = 2.0
            high_res_size = int(size * device_ratio)
            
            high_res_pixmap = pixmap.scaled(
                high_res_size, high_res_size, 
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            
            high_res_pixmap.setDevicePixelRatio(device_ratio)
            pixmap = high_res_pixmap

        return QIcon(pixmap)

    except Exception as e:
        print(f"Error loading SVG {svg_path}: {e}")
        return QIcon()

def load_stylesheet():
    try:
        qss_file_path = get_resource_path("Files/dark.qss").replace("\\", "/")
        with open(qss_file_path, 'r', encoding='utf-8') as f:
            qss = f.read()
        
        try:
            # Dropdown arrow
            dropdown_svg_path = get_resource_path("Files/dropdown.svg").replace("\\", "/")
            qss = qss.replace("QComboBox::drop-down {", 
                            f"QComboBox::drop-down {{ image: url({dropdown_svg_path});")
            
            qss += f"""QComboBox::down-arrow {{ image: url({dropdown_svg_path}); width: 24px; height: 24px; }}"""
            
            # Spinbox up arrow
            arrow_up_svg_path = get_resource_path("Files/arrow-up.svg").replace("\\", "/")
            qss = qss.replace("QSpinBox::up-button {", 
                            f"QSpinBox::up-button {{ image: url({arrow_up_svg_path});")
            qss = qss.replace("QDoubleSpinBox::up-button {", 
                            f"QDoubleSpinBox::up-button {{ image: url({arrow_up_svg_path});")
            
            # Spinbox down arrow
            arrow_down_svg_path = get_resource_path("Files/arrow-down.svg").replace("\\", "/")
            qss = qss.replace("QSpinBox::down-button {", 
                            f"QSpinBox::down-button {{ image: url({arrow_down_svg_path});")
            qss = qss.replace("QDoubleSpinBox::down-button {", 
                            f"QDoubleSpinBox::down-button {{ image: url({arrow_down_svg_path});")
            
        except Exception as e:
            print(f"Error processing SVG arrows: {e}")
        
        return qss
        
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"Error loading dark.qss: {e}")
        return ""
        
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov'}

def is_video_file(file_path):
    return os.path.splitext(file_path)[1].lower() in VIDEO_EXTENSIONS

def is_subtitle_file(file_path):
    return os.path.splitext(file_path)[1].lower() == '.srt'

CONFIG_FILE = get_persistent_path(os.path.join("Files", "config.json"))

DEFAULT_SETTINGS = {
    "gemini_api_key": "", 
    "gemini_api_key2": "", 
    "tmdb_api_key": "",
    "target_language": "English",
    "selected_languages": ["en"],
    "model_name": "gemini-2.5-flash",
    "output_file_naming_pattern": "{original_name}.{lang_code}.{modifiers}.srt",
    "update_existing_queue_languages": False,
    "queue_on_exit": "clear_if_translated",
    "existing_file_handling": "skip",
    "use_gst_parameters": False,
    "use_model_tuning": False,
    "use_tmdb": False,
    "tmdb_movie_template": "Overview: {movie.overview}\n\n{movie.title} - {movie.year}\nGenre(s): {movie.genres}",
    "tmdb_episode_template": "Episode Overview: {episode.overview}\n\n{show.title} {episode.number} - {episode.title}\nShow Overview: {show.overview}",
    "description": "", 
    "batch_size": 300,
    "free_quota": True, 
    "skip_upgrade": False, 
    "progress_log": False, 
    "thoughts_log": False,
    "temperature": 0.7, 
    "top_p": 0.95, 
    "top_k": 40, 
    "streaming": True, 
    "thinking": True, 
    "thinking_budget": 2048,
    "cleanup_audio_on_success": True,
    "cleanup_audio_on_failure": False,
    "cleanup_audio_on_cancel": False,
    "cleanup_audio_on_remove": True,
    "cleanup_audio_on_exit": False
}

LANGUAGES = {
    "Afrikaans": ("af", "afr"), "Albanian": ("sq", "sqi"), "Amharic": ("am", "amh"), "Arabic": ("ar", "ara"),
    "Armenian": ("hy", "hye"), "Azerbaijani": ("az", "aze"), "Basque": ("eu", "eus"), "Belarusian": ("be", "bel"),
    "Bengali": ("bn", "ben"), "Bosnian": ("bs", "bos"), "Bulgarian": ("bg", "bul"), "Catalan": ("ca", "cat"),
    "Cebuano": ("ceb", "ceb"), "Chinese (Simplified)": ("zh-CN", "zho"), "Chinese (Traditional)": ("zh-TW", "zho"),
    "Corsican": ("co", "cos"), "Croatian": ("hr", "hrv"), "Czech": ("cs", "ces"), "Danish": ("da", "dan"),
    "Dutch": ("nl", "nld"), "English": ("en", "eng"), "Estonian": ("et", "est"), "Finnish": ("fi", "fin"),
    "French": ("fr", "fra"), "Frisian": ("fy", "fry"), "Galician": ("gl", "glg"), "Georgian": ("ka", "kat"),
    "German": ("de", "deu"), "Greek": ("el", "ell"), "Gujarati": ("gu", "guj"), "Haitian Creole": ("ht", "hat"),
    "Hausa": ("ha", "hau"), "Hebrew": ("he", "heb"), "Hindi": ("hi", "hin"), "Hungarian": ("hu", "hun"),
    "Icelandic": ("is", "isl"), "Igbo": ("ig", "ibo"), "Indonesian": ("id", "ind"), "Italian": ("it", "ita"),
    "Japanese": ("ja", "jpn"), "Javanese": ("jv", "jav"), "Kannada": ("kn", "kan"), "Kazakh": ("kk", "kaz"),
    "Khmer": ("km", "khm"), "Korean": ("ko", "kor"), "Kurdish": ("ku", "kur"), "Kyrgyz": ("ky", "kir"),
    "Lao": ("lo", "lao"), "Latvian": ("lv", "lav"), "Lithuanian": ("lt", "lit"), "Luxembourgish": ("lb", "ltz"),
    "Macedonian": ("mk", "mkd"), "Malay": ("ms", "msa"), "Malayalam": ("ml", "mal"), "Maltese": ("mt", "mlt"),
    "Marathi": ("mr", "mar"), "Mongolian": ("mn", "mon"), "Myanmar": ("my", "mya"), "Nepali": ("ne", "nep"),
    "Norwegian": ("no", "nor"), "Pashto": ("ps", "pus"), "Persian": ("fa", "fas"), "Polish": ("pl", "pol"),
    "Brazilian Portuguese": ("pt-BR", "por"), "Portuguese": ("pt-PT", "por"), "Punjabi": ("pa", "pan"),
    "Romanian": ("ro", "ron"), "Russian": ("ru", "rus"), "Samoan": ("sm", "smo"), "Serbian": ("sr", "srp"),
    "Sindhi": ("sd", "snd"), "Sinhala": ("si", "sin"), "Slovak": ("sk", "slk"), "Slovenian": ("sl", "slv"),
    "Somali": ("so", "som"), "Spanish": ("es", "spa"), "Sundanese": ("su", "sun"), "Swahili": ("sw", "swa"),
    "Swedish": ("sv", "swe"), "Tajik": ("tg", "tgk"), "Tamil": ("ta", "tam"), "Telugu": ("te", "tel"),
    "Thai": ("th", "tha"), "Turkish": ("tr", "tur"), "Ukrainian": ("uk", "ukr"), "Urdu": ("ur", "urd"),
    "Uzbek": ("uz", "uzb"), "Vietnamese": ("vi", "vie"), "Xhosa": ("xh", "xho"), "Yiddish": ("yi", "yid"),
    "Yoruba": ("yo", "yor"), "Zulu": ("zu", "zul")
}

def _build_language_code_maps():
    two_letter_to_standard = {}
    three_letter_to_standard = {}
    
    for lang_name, (two_letter, three_letter) in LANGUAGES.items():
        two_letter_to_standard[two_letter] = two_letter
        three_letter_to_standard[three_letter] = two_letter
    
    return two_letter_to_standard, three_letter_to_standard
    
def _normalize_language_code(code):
    two_letter_map, three_letter_map = _build_language_code_maps()
    
    if code in two_letter_map:
        return two_letter_map[code]
    elif code in three_letter_map:
        return three_letter_map[code]
    
    return None
    
def _parse_subtitle_filename(subtitle_filename):
    if not subtitle_filename.lower().endswith('.srt'):
        return None
    
    basename = os.path.splitext(subtitle_filename)[0]
    parts = basename.split('.')
    
    if len(parts) < 2:
        return {
            'base_name': basename,
            'lang_code': None,
            'forced': False,
            'sdh': False,
            'modifiers_string': '',
            'original_parts': parts
        }
    
    result = {
        'base_name': None,
        'lang_code': None,
        'forced': False,
        'sdh': False,
        'modifiers_string': '',
        'original_parts': parts
    }
    
    lang_code = None
    lang_part_index = -1
    
    for i in range(len(parts) - 1, 0, -1):
        part = parts[i].lower()
        
        if part in ['forced', 'sdh']:
            continue
        
        normalized_code = _normalize_language_code(part)
        if normalized_code and lang_code is None:
            lang_code = normalized_code
            lang_part_index = i
            break
    
    if lang_part_index > 0:
        result['base_name'] = '.'.join(parts[:lang_part_index])
        
        modifier_parts = parts[lang_part_index + 1:]
        valid_modifiers = []
        
        for modifier_part in modifier_parts:
            modifier_lower = modifier_part.lower()
            if modifier_lower in ['forced', 'sdh']:
                valid_modifiers.append(modifier_lower)
                if modifier_lower == 'forced':
                    result['forced'] = True
                elif modifier_lower == 'sdh':
                    result['sdh'] = True
        
        result['modifiers_string'] = '.'.join(valid_modifiers)
    else:
        result['base_name'] = basename
    
    result['lang_code'] = lang_code
    
    return result
    
def _get_all_language_codes():
    codes = []
    for two_letter, three_letter in LANGUAGES.values():
        codes.append(two_letter)
        if three_letter != two_letter:
            codes.append(three_letter)
    return codes
    
def _strip_language_codes_from_name(name_part):
    parts = name_part.split('.')
    if len(parts) < 2:
        return name_part
    
    all_codes = _get_all_language_codes()
    modifiers = ['forced', 'sdh']
    
    while len(parts) > 1:
        last_part = parts[-1].lower()
        
        if last_part in modifiers or _normalize_language_code(last_part):
            parts.pop()
        else:
            break
    
    return '.'.join(parts)
    
def _build_modifiers_string(subtitle_parsed):
    if not subtitle_parsed:
        return ""
    
    return subtitle_parsed.get('modifiers_string', '')
    
def _clean_filename_dots(filename):
    while '..' in filename:
        filename = filename.replace('..', '.')
    return filename
    
def run_gst_translation_subprocess():
    parser = argparse.ArgumentParser(description="Run Gemini SRT Translator for a single file (subprocess mode).")
    parser.add_argument("--run-gst-subprocess", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--gemini_api_key", required=True, help="Gemini API Key")
    parser.add_argument("--target_language", required=True, help="Target language")
    parser.add_argument("--input_file", help="Input SRT file path")
    parser.add_argument("--video_file", help="Video file path")
    parser.add_argument("--audio_file", help="Audio file path")
    parser.add_argument("--extract_audio", type=bool, default=False, help="Extract audio from video")
    parser.add_argument("--model_name", help="Gemini model")
    parser.add_argument("--gemini_api_key2", help="Second API Key")
    parser.add_argument("--output_file", help="Output file name")
    parser.add_argument("--start_line", type=int, help="Start line")
    parser.add_argument("--description", help="Description")
    parser.add_argument("--batch_size", type=int, help="Batch size")
    parser.add_argument("--free_quota", type=bool, help="Free quota")
    parser.add_argument("--skip_upgrade", type=bool, help="Skip upgrade")
    parser.add_argument("--use_colors", type=bool, help="Use colors")
    parser.add_argument("--progress_log", type=bool, help="Progress log")
    parser.add_argument("--thoughts_log", type=bool, help="Thoughts log")
    parser.add_argument("--temperature", type=float, help="Temperature")
    parser.add_argument("--top_p", type=float, help="Top P")
    parser.add_argument("--top_k", type=int, help="Top K")
    parser.add_argument("--streaming", type=bool, help="Streaming")
    parser.add_argument("--thinking", type=bool, help="Thinking")
    parser.add_argument("--thinking_budget", type=int, help="Thinking budget")
    
    args = parser.parse_args()
    
    if os.name == 'nt':
        import subprocess

        original_Popen = subprocess.Popen
        original_run = subprocess.run

        class PatchedPopen(original_Popen):
            def __init__(self, *args, **kwargs):
                if 'creationflags' not in kwargs:
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                super().__init__(*args, **kwargs)

        def patched_run(*args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            if not kwargs.get('capture_output') and not kwargs.get('stdout') and not kwargs.get('stderr'):
                kwargs['stdout'] = subprocess.DEVNULL
                kwargs['stderr'] = subprocess.DEVNULL
                
            return original_run(*args, **kwargs)

        subprocess.Popen = PatchedPopen
        subprocess.run = patched_run

    try:
        import gemini_srt_translator as gst
        
        gst.gemini_api_key = args.gemini_api_key
        gst.target_language = args.target_language
        
        if args.video_file and args.extract_audio:
            gst.video_file = args.video_file
            gst.extract_audio = True
        elif args.input_file:
            gst.input_file = args.input_file
        elif args.video_file:
            gst.video_file = args.video_file
        if args.audio_file:
            gst.audio_file = args.audio_file
        if args.extract_audio:
            gst.extract_audio = args.extract_audio
        if args.model_name:
            gst.model_name = args.model_name
        if args.gemini_api_key2:
            gst.gemini_api_key2 = args.gemini_api_key2
        if args.output_file:
            gst.output_file = args.output_file
        if args.start_line is not None:
            gst.start_line = args.start_line
        if args.description:
            gst.description = args.description
        if args.batch_size is not None:
            gst.batch_size = args.batch_size
        if args.free_quota is not None:
            gst.free_quota = args.free_quota
        if args.skip_upgrade is not None:
            gst.skip_upgrade = args.skip_upgrade
        if args.use_colors is not None:
            gst.use_colors = args.use_colors
        if args.progress_log is not None:
            gst.progress_log = args.progress_log
        if args.thoughts_log is not None:
            gst.thoughts_log = args.thoughts_log
        if args.temperature is not None:
            gst.temperature = args.temperature
        if args.top_p is not None:
            gst.top_p = args.top_p
        if args.top_k is not None:
            gst.top_k = args.top_k
        if args.streaming is not None:
            gst.streaming = args.streaming
        if args.thinking is not None:
            gst.thinking = args.thinking
        if args.thinking_budget is not None:
            gst.thinking_budget = args.thinking_budget
        
        gst.use_colors = False
        
        gst.translate()
        sys.exit(0)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
def run_audio_extraction_subprocess():
    parser = argparse.ArgumentParser(description="Extract audio only")
    parser.add_argument("--run-audio-extraction", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--gemini_api_key", required=True)
    parser.add_argument("--video_file", required=True)
    parser.add_argument("--model_name", default="gemini-2.5-flash")
    
    args = parser.parse_args()
    
    if os.name == 'nt':
        import subprocess

        original_Popen = subprocess.Popen
        original_run = subprocess.run

        class PatchedPopen(original_Popen):
            def __init__(self, *args, **kwargs):
                if 'creationflags' not in kwargs:
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                super().__init__(*args, **kwargs)

        def patched_run(*args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
            if not kwargs.get('capture_output') and not kwargs.get('stdout') and not kwargs.get('stderr'):
                kwargs['stdout'] = subprocess.DEVNULL
                kwargs['stderr'] = subprocess.DEVNULL

            return original_run(*args, **kwargs)

        subprocess.Popen = PatchedPopen
        subprocess.run = patched_run
    
    try:
        import gemini_srt_translator as gst
        
        gst.gemini_api_key = args.gemini_api_key
        gst.video_file = args.video_file
        gst.extract_audio = True
        gst.target_language = "English"
        gst.use_colors = False
        gst.model_name = args.model_name
        
        print("Starting audio extraction and processing...")

        gst.translate()
        
        video_dir = os.path.dirname(args.video_file)
        video_name = os.path.splitext(os.path.basename(args.video_file))[0]
        expected_audio = os.path.join(video_dir, f"{video_name}_extracted.mp3")
        
        if os.path.exists(expected_audio):
            print(f"Success! Audio saved as: {expected_audio}")
            dummy_subtitle = os.path.join(video_dir, f"{video_name}.srt")
            if os.path.exists(dummy_subtitle):
                try:
                    os.remove(dummy_subtitle)
                except OSError:
                    pass
            sys.exit(0)
        else:
            print("Audio extraction process finished, but the output file was not found.")
            sys.exit(1)
        
    except Exception as e:
        print(f"Error during audio extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

class IconTextDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.icon_configs = {}
    
    def add_icon_config(self, column, text_pattern, icon_path, color="#A0A0A0", size=16, position="after", spacing=2, exact_match=True):
        if column not in self.icon_configs:
            self.icon_configs[column] = []
        
        config = {
            'text_pattern': text_pattern,
            'icon': load_svg(icon_path, color, size),
            'size': size,
            'position': position,
            'spacing': spacing,
            'exact_match': exact_match
        }
        self.icon_configs[column].append(config)
    
    def paint(self, painter, option, index):
        column = index.column()
        text = str(index.data()) if index.data() else ""
        
        config = self._get_matching_config(column, text)
        
        if config and config['icon'] and not config['icon'].isNull():
            self._paint_with_icon(painter, option, index, text, config)
        else:
            super().paint(painter, option, index)
    
    def _get_matching_config(self, column, text):
        if column not in self.icon_configs:
            return None
        
        for config in self.icon_configs[column]:
            if config['exact_match']:
                if config['text_pattern'] == text:
                    return config
            else:
                if config['text_pattern'] in text:
                    return config
        
        return None
    
    def _paint_with_icon(self, painter, option, index, text, config):
        super().paint(painter, option, index)
        
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(text)
        icon_size = config['size']
        spacing = config['spacing']
        
        margin_left = 4
        start_x = option.rect.left() + margin_left
        
        if config['position'] == "before":
            icon_x = start_x
            text_x = start_x + icon_size + spacing
            
            text_clear_rect = QRect(text_x, option.rect.top(), text_width, option.rect.height())
            if option.state & QStyle.State_Selected:
                painter.fillRect(text_clear_rect, option.palette.highlight())
            elif index.row() % 2:
                painter.fillRect(text_clear_rect, option.palette.alternateBase())
            else:
                painter.fillRect(text_clear_rect, option.palette.base())
        else:
            text_x = start_x
            icon_x = start_x + text_width + spacing
        
        if config['position'] == "before":
            if option.state & QStyle.State_Selected:
                painter.setPen(option.palette.highlightedText().color())
            else:
                painter.setPen(option.palette.text().color())
            
            text_rect = QRect(text_x, option.rect.top(), text_width, option.rect.height())
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        
        icon_y = option.rect.top() + (option.rect.height() - icon_size) // 2
        icon_rect = QRect(icon_x, icon_y, icon_size, icon_size)
        config['icon'].paint(painter, icon_rect)
        
class TMDBLookupWorker(QObject):
    finished = Signal(str, str, bool)
    status_update = Signal(str, str)
    
    def __init__(self, file_path, api_key, movie_template, episode_template):
        super().__init__()
        self.file_path = file_path
        self.api_key = api_key
        self.movie_template = movie_template
        self.episode_template = episode_template
        self.base_url = "https://api.themoviedb.org/3"
        
    def run(self):
        try:
            self.status_update.emit(self.file_path, "Fetching TMDB info...")
            
            parsed_info = self._parse_filename(self.file_path)
            if not parsed_info:
                self.finished.emit(self.file_path, "", False)
                return
                
            description = ""
            if parsed_info['type'] == 'movie':
                description = self._lookup_movie(parsed_info['title'], parsed_info.get('year'))
            elif parsed_info['type'] == 'episode':
                description = self._lookup_episode(parsed_info['show_title'], parsed_info['season'], parsed_info['episode'])
                
            self.finished.emit(self.file_path, description, bool(description))
            
        except Exception as e:
            self.finished.emit(self.file_path, "", False)
    
    def _parse_filename(self, file_path):
        basename = os.path.basename(file_path)
        
        if is_video_file(file_path):
            name_without_ext = os.path.splitext(basename)[0]
        else:
            subtitle_parsed = _parse_subtitle_filename(basename)
            if subtitle_parsed and subtitle_parsed['base_name']:
                name_without_ext = subtitle_parsed['base_name']
            else:
                name_without_ext = _strip_language_codes_from_name(os.path.splitext(basename)[0])
        
        episode_pattern = r'^(.+?)[.\s-]+[Ss](\d{1,2})[Ee](\d{1,2})'
        episode_match = re.search(episode_pattern, name_without_ext)
        
        if episode_match:
            show_title = re.sub(r'[._-]', ' ', episode_match.group(1)).strip()
            season = int(episode_match.group(2))
            episode = int(episode_match.group(3))
            return {
                'type': 'episode',
                'show_title': show_title,
                'season': season,
                'episode': episode
            }
        
        movie_pattern = r'^(.+?)[.\s-]*(?:\((\d{4})\)|(\d{4})).*$'
        movie_match = re.search(movie_pattern, name_without_ext)
        
        if movie_match:
            title = re.sub(r'[._-]', ' ', movie_match.group(1)).strip()
            year = movie_match.group(2) or movie_match.group(3)
            return {
                'type': 'movie',
                'title': title,
                'year': int(year) if year else None
            }
        
        title = re.sub(r'[._-]', ' ', name_without_ext).strip()
        return {
            'type': 'movie',
            'title': title,
            'year': None
        }
    
    def _make_request(self, endpoint, params=None, retries=3):
        if not params:
            params = {}
        params['api_key'] = self.api_key
        
        for attempt in range(retries):
            try:
                response = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=10)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    time.sleep(10)
                    continue
                else:
                    break
            except requests.RequestException:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                break
        
        return None
    
    def _lookup_movie(self, title, year=None):
        search_params = {'query': title}
        if year:
            search_params['year'] = year
            
        search_result = self._make_request('search/movie', search_params)
        if not search_result or not search_result.get('results'):
            if year:
                search_result = self._make_request('search/movie', {'query': title})
                if not search_result or not search_result.get('results'):
                    return ""
            else:
                return ""
        
        movie_id = search_result['results'][0]['id']
        movie_details = self._make_request(f'movie/{movie_id}')
        
        if not movie_details:
            return ""
        
        movie_data = {
            'movie.title': movie_details.get('title', ''),
            'movie.year': movie_details.get('release_date', '')[:4] if movie_details.get('release_date') else '',
            'movie.overview': movie_details.get('overview', ''),
            'movie.genres': '/'.join([g['name'] for g in movie_details.get('genres', [])]),
            'movie.genre': movie_details.get('genres', [{}])[0].get('name', '') if movie_details.get('genres') else ''
        }
        
        return self._apply_template(self.movie_template, movie_data)
    
    def _lookup_episode(self, show_title, season, episode):
        search_result = self._make_request('search/tv', {'query': show_title})
        if not search_result or not search_result.get('results'):
            return ""
        
        tv_id = search_result['results'][0]['id']
        tv_details = self._make_request(f'tv/{tv_id}')
        
        if not tv_details:
            return ""
        
        episode_details = self._make_request(f'tv/{tv_id}/season/{season}/episode/{episode}')
        
        if not episode_details:
            return ""
        
        episode_data = {
            'show.title': tv_details.get('name', ''),
            'show.overview': tv_details.get('overview', ''),
            'show.genres': '/'.join([g['name'] for g in tv_details.get('genres', [])]),
            'show.genre': tv_details.get('genres', [{}])[0].get('name', '') if tv_details.get('genres') else '',
            'episode.title': episode_details.get('name', ''),
            'episode.overview': episode_details.get('overview', ''),
            'episode.number': f"S{season:02d}E{episode:02d}"
        }
        
        return self._apply_template(self.episode_template, episode_data)
    
    def _apply_template(self, template, data):
        lines = template.split('\n')
        result_lines = []
        
        for line in lines:
            template_vars = re.findall(r'\{([^}]+)\}', line)
            
            if not template_vars:
                result_lines.append(line)
                continue
            
            has_missing_data = False
            processed_line = line
            
            for var in template_vars:
                value = data.get(var, '')
                if not value or value.strip() == '':
                    has_missing_data = True
                    break
            
            if has_missing_data:
                continue
            
            for var in template_vars:
                value = data.get(var, '')
                processed_line = processed_line.replace(f'{{{var}}}', str(value))
            
            result_lines.append(processed_line)
        
        return '\n'.join(result_lines)

def _validate_tmdb_api_key(api_key):
    if not api_key or len(api_key.strip()) < 30:
        return False
    
    try:
        response = requests.get(
            f"https://api.themoviedb.org/3/configuration",
            params={'api_key': api_key.strip()},
            timeout=5
        )
        return response.status_code == 200
    except:
        return False

class QueueStateManager:
    def __init__(self, queue_file_path):
        self.queue_file_path = queue_file_path
        self.state = self._load_queue_state()
    
    def _load_queue_state(self):
        try:
            if os.path.exists(self.queue_file_path):
                with open(self.queue_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading queue state: {e}")
        
        return {"queue_state": {}}
        
    def get_extracted_audio_file(self, subtitle_path):
            if subtitle_path in self.state["queue_state"]:
                audio_file = self.state["queue_state"][subtitle_path].get("extracted_audio_file")
                return audio_file
            return None
    
    def _save_queue_state(self):
        try:
            queue_dir = os.path.dirname(self.queue_file_path)
            if not os.path.exists(queue_dir):
                os.makedirs(queue_dir, exist_ok=True)
            
            with open(self.queue_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving queue state: {e}")
    
    def add_subtitle_to_queue(self, subtitle_path, languages, description, output_pattern, task_type="subtitle", video_file=None, requires_extraction=False):
        if subtitle_path not in self.state["queue_state"]:
            self.state["queue_state"][subtitle_path] = {
                "languages": {},
                "description": description,
                "target_languages": languages.copy(),
                "output_pattern": output_pattern,
                "task_type": task_type,
                "video_file": video_file,
                "requires_audio_extraction": requires_extraction,
                "extracted_audio_file": None,
                "audio_extraction_status": "pending"
            }
        
        subtitle_dir = os.path.dirname(subtitle_path)
        subtitle_basename = os.path.basename(subtitle_path)
        
        subtitle_parsed = _parse_subtitle_filename(subtitle_basename)
        if subtitle_parsed and subtitle_parsed['base_name']:
            name_part = subtitle_parsed['base_name']
        else:
            name_part = _strip_language_codes_from_name(os.path.splitext(subtitle_basename)[0])
        
        for lang_code in languages:
            if lang_code not in self.state["queue_state"][subtitle_path]["languages"]:
                file_lang_code = lang_code
                if file_lang_code.startswith('zh'):
                    file_lang_code = 'zh'
                elif file_lang_code.startswith('pt'):
                    file_lang_code = 'pt'
                
                modifiers = _build_modifiers_string(subtitle_parsed)
                
                output_filename = output_pattern.format(
                    original_name=name_part, 
                    lang_code=file_lang_code,
                    modifiers=modifiers
                )
                
                output_filename = _clean_filename_dots(output_filename)
                output_path = os.path.join(subtitle_dir, output_filename)
                
                self.state["queue_state"][subtitle_path]["languages"][lang_code] = {
                    "status": "queued",
                    "output_file": output_path
                }
        
        self._save_queue_state()
    
    def remove_subtitle_from_queue(self, subtitle_path):
        if subtitle_path in self.state["queue_state"]:
            del self.state["queue_state"][subtitle_path]
            self._save_queue_state()
    
    def get_current_language_in_progress(self, subtitle_path):
        if subtitle_path not in self.state["queue_state"]:
            return None
        
        languages = self.state["queue_state"][subtitle_path]["languages"]
        for lang_code, lang_data in languages.items():
            if lang_data["status"] == "in_progress":
                return lang_code
        
        return None
    
    def get_next_language_to_process(self, subtitle_path):
        if subtitle_path not in self.state["queue_state"]:
            return None
        
        languages = self.state["queue_state"][subtitle_path]["languages"]
        target_languages = self.state["queue_state"][subtitle_path]["target_languages"]
        
        for lang_code in target_languages:
            if lang_code in languages and languages[lang_code]["status"] == "in_progress":
                return lang_code
        
        for lang_code in target_languages:
            if lang_code in languages and languages[lang_code]["status"] == "queued":
                return lang_code
        
        return None
    
    def mark_language_in_progress(self, subtitle_path, lang_code):
        if subtitle_path in self.state["queue_state"]:
            if lang_code in self.state["queue_state"][subtitle_path]["languages"]:
                self.state["queue_state"][subtitle_path]["languages"][lang_code]["status"] = "in_progress"
                self._save_queue_state()
    
    def mark_language_completed(self, subtitle_path, lang_code):
        if subtitle_path in self.state["queue_state"]:
            if lang_code in self.state["queue_state"][subtitle_path]["languages"]:
                self.state["queue_state"][subtitle_path]["languages"][lang_code]["status"] = "completed"
                self._save_queue_state()
    
    def mark_language_queued(self, subtitle_path, lang_code):
        if subtitle_path in self.state["queue_state"]:
            if lang_code in self.state["queue_state"][subtitle_path]["languages"]:
                self.state["queue_state"][subtitle_path]["languages"][lang_code]["status"] = "queued"
                self._save_queue_state()
    
    def get_language_progress_summary(self, subtitle_path):
        if subtitle_path not in self.state["queue_state"]:
            return "Queued"
        
        languages = self.state["queue_state"][subtitle_path]["languages"]
        total_languages = len(languages)
        completed_count = sum(1 for lang_data in languages.values() if lang_data["status"] == "completed")
        
        if completed_count == 0:
            return "Queued"
        elif completed_count == total_languages:
            return "Translated"
        else:
            return f"{completed_count}/{total_languages} Languages completed"
    
    def has_any_work_remaining(self):
        for subtitle_path, subtitle_data in self.state["queue_state"].items():
            languages = subtitle_data["languages"]
            for lang_data in languages.values():
                if lang_data["status"] in ["queued", "in_progress"]:
                    return True
        return False
    
    def cleanup_completed_subtitle(self, subtitle_path):
        if subtitle_path in self.state["queue_state"]:
            languages = self.state["queue_state"][subtitle_path]["languages"]
            all_completed = all(lang_data["status"] == "completed" for lang_data in languages.values())
            
            if all_completed:
                progress_file = self._get_progress_file_path(subtitle_path)
                if os.path.exists(progress_file):
                    try:
                        os.remove(progress_file)
                    except Exception:
                        pass
    
    def _get_progress_file_path(self, subtitle_path):
        original_basename = os.path.basename(subtitle_path)
        name_part, ext = os.path.splitext(original_basename)
        progress_filename = f"{name_part}.progress"
        original_dir = os.path.dirname(subtitle_path)
        return os.path.join(original_dir, progress_filename)
    
    def clear_all_state(self):
        self.state = {"queue_state": {}}
        self._save_queue_state()
        
    def update_subtitle_languages(self, subtitle_path, new_languages, description, output_pattern):
        if subtitle_path in self.state["queue_state"]:
            old_entry = self.state["queue_state"][subtitle_path]
            
            task_type = old_entry.get("task_type", "subtitle")
            video_file = old_entry.get("video_file")
            requires_extraction = old_entry.get("requires_audio_extraction", False)
            extracted_audio_file = old_entry.get("extracted_audio_file")
            audio_extraction_status = old_entry.get("audio_extraction_status", "pending")
            
            self.state["queue_state"][subtitle_path] = {
                "languages": {},
                "description": description,
                "target_languages": new_languages.copy(),
                "output_pattern": output_pattern,
                "task_type": task_type,
                "video_file": video_file,
                "requires_audio_extraction": requires_extraction,
                "extracted_audio_file": extracted_audio_file,
                "audio_extraction_status": audio_extraction_status
            }
            
            subtitle_dir = os.path.dirname(subtitle_path)
            subtitle_basename = os.path.basename(subtitle_path)
            
            subtitle_parsed = _parse_subtitle_filename(subtitle_basename)
            if subtitle_parsed and subtitle_parsed['base_name']:
                name_part = subtitle_parsed['base_name']
            else:
                name_part = _strip_language_codes_from_name(os.path.splitext(subtitle_basename)[0])
            
            for lang_code in new_languages:
                file_lang_code = lang_code
                if file_lang_code.startswith('zh'):
                    file_lang_code = 'zh'
                elif file_lang_code.startswith('pt'):
                    file_lang_code = 'pt'
                
                modifiers = _build_modifiers_string(subtitle_parsed)
                
                output_filename = output_pattern.format(
                    original_name=name_part, 
                    lang_code=file_lang_code,
                    modifiers=modifiers
                )
                
                output_filename = _clean_filename_dots(output_filename)
                output_path = os.path.join(subtitle_dir, output_filename)
                
                old_status = "queued"
                if lang_code in old_entry.get("languages", {}):
                    old_status = old_entry["languages"][lang_code].get("status", "queued")
                
                self.state["queue_state"][subtitle_path]["languages"][lang_code] = {
                    "status": old_status,
                    "output_file": output_path
                }
            
            self._save_queue_state()
            
    def set_audio_extraction_status(self, subtitle_path, status, audio_file_path=None):
        if subtitle_path in self.state["queue_state"]:
            self.state["queue_state"][subtitle_path]["audio_extraction_status"] = status
            if audio_file_path:
                self.state["queue_state"][subtitle_path]["extracted_audio_file"] = audio_file_path
            self._save_queue_state()
    
    def get_extracted_subtitle_file(self, subtitle_path):
        if subtitle_path in self.state["queue_state"]:
            subtitle_file = self.state["queue_state"][subtitle_path].get("extracted_subtitle_file")
            return subtitle_file
        return None
    
    def should_extract_audio(self, subtitle_path):
        if subtitle_path in self.state["queue_state"]:
            entry = self.state["queue_state"][subtitle_path]
            return (entry.get("requires_audio_extraction", False) and 
                    entry.get("audio_extraction_status") != "completed")
        return False
    
    def get_all_extracted_audio_files(self):
        audio_files = []
        for subtitle_data in self.state["queue_state"].values():
            audio_file = subtitle_data.get("extracted_audio_file")
            if audio_file and os.path.exists(audio_file):
                audio_files.append(audio_file)
        return audio_files
    
    def cleanup_extracted_audio(self, subtitle_path):
        if subtitle_path in self.state["queue_state"]:
            audio_file = self.state["queue_state"][subtitle_path].get("extracted_audio_file")
            subtitle_file = self.state["queue_state"][subtitle_path].get("extracted_subtitle_file")
            
            if audio_file and os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                except Exception as e:
                    pass
            
            if subtitle_file and os.path.exists(subtitle_file):
                try:
                    os.remove(subtitle_file)
                except Exception as e:
                    pass
            
            self.state["queue_state"][subtitle_path]["extracted_audio_file"] = None
            self.state["queue_state"][subtitle_path]["extracted_subtitle_file"] = None
            self.state["queue_state"][subtitle_path]["audio_extraction_status"] = "pending"
            self._save_queue_state()
            
    def sync_audio_extraction_status(self, subtitle_path):
        if subtitle_path not in self.state["queue_state"]:
            return None, None
            
        entry = self.state["queue_state"][subtitle_path]
        video_file = entry.get("video_file")
        current_status = entry.get("audio_extraction_status", "pending")
        current_audio_file = entry.get("extracted_audio_file")
        current_extracted_subtitle = entry.get("extracted_subtitle_file")
        
        if current_status in ["extracting", "pending"] and video_file:
            video_dir = os.path.dirname(video_file)
            video_basename = os.path.basename(video_file)
            video_name = os.path.splitext(video_basename)[0]
            expected_audio = os.path.join(video_dir, f"{video_name}_extracted.mp3")
            expected_subtitle = os.path.join(video_dir, f"{video_name}_extracted.srt")
            
            audio_exists = os.path.exists(expected_audio)
            subtitle_exists = os.path.exists(expected_subtitle)
            
            if audio_exists:
                self.state["queue_state"][subtitle_path]["audio_extraction_status"] = "completed"
                self.state["queue_state"][subtitle_path]["extracted_audio_file"] = expected_audio
                
                if subtitle_exists:
                    self.state["queue_state"][subtitle_path]["extracted_subtitle_file"] = expected_subtitle
                else:
                    if not current_extracted_subtitle:
                        self.state["queue_state"][subtitle_path]["extracted_subtitle_file"] = None
                
                self._save_queue_state()
                return expected_audio, expected_subtitle if subtitle_exists else current_extracted_subtitle
        
        return current_audio_file, current_extracted_subtitle
        
    def mark_language_skipped(self, subtitle_path, lang_code):
        if subtitle_path in self.state["queue_state"]:
            if lang_code in self.state["queue_state"][subtitle_path]["languages"]:
                self.state["queue_state"][subtitle_path]["languages"][lang_code]["status"] = "skipped"
                self._save_queue_state()

class DialogTitleBarWidget(QWidget):
    def __init__(self, title="Dialog", parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(30)
        self.setObjectName("DialogTitleBar")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 0, 0)
        layout.setSpacing(5)
        
        self.title_label = QLabel(title)
        self.title_label.setObjectName("DialogTitle")
        layout.addWidget(self.title_label)
        
        layout.addStretch()
        
        self.close_btn = HoverToolButton(
            get_resource_path("Files/window-close.svg"),
            normal_color="#A0A0A0",
            hover_color="white"
        )
        self.close_btn.setObjectName("WindowCloseButton")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close_window)
        
        layout.addWidget(self.close_btn)
        
        self.mouse_pressed = False
        self.mouse_pos = None
    
    def set_title(self, title):
        self.title_label.setText(title)
    
    def close_window(self):
        if self.parent_window:
            self.parent_window.close()
    
    def mouseMoveEvent(self, event):
        if self.mouse_pressed and self.mouse_pos and self.parent_window:
            diff = event.globalPosition().toPoint() - self.mouse_pos
            self.parent_window.move(self.parent_window.pos() + diff)
            self.mouse_pos = event.globalPosition().toPoint()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = False
            self.mouse_pos = None

class GradientTitleWidget(QWidget):
    def __init__(self, text="Gemini SRT Translator", parent=None):
        super().__init__(parent)
        self.text = text
        self.setMinimumHeight(30)
        self.setMaximumHeight(40)
        
        self.font = QFont("Arial", 13, QFont.Bold)
        self.setFont(self.font)
        
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text)
        self.setMinimumWidth(text_width)
        self.setMaximumWidth(text_width)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        content_rect = self.contentsRect()
        
        gradient = QLinearGradient(content_rect.left(), 0, content_rect.right(), 0)
        gradient.setColorAt(0.0, QColor("#4995ff"))
        gradient.setColorAt(0.7, QColor("#a981d8"))
        gradient.setColorAt(1.0, QColor("#e84d62"))
        
        pen = QPen()
        pen.setBrush(gradient)
        pen.setWidth(1)
        painter.setPen(pen)
        
        painter.setFont(self.font)
        
        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(self.text)
        x = content_rect.left() + (content_rect.width() - text_rect.width()) // 2
        y = content_rect.top() + (content_rect.height() + text_rect.height()) // 2 - fm.descent()
        
        painter.drawText(x, y, self.text)
    
    def setText(self, text):
        self.text = text
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text)
        self.setMinimumWidth(text_width)
        self.setMaximumWidth(text_width)
        self.update()

class HoverToolButton(QToolButton):
    def __init__(self, svg_path, normal_color="#A0A0A0", hover_color="white", disabled_color="#444444", parent=None):
        super().__init__(parent)
        self.svg_path = svg_path
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.disabled_color = disabled_color
        
        self.normal_icon = load_svg(svg_path, normal_color)
        self.hover_icon = load_svg(svg_path, hover_color)
        self.disabled_icon = load_svg(svg_path, disabled_color)
        
        self.setIcon(self.normal_icon)
        
    def enterEvent(self, event):
        if self.isEnabled():
            self.setIcon(self.hover_icon)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if self.isEnabled():
            self.setIcon(self.normal_icon)
        super().leaveEvent(event)
        
    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        if enabled:
            self.setIcon(self.normal_icon)
        else:
            self.setIcon(self.disabled_icon)

class HoverPushButton(QPushButton):
    def __init__(self, svg_path, normal_color="#A0A0A0", hover_color="white", disabled_color="#444444", parent=None):
        super().__init__(parent)
        self.svg_path = svg_path
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.disabled_color = disabled_color
        
        self.normal_icon = load_svg(svg_path, normal_color)
        self.hover_icon = load_svg(svg_path, hover_color)
        self.disabled_icon = load_svg(svg_path, disabled_color)
        
        self.setIcon(self.normal_icon)
        
    def enterEvent(self, event):
        if self.isEnabled():
            self.setIcon(self.hover_icon)
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        if self.isEnabled():
            self.setIcon(self.normal_icon)
        super().leaveEvent(event)
        
    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        if enabled:
            self.setIcon(self.normal_icon)
        else:
            self.setIcon(self.disabled_icon)

class CustomFramelessDialog(FramelessWidget):
    def __init__(self, title="Dialog", parent=None):
        super().__init__(hint=['close'])
        
        self.setWindowTitle(title)
        self.setWindowModality(Qt.ApplicationModal)
        self.parent_window = parent
        
        self._result = QDialog.Rejected
        self._finished = False
        
        title_bar = self.getTitleBar()
        title_bar.setTitleBarFont(QFont('Arial', 10))
        title_bar.setIconSize(16, 16)
        
        self.custom_title_bar = DialogTitleBarWidget(title, self)
        
        title_bar_layout = title_bar.layout()
        if title_bar_layout:
            while title_bar_layout.count():
                child = title_bar_layout.takeAt(0)
                if child.widget():
                    child.widget().setParent(None)
            title_bar_layout.addWidget(self.custom_title_bar)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        
        main_layout = self.layout()
        main_layout.addWidget(self.content_widget)
    
    def center_on_parent(self):
        if self.parent_window:
            parent_geometry = self.parent_window.geometry()
            dialog_geometry = self.geometry()
            
            x = parent_geometry.x() + (parent_geometry.width() - dialog_geometry.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - dialog_geometry.height()) // 2
            
            screen = QApplication.primaryScreen().geometry()
            x = max(0, min(x, screen.width() - dialog_geometry.width()))
            y = max(0, min(y, screen.height() - dialog_geometry.height()))
            
            self.move(x, y)
        else:
            screen = QApplication.primaryScreen().geometry()
            dialog_geometry = self.geometry()
            x = (screen.width() - dialog_geometry.width()) // 2
            y = (screen.height() - dialog_geometry.height()) // 2
            self.move(x, y)
    
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.center_on_parent)
    
    def set_title(self, title):
        self.custom_title_bar.set_title(title)
        self.setWindowTitle(title)
    
    def get_content_layout(self):
        return self.content_layout
    
    def accept(self):
        self._result = QDialog.Accepted
        self._finished = True
        self.close()
    
    def reject(self):
        self._result = QDialog.Rejected
        self._finished = True
        self.close()
    
    def done(self, result):
        self._result = result
        self._finished = True
        self.close()
    
    def result(self):
        return self._result
    
    def exec(self):
        self._finished = False
        self._result = QDialog.Rejected
        self.show()
        
        app = QApplication.instance()
        while not self._finished and self.isVisible():
            app.processEvents()
            QThread.msleep(10)
        
        return self._result
    
    def closeEvent(self, event):
        if not self._finished:
            self.reject()
        super().closeEvent(event)

class CustomMessageBox(CustomFramelessDialog):
    def __init__(self, icon_type, title, text, buttons=QMessageBox.Ok, parent=None, secondary_text=None):
        super().__init__(title, parent)
        self.setMinimumSize(300, 150)
        self.result_value = QMessageBox.Cancel
        
        layout = self.get_content_layout()
        
        message_layout = QHBoxLayout()
        
        icon_label = QLabel()
        icon_size = 32
        style = QApplication.style()
        
        if icon_type == QMessageBox.Question:
            icon_label.setPixmap(style.standardIcon(QStyle.SP_MessageBoxQuestion).pixmap(icon_size, icon_size))
        elif icon_type == QMessageBox.Warning:
            icon_label.setPixmap(style.standardIcon(QStyle.SP_MessageBoxWarning).pixmap(icon_size, icon_size))
        elif icon_type == QMessageBox.Critical:
            icon_label.setPixmap(style.standardIcon(QStyle.SP_MessageBoxCritical).pixmap(icon_size, icon_size))
        elif icon_type == QMessageBox.Information:
            icon_label.setPixmap(style.standardIcon(QStyle.SP_MessageBoxInformation).pixmap(icon_size, icon_size))
        else:
            icon_label.setPixmap(style.standardIcon(QStyle.SP_MessageBoxInformation).pixmap(icon_size, icon_size))
        
        icon_label.setAlignment(Qt.AlignTop)
        icon_label.setFixedSize(icon_size + 10, icon_size + 10)
        message_layout.addWidget(icon_label)
        
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(8)
        
        text_label = QLabel(text)
        text_label.setObjectName("DialogMainText")
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        text_layout.addWidget(text_label)
        
        if secondary_text:
            secondary_label = QLabel(secondary_text)
            secondary_label.setObjectName("DialogSecondaryText")
            secondary_label.setWordWrap(True)
            secondary_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            text_layout.addWidget(secondary_label)
        
        message_layout.addWidget(text_container, 1)
        
        layout.addLayout(message_layout)
        layout.addStretch()
        
        self.button_box = QDialogButtonBox()
        
        if buttons & QMessageBox.Ok:
            ok_btn = self.button_box.addButton(QDialogButtonBox.Ok)
            ok_btn.clicked.connect(lambda: self.done_with_result(QMessageBox.Ok))
        
        if buttons & QMessageBox.Cancel:
            cancel_btn = self.button_box.addButton(QDialogButtonBox.Cancel)
            cancel_btn.clicked.connect(lambda: self.done_with_result(QMessageBox.Cancel))
        
        if buttons & QMessageBox.Yes:
            yes_btn = self.button_box.addButton(QDialogButtonBox.Yes)
            yes_btn.clicked.connect(lambda: self.done_with_result(QMessageBox.Yes))
        
        if buttons & QMessageBox.No:
            no_btn = self.button_box.addButton(QDialogButtonBox.No)
            no_btn.clicked.connect(lambda: self.done_with_result(QMessageBox.No))
        
        layout.addWidget(self.button_box)
    
    def done_with_result(self, result):
        self.result_value = result
        self.accept()
    
    def exec(self):
        super().exec()
        return self.result_value
    
    @staticmethod
    def question(parent, title, text, buttons=QMessageBox.Yes | QMessageBox.No, default_button=QMessageBox.No, secondary_text=None):
        dialog = CustomMessageBox(QMessageBox.Question, title, text, buttons, parent, secondary_text)
        return dialog.exec()
    
    @staticmethod
    def warning(parent, title, text, buttons=QMessageBox.Ok, default_button=QMessageBox.Ok, secondary_text=None):
        dialog = CustomMessageBox(QMessageBox.Warning, title, text, buttons, parent, secondary_text)
        return dialog.exec()
    
    @staticmethod
    def information(parent, title, text, buttons=QMessageBox.Ok, default_button=QMessageBox.Ok, secondary_text=None):
        dialog = CustomMessageBox(QMessageBox.Information, title, text, buttons, parent, secondary_text)
        return dialog.exec()
    
    @staticmethod
    def critical(parent, title, text, buttons=QMessageBox.Ok, default_button=QMessageBox.Ok, secondary_text=None):
        dialog = CustomMessageBox(QMessageBox.Critical, title, text, buttons, parent, secondary_text)
        return dialog.exec()

class BulkDescriptionDialog(CustomFramelessDialog):
    def __init__(self, current_text="", parent=None):
        super().__init__("Edit Description", parent)
        self.setMinimumSize(400, 200)
        
        layout = self.get_content_layout()
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(current_text)
        layout.addWidget(self.text_edit)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
    
    def get_description(self):
        return self.text_edit.toPlainText().strip()

class SettingsDialog(CustomFramelessDialog):
    def __init__(self, current_settings, parent=None):
        super().__init__("Advanced Settings", parent)
        self.setMinimumSize(600, 500)
        self.settings = current_settings.copy()
        
        layout = self.get_content_layout()
        
        main_layout = QHBoxLayout()
        
        self.category_tree = QTreeView()
        self.category_tree.setHeaderHidden(True)
        self.category_tree.setMinimumWidth(150)
        self.category_tree.setMaximumWidth(200)
        self.category_tree.setRootIsDecorated(False)
        
        self.tree_model = QStandardItemModel()
        
        basic_item = QStandardItem("Basic Configuration")
        basic_item.setIcon(load_svg(get_resource_path("Files/cog-box.svg"), "#A0A0A0"))
        basic_item.setEditable(False)
        
        gst_item = QStandardItem("GST Parameters")
        gst_item.setIcon(load_svg(get_resource_path("Files/gst-params.svg"), "#A0A0A0"))
        gst_item.setEditable(False)
        
        model_item = QStandardItem("Model Tuning")
        model_item.setIcon(load_svg(get_resource_path("Files/model-tuning.svg"), "#A0A0A0"))
        model_item.setEditable(False)
        
        tmdb_item = QStandardItem("TMDB Configuration")
        tmdb_item.setIcon(load_svg(get_resource_path("Files/tmdb.svg"), "#A0A0A0"))
        tmdb_item.setEditable(False)
        
        self.tree_model.appendRow(basic_item)
        self.tree_model.appendRow(gst_item)
        self.tree_model.appendRow(model_item)
        self.tree_model.appendRow(tmdb_item)
        
        self.category_tree.setModel(self.tree_model)
        self.category_tree.selectionModel().currentChanged.connect(self.on_category_changed)
        
        main_layout.addWidget(self.category_tree)
        
        self.pages_widget = QStackedWidget()
        
        self.basic_page = self._build_basic_page()
        self.gst_page = self._build_gst_page()
        self.model_page = self._build_model_page()
        self.tmdb_page = self._build_tmdb_page()
        
        self.pages_widget.addWidget(self.basic_page)
        self.pages_widget.addWidget(self.gst_page)
        self.pages_widget.addWidget(self.model_page)
        self.pages_widget.addWidget(self.tmdb_page)
        
        main_layout.addWidget(self.pages_widget)
        layout.addLayout(main_layout)
        
        buttons_layout = QHBoxLayout()
        
        self.reset_defaults_btn = QPushButton("Reset to Default")
        self.reset_defaults_btn.clicked.connect(self.reset_defaults)
        buttons_layout.addWidget(self.reset_defaults_btn)
        
        buttons_layout.addStretch()
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        buttons_layout.addWidget(self.button_box)
        
        layout.addLayout(buttons_layout)
        
        self.category_tree.setCurrentIndex(self.tree_model.index(0, 0))
        self.pages_widget.setCurrentIndex(0)
    
    def _build_basic_page(self):
        page = QWidget()
        main_layout = QVBoxLayout(page)
        
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(15)
        
        self.output_naming_pattern_edit = QLineEdit(self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.srt"))
        form_layout.addRow("Output Naming Pattern:", self.output_naming_pattern_edit)
        
        self.queue_on_exit_combo = QComboBox()
        self.queue_on_exit_combo.addItem("Clear Queue", "clear")
        self.queue_on_exit_combo.addItem("Clear Queue if all Translated", "clear_if_translated")
        self.queue_on_exit_combo.addItem("Don't Clear Queue", "keep")
        
        current_setting = self.settings.get("queue_on_exit", "clear_if_translated")
        for i in range(self.queue_on_exit_combo.count()):
            if self.queue_on_exit_combo.itemData(i) == current_setting:
                self.queue_on_exit_combo.setCurrentIndex(i)
                break
        
        form_layout.addRow("Queue on Exit:", self.queue_on_exit_combo)
        
        self.existing_file_combo = QComboBox()
        self.existing_file_combo.addItem("Skip Existing Files", "skip")
        self.existing_file_combo.addItem("Overwrite Always (Skips if same as input)", "overwrite")
        
        current_setting = self.settings.get("existing_file_handling", "skip")
        for i in range(self.existing_file_combo.count()):
            if self.existing_file_combo.itemData(i) == current_setting:
                self.existing_file_combo.setCurrentIndex(i)
                break
        
        form_layout.addRow("Existing Output Files:", self.existing_file_combo)
        
        main_layout.addLayout(form_layout)
        
        self.update_queue_languages_checkbox = QCheckBox("Auto-Update Queue Languages")
        self.update_queue_languages_checkbox.setChecked(self.settings.get("update_existing_queue_languages", True))
        self.update_queue_languages_checkbox.setToolTip("When enabled, changing the language selection will update all existing queue items that match the previous selection")
        main_layout.addWidget(self.update_queue_languages_checkbox)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        main_layout.addWidget(separator)
        
        cleanup_label = QLabel("Delete Extracted Audio:")
        cleanup_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        main_layout.addWidget(cleanup_label)
        
        cleanup_widget = QWidget()
        cleanup_layout = QVBoxLayout(cleanup_widget)
        cleanup_layout.setContentsMargins(20, 0, 0, 0)
        
        self.cleanup_checkboxes = {}
        cleanup_items = [
            ("cleanup_audio_on_success", "on successful translation", True),
            ("cleanup_audio_on_failure", "on failed translation", False), 
            ("cleanup_audio_on_cancel", "when task is cancelled", False),
            ("cleanup_audio_on_remove", "when task is removed from queue", True),
            ("cleanup_audio_on_exit", "on application exit", False)
        ]
        
        for setting_key, label_text, default_value in cleanup_items:
            checkbox = QCheckBox(label_text)
            checkbox.setChecked(bool(self.settings.get(setting_key, default_value)))
            self.cleanup_checkboxes[setting_key] = checkbox
            cleanup_layout.addWidget(checkbox)
        
        main_layout.addWidget(cleanup_widget)
        
        main_layout.addStretch()
        return page
    
    def _build_gst_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        
        self.gst_checkbox = QCheckBox("Enable GST Parameters")
        self.gst_checkbox.setChecked(self.settings.get("use_gst_parameters", False))
        self.gst_checkbox.stateChanged.connect(self.toggle_gst_settings)
        layout.addWidget(self.gst_checkbox)
        
        self.gst_content_widget = QWidget()
        gst_layout = QVBoxLayout(self.gst_content_widget)
        gst_layout.setContentsMargins(20, 0, 0, 0)
        gst_layout.setSpacing(10)
        
        form_layout = QFormLayout()
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 10000)
        self.batch_size_spin.setValue(self.settings.get("batch_size", 30))
        self.batch_size_spin.setMaximumWidth(150)
        form_layout.addRow("Batch Size:", self.batch_size_spin)
        gst_layout.addLayout(form_layout)
        
        checkbox_items = [
            ("free_quota", "Free Quota", True),
            ("skip_upgrade", "Skip Upgrade", False),
            ("progress_log", "Progress Log", False),
            ("thoughts_log", "Thoughts Log", False)
        ]
        
        self.gst_checkboxes = {}
        for setting_key, label_text, default_value in checkbox_items:
            checkbox = QCheckBox(label_text)
            checkbox.setChecked(self.settings.get(setting_key, default_value))
            self.gst_checkboxes[setting_key] = checkbox
            gst_layout.addWidget(checkbox)
        
        layout.addWidget(self.gst_content_widget)
        layout.addStretch()
        
        self.toggle_gst_settings(self.gst_checkbox.isChecked())
        
        return page
    
    def _build_model_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        
        self.model_checkbox = QCheckBox("Enable Model Tuning Parameters")
        self.model_checkbox.setChecked(self.settings.get("use_model_tuning", False))
        self.model_checkbox.stateChanged.connect(self.toggle_model_settings)
        layout.addWidget(self.model_checkbox)
        
        self.model_content_widget = QWidget()
        model_layout = QVBoxLayout(self.model_content_widget)
        model_layout.setContentsMargins(20, 0, 0, 0)
        model_layout.setSpacing(10)
        
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(10)
        
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(self.settings.get("temperature", 0.7))
        self.temperature_spin.setDecimals(1)
        self.temperature_spin.setMaximumWidth(150)
        form_layout.addRow("Temperature:", self.temperature_spin)
        
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.1)
        self.top_p_spin.setValue(self.settings.get("top_p", 0.95))
        self.top_p_spin.setDecimals(2)
        self.top_p_spin.setMaximumWidth(150)
        form_layout.addRow("Top P:", self.top_p_spin)
        
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(0, 1000)
        self.top_k_spin.setValue(self.settings.get("top_k", 40))
        self.top_k_spin.setMaximumWidth(150)
        form_layout.addRow("Top K:", self.top_k_spin)
        
        model_layout.addLayout(form_layout)
        
        model_checkbox_items = [
            ("streaming", "Streaming", True),
            ("thinking", "Thinking", True)
        ]
        
        self.model_checkboxes = {}
        for setting_key, label_text, default_value in model_checkbox_items:
            checkbox = QCheckBox(label_text)
            checkbox.setChecked(self.settings.get(setting_key, default_value))
            self.model_checkboxes[setting_key] = checkbox
            model_layout.addWidget(checkbox)
        
        self.model_checkboxes["thinking"].stateChanged.connect(self.toggle_thinking_budget)
        
        self.thinking_budget_widget = QWidget()
        budget_layout = QFormLayout(self.thinking_budget_widget)
        budget_layout.setContentsMargins(20, 0, 0, 0)
        
        self.thinking_budget_spin = QSpinBox()
        self.thinking_budget_spin.setRange(0, 32768)
        self.thinking_budget_spin.setValue(self.settings.get("thinking_budget", 2048))
        self.thinking_budget_spin.setMaximumWidth(150)
        budget_layout.addRow("Budget:", self.thinking_budget_spin)
        
        model_layout.addWidget(self.thinking_budget_widget)
        
        layout.addWidget(self.model_content_widget)
        layout.addStretch()
        
        self.toggle_model_settings(self.model_checkbox.isChecked())
        self.toggle_thinking_budget(self.model_checkboxes["thinking"].isChecked())
        
        return page
        
    def _build_tmdb_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(15)
        
        self.tmdb_checkbox = QCheckBox("Use TMDB for automatic descriptions")
        self.tmdb_checkbox.setChecked(self.settings.get("use_tmdb", False))
        self.tmdb_checkbox.stateChanged.connect(self.toggle_tmdb_settings)
        layout.addWidget(self.tmdb_checkbox)
        
        self.tmdb_content_widget = QWidget()
        tmdb_layout = QVBoxLayout(self.tmdb_content_widget)
        tmdb_layout.setContentsMargins(20, 0, 0, 0)
        tmdb_layout.setSpacing(15)
        
        movie_section = QWidget()
        movie_layout = QVBoxLayout(movie_section)
        movie_layout.setContentsMargins(0, 0, 0, 0)
        
        movie_header = QHBoxLayout()
        movie_title = QLabel("Movie Template:")
        movie_title.setStyleSheet("font-weight: bold;")
        movie_header.addWidget(movie_title)
        
        movie_header.addStretch()
        
        self.edit_movie_btn = QPushButton("Edit Movie Template")
        self.edit_movie_btn.clicked.connect(self.edit_movie_template)
        movie_header.addWidget(self.edit_movie_btn)
        
        movie_layout.addLayout(movie_header)
        
        self.movie_template_display = QLabel()
        self.movie_template_display.setWordWrap(True)
        self.movie_template_display.setStyleSheet("background-color: #2a2a2a; padding: 10px; border-radius: 4px; font-family: monospace;")
        self._update_movie_template_display()
        movie_layout.addWidget(self.movie_template_display)
        
        tmdb_layout.addWidget(movie_section)
        
        episode_section = QWidget()
        episode_layout = QVBoxLayout(episode_section)
        episode_layout.setContentsMargins(0, 0, 0, 0)
        
        episode_header = QHBoxLayout()
        episode_title = QLabel("Episode Template:")
        episode_title.setStyleSheet("font-weight: bold;")
        episode_header.addWidget(episode_title)
        
        episode_header.addStretch()
        
        self.edit_episode_btn = QPushButton("Edit Episode Template")
        self.edit_episode_btn.clicked.connect(self.edit_episode_template)
        episode_header.addWidget(self.edit_episode_btn)
        
        episode_layout.addLayout(episode_header)
        
        self.episode_template_display = QLabel()
        self.episode_template_display.setWordWrap(True)
        self.episode_template_display.setStyleSheet("background-color: #2a2a2a; padding: 10px; border-radius: 4px; font-family: monospace;")
        self._update_episode_template_display()
        episode_layout.addWidget(self.episode_template_display)
        
        tmdb_layout.addWidget(episode_section)
        
        layout.addWidget(self.tmdb_content_widget)
        layout.addStretch()
        
        self.toggle_tmdb_settings(self.tmdb_checkbox.isChecked())
        
        return page
        
    def toggle_thinking_budget(self, enabled):
        self.thinking_budget_widget.setEnabled(enabled)
        if not enabled:
            self.thinking_budget_widget.setStyleSheet("color: grey;")
        else:
            self.thinking_budget_widget.setStyleSheet("")
    
    def on_category_changed(self, current, previous):
        if current.isValid():
            row = current.row()
            self.pages_widget.setCurrentIndex(row)
    
    def toggle_gst_settings(self, enabled):
        self.gst_content_widget.setEnabled(enabled)
        if not enabled:
            self.gst_content_widget.setStyleSheet("color: grey;")
        else:
            self.gst_content_widget.setStyleSheet("")
    
    def toggle_model_settings(self, enabled):
        self.model_content_widget.setEnabled(enabled)
        if not enabled:
            self.model_content_widget.setStyleSheet("color: grey;")
        else:
            self.model_content_widget.setStyleSheet("")
            if hasattr(self, 'model_checkboxes') and 'thinking' in self.model_checkboxes:
                self.toggle_thinking_budget(self.model_checkboxes["thinking"].isChecked())
                
    def toggle_tmdb_settings(self, enabled):
        self.tmdb_content_widget.setEnabled(enabled)
        if not enabled:
            self.tmdb_content_widget.setStyleSheet("color: grey;")
        else:
            self.tmdb_content_widget.setStyleSheet("")
            
    def edit_movie_template(self):
        current_template = self.settings.get("tmdb_movie_template", "Overview: {movie.overview}\n\n{movie.title} - {movie.year}\nGenre(s): {movie.genres}")
        dialog = TemplateEditorDialog("movie", current_template, self)
        if dialog.exec():
            new_template = dialog.get_template()
            self.settings["tmdb_movie_template"] = new_template
            self._update_movie_template_display()
    
    def edit_episode_template(self):
        current_template = self.settings.get("tmdb_episode_template", "Episode Overview: {episode.overview}\n\n{show.title} {episode.number} - {episode.title}\nShow Overview: {show.overview}")
        dialog = TemplateEditorDialog("episode", current_template, self)
        if dialog.exec():
            new_template = dialog.get_template()
            self.settings["tmdb_episode_template"] = new_template
            self._update_episode_template_display()
            
    def _update_movie_template_display(self):
        template = self.settings.get("tmdb_movie_template", "Overview: {movie.overview}\n\n{movie.title} - {movie.year}\nGenre(s): {movie.genres}")
        self.movie_template_display.setText(template.replace('\n', '<br>'))
    
    def _update_episode_template_display(self):
        template = self.settings.get("tmdb_episode_template", "Episode Overview: {episode.overview}\n\n{show.title} {episode.number} - {episode.title}\nShow Overview: {show.overview}")
        self.episode_template_display.setText(template.replace('\n', '<br>'))
    
    def reset_defaults(self):
        self.output_naming_pattern_edit.setText("{original_name}.{lang_code}.srt")
        self.queue_on_exit_combo.setCurrentIndex(1)
        self.existing_file_combo.setCurrentIndex(0)
        self.update_queue_languages_checkbox.setChecked(False)
        
        self.gst_checkbox.setChecked(False)
        self.batch_size_spin.setValue(30)
        
        gst_defaults = {
            "free_quota": True,
            "skip_upgrade": False,
            "progress_log": False,
            "thoughts_log": False
        }
        for key, default_val in gst_defaults.items():
            if key in self.gst_checkboxes:
                self.gst_checkboxes[key].setChecked(default_val)
        
        self.model_checkbox.setChecked(False)
        self.temperature_spin.setValue(0.7)
        self.top_p_spin.setValue(0.95)
        self.top_k_spin.setValue(40)
        self.thinking_budget_spin.setValue(2048)
        
        model_defaults = {
            "streaming": True,
            "thinking": True
        }
        for key, default_val in model_defaults.items():
            if key in self.model_checkboxes:
                self.model_checkboxes[key].setChecked(default_val)
        
        self.tmdb_checkbox.setChecked(False)
        self.settings["tmdb_movie_template"] = "Overview: {movie.overview}\n\n{movie.title} - {movie.year}\nGenre(s): {movie.genres}"
        self.settings["tmdb_episode_template"] = "Episode Overview: {episode.overview}\n\n{show.title} {episode.number} - {episode.title}\nShow Overview: {show.overview}"
        self._update_movie_template_display()
        self._update_episode_template_display()
                
        cleanup_defaults = {
            "cleanup_audio_on_success": True,
            "cleanup_audio_on_failure": False,
            "cleanup_audio_on_cancel": False,
            "cleanup_audio_on_remove": True,
            "cleanup_audio_on_exit": False
        }
        for key, default_val in cleanup_defaults.items():
            if key in self.cleanup_checkboxes:
                self.cleanup_checkboxes[key].setChecked(default_val)
        
        self.toggle_gst_settings(False)
        self.toggle_model_settings(False)
        self.toggle_tmdb_settings(False)
    
    def get_settings(self):
        s = self.settings.copy()
        
        s["output_file_naming_pattern"] = self.output_naming_pattern_edit.text().strip()
        s["queue_on_exit"] = self.queue_on_exit_combo.currentData()
        s["existing_file_handling"] = self.existing_file_combo.currentData()
        s["update_existing_queue_languages"] = self.update_queue_languages_checkbox.isChecked()
        
        s["use_gst_parameters"] = self.gst_checkbox.isChecked()
        s["batch_size"] = self.batch_size_spin.value()
        
        for key, checkbox in self.gst_checkboxes.items():
            s[key] = checkbox.isChecked()
        
        s["use_model_tuning"] = self.model_checkbox.isChecked()
        s["temperature"] = self.temperature_spin.value()
        s["top_p"] = self.top_p_spin.value()
        s["top_k"] = self.top_k_spin.value()
        s["thinking_budget"] = self.thinking_budget_spin.value()
        
        for key, checkbox in self.model_checkboxes.items():
            s[key] = checkbox.isChecked()
        
        s["use_tmdb"] = self.tmdb_checkbox.isChecked()
        s["tmdb_movie_template"] = self.settings.get("tmdb_movie_template", "Overview: {movie.overview}\n\n{movie.title} - {movie.year}\nGenre(s): {movie.genres}")
        s["tmdb_episode_template"] = self.settings.get("tmdb_episode_template", "Episode Overview: {episode.overview}\n\n{show.title} {episode.number} - {episode.title}\nShow Overview: {show.overview}")
            
        for key, checkbox in self.cleanup_checkboxes.items():
            s[key] = checkbox.isChecked()
        
        return s
        
class TemplateEditorDialog(CustomFramelessDialog):
    def __init__(self, template_type, current_template="", parent=None):
        title = f"Edit {template_type.title()} Template"
        super().__init__(title, parent)
        self.setMinimumSize(600, 500)
        self.template_type = template_type
        
        layout = self.get_content_layout()
        
        main_layout = QHBoxLayout()
        
        left_layout = QVBoxLayout()
        
        template_label = QLabel("Template:")
        template_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(template_label)
        
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(current_template)
        self.text_edit.textChanged.connect(self.update_preview)
        left_layout.addWidget(self.text_edit)
        
        main_layout.addLayout(left_layout)
        
        right_layout = QVBoxLayout()
        
        preview_label = QLabel("Preview:")
        preview_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(preview_label)
        
        self.preview_area = QLabel()
        self.preview_area.setWordWrap(True)
        self.preview_area.setStyleSheet("background-color: #2a2a2a; padding: 15px; border-radius: 4px; font-family: Arial;")
        self.preview_area.setAlignment(Qt.AlignTop)
        self.preview_area.setMinimumWidth(250)
        right_layout.addWidget(self.preview_area)
        
        main_layout.addLayout(right_layout)
        
        layout.addLayout(main_layout)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        self.update_preview()
    
    def update_preview(self):
        template = self.text_edit.toPlainText()
        preview_text = self._generate_preview(template)
        self.preview_area.setText(preview_text)
    
    def _generate_preview(self, template):
        if self.template_type == "movie":
            sample_data = {
                'movie.title': 'Interstellar',
                'movie.year': '2014',
                'movie.genres': 'Sci-Fi/Adventure',
                'movie.genre': 'Sci-Fi',
                'movie.overview': 'A team of explorers travel through a wormhole in space in attempt to ensure humanity\'s survival.'
            }
        else:
            sample_data = {
                'show.title': 'Friends',
                'show.overview': 'Six friends navigate life and love in New York City.',
                'show.genres': 'Comedy/Romance',
                'show.genre': 'Comedy',
                'episode.title': 'The One Where Rachel Finds Out',
                'episode.number': 'S01E24',
                'episode.overview': 'Rachel finds out Ross is in love with her when she overhears a message he left on her answering machine.'
            }
        
        preview = template
        for key, value in sample_data.items():
            preview = preview.replace(f'{{{key}}}', value)
        
        return preview
    
    def get_template(self):
        return self.text_edit.toPlainText()

class LanguageSelectionDialog(CustomFramelessDialog):
    def __init__(self, selected_languages=None, parent=None):
        super().__init__("Select Output Languages", parent)
        self.setMinimumSize(400, 500)
        self.selected_languages = selected_languages or ["sv"]
        self.setup_ui()
        
    def setup_ui(self):
        layout = self.get_content_layout()
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter languages...")
        self.search_input.textChanged.connect(self.filter_languages)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        self.language_list = QListWidget()
        self.language_list.setAlternatingRowColors(True)
        layout.addWidget(self.language_list)
        
        self.populate_languages()
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)
        
        layout.addLayout(button_layout)
    
    def populate_languages(self):
        sorted_languages = sorted(LANGUAGES.items())
        
        for lang_name, (two_letter, three_letter) in sorted_languages:
            item = QListWidgetItem()
            
            checkbox = QCheckBox(f"{lang_name} ({two_letter})")
            checkbox.setChecked(two_letter in self.selected_languages)
            checkbox.setProperty("lang_code", two_letter)
            
            item.setSizeHint(checkbox.sizeHint())
            self.language_list.addItem(item)
            self.language_list.setItemWidget(item, checkbox)
    
    def filter_languages(self, search_text):
        search_text = search_text.lower()
        
        for i in range(self.language_list.count()):
            item = self.language_list.item(i)
            checkbox = self.language_list.itemWidget(item)
            
            lang_text = checkbox.text().lower()
            should_show = search_text in lang_text
            item.setHidden(not should_show)
    
    def validate_and_accept(self):
        selected = self.get_selected_languages()
        if not selected:
            CustomMessageBox.warning(self, "No Selection", "Please select at least one language.")
            return
        self.accept()
    
    def get_selected_languages(self):
        selected = []
        for i in range(self.language_list.count()):
            item = self.language_list.item(i)
            checkbox = self.language_list.itemWidget(item)
            
            if checkbox.isChecked():
                lang_code = checkbox.property("lang_code")
                selected.append(lang_code)
        
        return selected
        
class CustomTaskDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.row_height = 25
    
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if not index.parent().isValid():
            size.setHeight(self.row_height)
        return size
    
    def paint(self, painter, option, index):
        if index.parent().isValid():
            super().paint(painter, option, index)
            return
        
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)
        
        painter.save()
        
        primary_font = option.font
        secondary_font = QFont(option.font)
        secondary_font.setPointSize(max(6, int(option.font.pointSize() * 0.8)))
        
        indicator_font = QFont(option.font)
        indicator_font.setPointSize(max(6, int(option.font.pointSize() * 0.7)))
        
        if index.column() == 2:
            full_text = str(index.data()) if index.data() else ""
            primary_text = full_text.split('\n')[0] if full_text else ""
            
            indicator_text = ""
            if hasattr(index.model(), 'get_description_source'):
                indicator_text = index.model().get_description_source(index)
            
            available_width = option.rect.width() - 16
            
            indicator_width = 0
            if indicator_text:
                painter.setFont(indicator_font)
                indicator_metrics = painter.fontMetrics()
                indicator_width = indicator_metrics.horizontalAdvance(indicator_text) + 8
            
            painter.setFont(primary_font)
            text_metrics = painter.fontMetrics()
            
            text_width_available = available_width - indicator_width
            text_width_needed = text_metrics.horizontalAdvance(primary_text)
            
            display_text = primary_text
            show_indicator = True
            
            if text_width_needed > text_width_available:
                if text_width_available > 30:
                    truncated_width = text_width_available - text_metrics.horizontalAdvance("...")
                    display_text = text_metrics.elidedText(primary_text, Qt.ElideRight, truncated_width)
                else:
                    show_indicator = False
                    text_width_available = available_width
                    if text_width_needed > text_width_available:
                        truncated_width = text_width_available - text_metrics.horizontalAdvance("...")
                        display_text = text_metrics.elidedText(primary_text, Qt.ElideRight, truncated_width)
            
            primary_rect = QRect(option.rect.left() + 4, option.rect.top(), 
                               text_width_available + 4, option.rect.height())
            
            painter.drawText(primary_rect, Qt.AlignLeft | Qt.AlignVCenter, display_text)
            
            if show_indicator and indicator_text:
                indicator_rect = QRect(option.rect.right() - indicator_width, option.rect.top(),
                                     indicator_width - 4, option.rect.height())
                painter.setFont(indicator_font)
                painter.drawText(indicator_rect, Qt.AlignRight | Qt.AlignVCenter, indicator_text)
        
        elif index.column() == 0:
            primary_text = str(index.data()) if index.data() else ""
            
            secondary_text = ""
            if hasattr(index.model(), 'get_secondary_info'):
                secondary_text = index.model().get_secondary_info(index)
            
            primary_rect = QRect(option.rect.left() + 4, option.rect.top() + 2, 
                               option.rect.width() - 8, option.rect.height() // 2)
            secondary_rect = QRect(option.rect.left() + 4, option.rect.top() + option.rect.height() // 2, 
                                 option.rect.width() - 8, option.rect.height() // 2)
            
            painter.setFont(primary_font)
            painter.drawText(primary_rect, Qt.AlignLeft | Qt.AlignVCenter, primary_text)
            
            if secondary_text:
                painter.setFont(secondary_font)
                painter.drawText(secondary_rect, Qt.AlignLeft | Qt.AlignVCenter, secondary_text)
        
        else:
            primary_text = str(index.data()) if index.data() else ""
            primary_rect = QRect(option.rect.left() + 4, option.rect.top(), 
                               option.rect.width() - 8, option.rect.height())
            
            painter.setFont(primary_font)
            painter.drawText(primary_rect, Qt.AlignLeft | Qt.AlignVCenter, primary_text)
        
        painter.restore()

class CustomTaskModel(QStandardItemModel):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
    
    def get_secondary_info(self, index):
        if index.column() != 0:
            return ""
        
        row = index.row()
        if row < len(self.main_window.tasks):
            task = self.main_window.tasks[row]
            task_type = task.get("task_type", "subtitle")
            languages = task.get("languages", [])
            
            if task_type == "video+subtitle":
                type_text = "Video+Subtitle"
            elif task_type == "video":
                type_text = "Video"
            else:
                type_text = "Subtitle"
            
            lang_text = ", ".join(languages)
            return f"Type: {type_text}  Translating to: {lang_text}"
        
        return ""
    
    def get_description_source(self, index):
        if index.column() != 2:
            return ""
        
        row = index.row()
        if row < len(self.main_window.tasks):
            task = self.main_window.tasks[row]
            return task.get("description_source", "Manual")
        
        return "Manual"

class TranslationWorker(QObject):
    finished = Signal(int, str, bool)
    progress_update = Signal(int, int, str)
    status_message = Signal(int, str)
    language_completed = Signal(int, str, bool)
    
    def __init__(self, task_index, input_file_path, target_languages, api_key, api_key2, model_name, settings, description="", queue_manager=None, main_window=None):
        super().__init__()
        self.task_index = task_index
        self.input_file_path = input_file_path
        self.target_languages = target_languages
        self.api_key = api_key
        self.api_key2 = api_key2
        self.model_name = model_name
        self.settings = settings
        self.description = description
        self.queue_manager = queue_manager
        self.main_window = main_window
        
        self.force_cancelled = False
        self.current_language = None
        self.process = None
        self.is_extracting = False
        self.pending_force_cancellation = False
    
    def _should_stop_gracefully(self):
        if self.main_window:
            return self.main_window.stop_after_current_task
        return False
    
    def _should_force_cancel(self):
        return self.force_cancelled
    
    def _read_stream(self, stream, q):
        try:
            for line in iter(stream.readline, ''):
                q.put(line)
        except (IOError, ValueError):
            pass
        finally:
            try:
                stream.close()
            except (IOError, ValueError):
                pass
    
    def _run_and_monitor_subprocess(self, cmd, line_callback, process_cwd):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        creation_flags = 0
        if os.name == 'nt':
            creation_flags = subprocess.CREATE_NO_WINDOW

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            env=env,
            cwd=process_cwd,
            creationflags=creation_flags
        )

        q = queue.Queue()
        
        stdout_thread = threading.Thread(target=self._read_stream, args=(self.process.stdout, q), daemon=True)
        stderr_thread = threading.Thread(target=self._read_stream, args=(self.process.stderr, q), daemon=True)
        
        stdout_thread.start()
        stderr_thread.start()

        while self.process.poll() is None:
            if self._should_force_cancel():
                self._send_interrupt_signal()
                break
            try:
                line = q.get(timeout=0.1)
                line_callback(line)
            except queue.Empty:
                continue

        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._send_interrupt_signal()
            
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

        while not q.empty():
            try:
                line = q.get_nowait()
                line_callback(line)
            except queue.Empty:
                break
            
        return_code = self.process.returncode if self.process else -1
        self.process = None
        
        if self._should_force_cancel():
            return -1

        return return_code

    def _extract_audio_pass(self):
        try:
            queue_entry = self.queue_manager.state["queue_state"].get(self.input_file_path, {})
            video_file = queue_entry.get("video_file")
            
            if not video_file or not os.path.exists(video_file):
                self.status_message.emit(self.task_index, "Video file not found")
                return False
            
            self.status_message.emit(self.task_index, "Extracting Audio")
            self.queue_manager.set_audio_extraction_status(self.input_file_path, "extracting")
            
            executable_path = get_executable_path()
            
            if is_compiled():
                cmd = [executable_path, "--run-audio-extraction"]
            else:
                cmd = [sys.executable, executable_path, "--run-audio-extraction"]
            
            cmd.extend(["--gemini_api_key", "DUMMY_KEY_FOR_AUDIO_EXTRACTION_ONLY"])

            cmd.extend(["--video_file", video_file])
            cmd.extend(["--model_name", self.model_name])
            
            def audio_line_callback(line):
                if not line: return
                clean_line = line.strip()
                if "Starting audio extraction" in clean_line:
                    self.progress_update.emit(self.task_index, 30, "Starting audio extraction...")
                elif "Success! Audio saved as:" in clean_line:
                    self.progress_update.emit(self.task_index, 90, "Audio extraction completed")
                
            process_cwd = get_app_directory()
            self._run_and_monitor_subprocess(cmd, audio_line_callback, process_cwd)
            
            if self._should_force_cancel():
                self._cleanup_current_language_only()
                return False

            video_basename = os.path.basename(video_file)
            video_name = os.path.splitext(video_basename)[0]
            video_dir = os.path.dirname(video_file)
            expected_audio = os.path.join(video_dir, f"{video_name}_extracted.mp3")
            expected_subtitle = os.path.join(video_dir, f"{video_name}_extracted.srt")
            
            if os.path.exists(expected_audio):
                self.queue_manager.set_audio_extraction_status(
                    self.input_file_path, "completed", expected_audio
                )
                if os.path.exists(expected_subtitle):
                    if self.input_file_path in self.queue_manager.state["queue_state"]:
                        self.queue_manager.state["queue_state"][self.input_file_path]["extracted_subtitle_file"] = expected_subtitle
                        self.queue_manager._save_queue_state()
                self.status_message.emit(self.task_index, "Audio extraction successful")
                return True
            else:
                self.queue_manager.set_audio_extraction_status(self.input_file_path, "failed")
                self.status_message.emit(self.task_index, "Audio extraction failed")
                return False
    
        except Exception as e:
            print(f"Critical error in _extract_audio_pass: {e}")
            self.queue_manager.set_audio_extraction_status(self.input_file_path, "failed")
            return False

    def _execute_translation_command(self, cmd, lang_code, completed_count, total_languages):
        lang_name = self._get_language_name(lang_code)
        
        if total_languages > 1:
            if self.queue_manager and self.input_file_path in self.queue_manager.state["queue_state"]:
                languages = self.queue_manager.state["queue_state"][self.input_file_path].get("languages", {})
                actual_completed = sum(1 for lang_data in languages.values() if lang_data.get("status") == "completed")
                current_position = actual_completed + 1
            else:
                current_position = completed_count + 1
                
            simple_status = f"Translating {lang_name} {current_position}/{total_languages}"
        else:
            simple_status = f"Translating {lang_name}"
        
        self.status_message.emit(self.task_index, simple_status)
        
        found_completion = [False]

        def translation_line_callback(line):
            if not line: return
            line = line.strip()

            if "Resuming from line" in line:
                resume_match = re.search(r"Resuming from line (\d+)", line)
                if resume_match:
                    resume_line = resume_match.group(1)
                    self.status_message.emit(self.task_index, f"Resuming {lang_name} from line {resume_line}")
                return

            progress_match = re.search(r"Translating:\s*\|.*\|\s*(\d+)%\s*\(([^)]+)\)[^|]*\|\s*(Thinking|Processing)", line)
            
            if progress_match:
                lang_percent = int(progress_match.group(1))
                details = progress_match.group(2)
                state = progress_match.group(3)
                progress_bar_text = f"{lang_percent}% - {details} | {state}..."
                self.progress_update.emit(self.task_index, lang_percent, progress_bar_text)
                return

            elif "Translation completed successfully!" in line:
                found_completion[0] = True
            
            elif "error" in line.lower() or "traceback" in line.lower():
                print(f"GST subprocess error: {line}")

        process_cwd = os.path.dirname(self.input_file_path)
        return_code = self._run_and_monitor_subprocess(cmd, translation_line_callback, process_cwd)

        self.is_extracting = False
        self.pending_force_cancellation = False

        if self._should_force_cancel() or return_code == -1:
            self._cleanup_current_language_only()
            return False
        
        return return_code == 0 and found_completion[0]
        
    def _generate_output_filename(self, lang_code):
        original_basename = os.path.basename(self.input_file_path)
        subtitle_parsed = _parse_subtitle_filename(original_basename)
        
        if subtitle_parsed and subtitle_parsed['base_name']:
            name_part = subtitle_parsed['base_name']
        else:
            name_part = _strip_language_codes_from_name(os.path.splitext(original_basename)[0])
        
        pattern = self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.{modifiers}.srt")
    
        file_lang_code = lang_code
        if file_lang_code.startswith('zh'):
            file_lang_code = 'zh'
        elif file_lang_code.startswith('pt'):
            file_lang_code = 'pt'
        
        modifiers = _build_modifiers_string(subtitle_parsed)
        
        final_name = pattern.format(
            original_name=name_part, 
            lang_code=file_lang_code,
            modifiers=modifiers
        )
        
        final_name = _clean_filename_dots(final_name)
        
        original_dir = os.path.dirname(self.input_file_path)
        return os.path.join(original_dir, final_name)
    
    def _get_progress_file_path(self):
        original_basename = os.path.basename(self.input_file_path)
        name_part, ext = os.path.splitext(original_basename)
        progress_filename = f"{name_part}.progress"
        original_dir = os.path.dirname(self.input_file_path)
        return os.path.join(original_dir, progress_filename)
    
    def _detect_progress_file(self):
        progress_file = self._get_progress_file_path()
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                    progress_line = progress_data.get("line", None)
                    
                    if self.queue_manager:
                        current_lang = self.queue_manager.get_current_language_in_progress(self.input_file_path)
                        if current_lang:
                            return progress_line, current_lang
                    
                    return progress_line, None
            except Exception as e:
                print(f"Error reading progress file {progress_file}: {e}")
                return None, None
        return None, None
        
    def _cleanup_for_fresh_start(self, target_language):
        try:
            progress_file = self._get_progress_file_path()
            if os.path.exists(progress_file):
                os.remove(progress_file)
            
            app_dir_progress = os.path.join(get_app_directory(), os.path.basename(progress_file))
            if os.path.exists(app_dir_progress):
                os.remove(app_dir_progress)
            
            output_file = self._generate_output_filename(target_language)
            if os.path.exists(output_file):
                os.remove(output_file)
                
        except Exception as e:
            print(f"Error cleaning up files for fresh start: {e}")
    
    def _build_cli_command(self, target_language):
        executable_path = get_executable_path()
        
        if is_compiled():
            cmd = [executable_path, "--run-gst-subprocess"]
        else:
            cmd = [sys.executable, executable_path, "--run-gst-subprocess"]
        
        cmd.extend(["--gemini_api_key", self.api_key])
        cmd.extend(["--target_language", target_language])
        cmd.extend(["--input_file", self.input_file_path])
        cmd.extend(["--model_name", self.model_name])
        
        output_path = self._generate_output_filename(target_language)
        cmd.extend(["--output_file", output_path])
        
        if self.api_key2:
            cmd.extend(["--gemini_api_key2", self.api_key2])
        
        if self.description:
            cmd.extend(["--description", self.description])
        
        extracted_audio = self.queue_manager.get_extracted_audio_file(self.input_file_path)
        if extracted_audio and os.path.exists(extracted_audio):
            cmd.extend(["--audio_file", extracted_audio])
        
        progress_line, progress_lang = self._detect_progress_file()
        if progress_line is not None:
            self._cleanup_for_fresh_start(target_language)
        
        if self.settings.get("use_gst_parameters", False):
            cmd.extend(["--batch_size", str(self.settings.get("batch_size", 30))])
            
            if not self.settings.get("free_quota", True):
                cmd.extend(["--free_quota", "False"])
            else:
                cmd.extend(["--free_quota", "True"])
                
            if self.settings.get("skip_upgrade", False):
                cmd.extend(["--skip_upgrade", "True"])
            if self.settings.get("progress_log", False):
                cmd.extend(["--progress_log", "True"])
            if self.settings.get("thoughts_log", False):
                cmd.extend(["--thoughts_log", "True"])
    
        cmd.extend(["--use_colors", "False"])
    
        if self.settings.get("use_model_tuning", False):
            cmd.extend(["--temperature", str(self.settings.get("temperature", 0.7))])
            cmd.extend(["--top_p", str(self.settings.get("top_p", 0.95))])
            cmd.extend(["--top_k", str(self.settings.get("top_k", 40))])
            cmd.extend(["--thinking_budget", str(self.settings.get("thinking_budget", 2048))])
            
            if not self.settings.get("streaming", True):
                cmd.extend(["--streaming", "False"])
            else:
                cmd.extend(["--streaming", "True"])
                
            if not self.settings.get("thinking", True):
                cmd.extend(["--thinking", "False"])
            else:
                cmd.extend(["--thinking", "True"])
        
        return cmd
        
    def _build_video_only_command(self, video_file, target_language):
        executable_path = get_executable_path()
        
        if is_compiled():
            cmd = [executable_path, "--run-gst-subprocess"]
        else:
            cmd = [sys.executable, executable_path, "--run-gst-subprocess"]
        
        cmd.extend(["--gemini_api_key", self.api_key])
        cmd.extend(["--target_language", target_language])
        cmd.extend(["--video_file", video_file])
        cmd.extend(["--model_name", self.model_name])
        
        output_path = self._generate_output_filename(target_language)
        cmd.extend(["--output_file", output_path])
        
        if self.api_key2:
            cmd.extend(["--gemini_api_key2", self.api_key2])
        
        if self.description:
            cmd.extend(["--description", self.description])
        
        if self.settings.get("use_gst_parameters", False):
            cmd.extend(["--batch_size", str(self.settings.get("batch_size", 30))])
            
            if not self.settings.get("free_quota", True):
                cmd.extend(["--free_quota", "False"])
            else:
                cmd.extend(["--free_quota", "True"])
                
            if self.settings.get("skip_upgrade", False):
                cmd.extend(["--skip_upgrade", "True"])
            if self.settings.get("progress_log", False):
                cmd.extend(["--progress_log", "True"])
            if self.settings.get("thoughts_log", False):
                cmd.extend(["--thoughts_log", "True"])
    
        cmd.extend(["--use_colors", "False"])
    
        if self.settings.get("use_model_tuning", False):
            cmd.extend(["--temperature", str(self.settings.get("temperature", 0.7))])
            cmd.extend(["--top_p", str(self.settings.get("top_p", 0.95))])
            cmd.extend(["--top_k", str(self.settings.get("top_k", 40))])
            cmd.extend(["--thinking_budget", str(self.settings.get("thinking_budget", 2048))])
            
            if not self.settings.get("streaming", True):
                cmd.extend(["--streaming", "False"])
            else:
                cmd.extend(["--streaming", "True"])
                
            if not self.settings.get("thinking", True):
                cmd.extend(["--thinking", "False"])
            else:
                cmd.extend(["--thinking", "True"])
        
        return cmd
    
    def _get_language_name(self, lang_code):
        for name, (two_letter, three_letter) in LANGUAGES.items():
            if two_letter == lang_code:
                return name
        return lang_code.upper()
    
    def _send_interrupt_signal(self):
        process = self.process
        if process and process.poll() is None:
            try:
                if os.name == 'nt':
                    subprocess.run(f"taskkill /F /T /PID {process.pid}", shell=True, timeout=3, capture_output=True)
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=1)
                except:
                    pass
                
    def _cleanup_all_task_files(self):
        try:
            progress_file = self._get_progress_file_path()
            if os.path.exists(progress_file):
                os.remove(progress_file)
            
            app_dir_progress = os.path.join(get_app_directory(), os.path.basename(progress_file))
            if os.path.exists(app_dir_progress):
                os.remove(app_dir_progress)
            
            original_basename = os.path.basename(self.input_file_path)
            original_dir = os.path.dirname(self.input_file_path)
            
            subtitle_parsed = _parse_subtitle_filename(original_basename)
            if subtitle_parsed and subtitle_parsed['base_name']:
                name_part = subtitle_parsed['base_name']
            else:
                name_part = _strip_language_codes_from_name(os.path.splitext(original_basename)[0])
            
            pattern = self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.{modifiers}.srt")
            
            for lang_code in self.target_languages:
                file_lang_code = lang_code
                if file_lang_code.startswith('zh'):
                    file_lang_code = 'zh'
                elif file_lang_code.startswith('pt'):
                    file_lang_code = 'pt'
                
                modifiers = _build_modifiers_string(subtitle_parsed)
                
                output_filename = pattern.format(
                    original_name=name_part, 
                    lang_code=file_lang_code,
                    modifiers=modifiers
                )
                
                output_filename = _clean_filename_dots(output_filename)
                output_file = os.path.join(original_dir, output_filename)
                
                if not os.path.exists(output_file):
                    continue
                    
                if os.path.normpath(self.input_file_path) == os.path.normpath(output_file):
                    continue
                
                input_parsed = _parse_subtitle_filename(os.path.basename(self.input_file_path))
                output_parsed = _parse_subtitle_filename(os.path.basename(output_file))
                
                if (input_parsed and output_parsed and 
                    input_parsed['base_name'] == output_parsed['base_name'] and
                    input_parsed['modifiers_string'] == output_parsed['modifiers_string']):
                    
                    input_lang_normalized = _normalize_language_code(input_parsed['lang_code']) if input_parsed['lang_code'] else None
                    output_lang_normalized = _normalize_language_code(output_parsed['lang_code']) if output_parsed['lang_code'] else None
                    
                    if input_lang_normalized == output_lang_normalized == lang_code:
                        continue
                
                os.remove(output_file)
    
            if self.queue_manager:
                files_to_delete = set()
                
                state_managed_subtitle = self.queue_manager.get_extracted_subtitle_file(self.input_file_path)
                if state_managed_subtitle:
                    files_to_delete.add(state_managed_subtitle)
    
                queue_entry = self.queue_manager.state["queue_state"].get(self.input_file_path, {})
                source_file_for_naming = queue_entry.get("video_file") or self.input_file_path
                
                base_dir = os.path.dirname(source_file_for_naming)
                file_name_without_ext = os.path.splitext(os.path.basename(source_file_for_naming))[0]
                file_name_without_ext = _strip_language_codes_from_name(file_name_without_ext)
    
                predicted_subtitle_path = os.path.join(base_dir, f"{file_name_without_ext}_extracted.srt")
                files_to_delete.add(predicted_subtitle_path)
    
                for file_path in files_to_delete:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                
                should_cleanup_audio = self.settings.get("cleanup_audio_on_cancel", False)
                
                if should_cleanup_audio:
                    audio_file = self.queue_manager.get_extracted_audio_file(self.input_file_path)
                    if audio_file and os.path.exists(audio_file):
                        os.remove(audio_file)
                    
                    self.queue_manager.cleanup_extracted_audio(self.input_file_path)
                else:
                    if self.input_file_path in self.queue_manager.state["queue_state"]:
                        self.queue_manager.state["queue_state"][self.input_file_path]["extracted_subtitle_file"] = None
                        self.queue_manager._save_queue_state()
                
                for lang_code in self.target_languages:
                    self.queue_manager.mark_language_queued(self.input_file_path, lang_code)
                
                if should_cleanup_audio:
                    queue_entry = self.queue_manager.state["queue_state"].get(self.input_file_path, {})
                    if queue_entry.get("requires_audio_extraction", False):
                        self.queue_manager.set_audio_extraction_status(self.input_file_path, "pending")
            
        except Exception as e:
            pass
                
    def run(self):
        if self._should_force_cancel():
            self._cleanup_current_language_only()
            progress_summary = self.queue_manager.get_language_progress_summary(self.input_file_path)
            self.finished.emit(self.task_index, progress_summary, False)
            return
    
        if not self.queue_manager:
            self.finished.emit(self.task_index, "Queue manager not available", False)
            return
    
        queue_entry = self.queue_manager.state["queue_state"].get(self.input_file_path, {})
        task_type = queue_entry.get("task_type", "subtitle")
        
        success = False
        if task_type == "video+subtitle":
            success = self._handle_video_subtitle_workflow()
        elif task_type == "video":
            success = self._handle_video_only_workflow()
        else:
            success = self._handle_subtitle_only_workflow()
        
        if self._should_force_cancel():
            self._cleanup_current_language_only()
            progress_summary = self.queue_manager.get_language_progress_summary(self.input_file_path)
            self.finished.emit(self.task_index, progress_summary, False)
        elif self._should_stop_gracefully():
            progress_summary = self.queue_manager.get_language_progress_summary(self.input_file_path)
            if progress_summary == "Translated":
                self.finished.emit(self.task_index, "Translated", True)
            else:
                self.finished.emit(self.task_index, progress_summary, success)
        elif success:
            self.finished.emit(self.task_index, "Translated", True)
        else:
            self.finished.emit(self.task_index, "Translation failed", False)
            
    def _handle_video_subtitle_workflow(self):
        languages_needing_work = []
        for lang_code in self.target_languages:
            should_skip, skip_reason = self._should_skip_language(lang_code)
            if not should_skip:
                languages_needing_work.append(lang_code)
            else:
                if skip_reason == "same_as_input":
                    self.status_message.emit(self.task_index, f"Skipped {self._get_language_name(lang_code)} - same as input file")
                elif skip_reason == "exists":
                    self.status_message.emit(self.task_index, f"Skipped {self._get_language_name(lang_code)} - file already exists")
                
                self.queue_manager.mark_language_completed(self.input_file_path, lang_code)
                self.language_completed.emit(self.task_index, lang_code, True)
        
        if not languages_needing_work:
            return True
        
        if self.queue_manager.should_extract_audio(self.input_file_path):
            success = self._extract_audio_pass()
            if not success or self._should_force_cancel():
                return False
        
        return self._translate_with_languages()
    
    def _handle_video_only_workflow(self):
        if self._should_force_cancel():
            return False
            
        queue_entry = self.queue_manager.state["queue_state"].get(self.input_file_path, {})
        video_file = queue_entry.get("video_file", self.input_file_path)
        
        if not os.path.exists(video_file):
            self.status_message.emit(self.task_index, "Video file not found")
            return False
        
        completed_count = 0
        total_languages = len(self.target_languages)
        
        for lang_code in self.target_languages:
            if self._should_force_cancel():
                return False
            
            should_skip, skip_reason = self._should_skip_language(lang_code)
            if should_skip:
                if skip_reason == "same_as_input":
                    self.status_message.emit(self.task_index, f"Skipped {self._get_language_name(lang_code)} - same as input file")
                elif skip_reason == "exists":
                    self.status_message.emit(self.task_index, f"Skipped {self._get_language_name(lang_code)} - file already exists")
                
                self.queue_manager.mark_language_completed(self.input_file_path, lang_code)
                completed_count += 1
                self.language_completed.emit(self.task_index, lang_code, True)
                continue
            
            if self._should_stop_gracefully() and completed_count > 0:
                break
                
            self.current_language = lang_code
            lang_name = self._get_language_name(lang_code)
            
            try:
                self.queue_manager.mark_language_in_progress(self.input_file_path, lang_code)
                self.status_message.emit(self.task_index, f"Extracting and translating to {lang_name}...")
                
                cmd = self._build_video_only_command(video_file, lang_code)
                
                success = self._execute_translation_command(cmd, lang_code, completed_count, total_languages)
                
                if self._should_force_cancel():
                    return False
                
                if success:
                    self.queue_manager.mark_language_completed(self.input_file_path, lang_code)
                    completed_count += 1
                    self.language_completed.emit(self.task_index, lang_code, True)
                else:
                    self.queue_manager.mark_language_queued(self.input_file_path, lang_code)
                    self.language_completed.emit(self.task_index, lang_code, False)
                    
            except Exception as e:
                print(f"Exception during video-only translation of {lang_code}: {e}")
                self.queue_manager.mark_language_queued(self.input_file_path, lang_code)
                self.language_completed.emit(self.task_index, lang_code, False)
        
        if self._should_force_cancel():
            return False
        
        final_summary = self.queue_manager.get_language_progress_summary(self.input_file_path)
        if final_summary == "Translated":
            self.queue_manager.cleanup_completed_subtitle(self.input_file_path)
            return True
        else:
            return completed_count > 0
    
    def _handle_subtitle_only_workflow(self):
        return self._translate_with_languages()
    
    def _translate_with_languages(self):
        completed_count = 0
        total_languages = len(self.target_languages)
        
        while True:
            if self._should_force_cancel():
                return False
            
            next_lang = self.queue_manager.get_next_language_to_process(self.input_file_path)
            if not next_lang:
                break
            
            should_skip, skip_reason = self._should_skip_language(next_lang)
            if should_skip:
                if skip_reason == "same_as_input":
                    self.status_message.emit(self.task_index, f"Skipped {self._get_language_name(next_lang)} - same as input file")
                elif skip_reason == "exists":
                    self.status_message.emit(self.task_index, f"Skipped {self._get_language_name(next_lang)} - file already exists")
                
                self.queue_manager.mark_language_completed(self.input_file_path, next_lang)
                self.language_completed.emit(self.task_index, next_lang, True)
                completed_count += 1
                continue
            
            if self._should_stop_gracefully() and completed_count > 0:
                break
            
            self.current_language = next_lang
            lang_name = self._get_language_name(next_lang)
            
            try:
                self.queue_manager.mark_language_in_progress(self.input_file_path, next_lang)
                
                self.status_message.emit(self.task_index, f"Translating to {lang_name}...")
                
                cmd = self._build_cli_command(next_lang)
                
                success = self._execute_translation_command(cmd, next_lang, completed_count, total_languages)
                
                if self._should_force_cancel():
                    return False
                
                if success:
                    self.queue_manager.mark_language_completed(self.input_file_path, next_lang)
                    completed_count += 1
                    self.language_completed.emit(self.task_index, next_lang, True)
                else:
                    self.queue_manager.mark_language_queued(self.input_file_path, next_lang)
                    self.language_completed.emit(self.task_index, next_lang, False)
    
            except Exception as e:
                print(f"Exception during translation of {next_lang}: {e}")
                if self._should_force_cancel():
                    return False
                else:
                    self.queue_manager.mark_language_queued(self.input_file_path, next_lang)
                    self.language_completed.emit(self.task_index, next_lang, False)
    
        if self._should_force_cancel():
            return False
        
        final_summary = self.queue_manager.get_language_progress_summary(self.input_file_path)
        if final_summary == "Translated":
            self.queue_manager.cleanup_completed_subtitle(self.input_file_path)
            return True
        else:
            return completed_count > 0
            
    def _should_skip_language(self, lang_code):
        output_path = self._generate_output_filename(lang_code)
        
        if os.path.normpath(self.input_file_path) == os.path.normpath(output_path):
            return True, "same_as_input"
        
        if os.path.exists(output_path):
            handling = self.settings.get("existing_file_handling", "skip")
            if handling == "skip":
                return True, "exists"
        
        return False, None
        
    def _cleanup_current_language_only(self):
        try:
            progress_file = self._get_progress_file_path()
            if os.path.exists(progress_file):
                os.remove(progress_file)
            
            app_dir_progress = os.path.join(get_app_directory(), os.path.basename(progress_file))
            if os.path.exists(app_dir_progress):
                os.remove(app_dir_progress)
    
            if self.current_language:
                original_basename = os.path.basename(self.input_file_path)
                original_dir = os.path.dirname(self.input_file_path)
                
                subtitle_parsed = _parse_subtitle_filename(original_basename)
                if subtitle_parsed and subtitle_parsed['base_name']:
                    name_part = subtitle_parsed['base_name']
                else:
                    name_part = _strip_language_codes_from_name(os.path.splitext(original_basename)[0])
                
                pattern = self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.{modifiers}.srt")
                
                file_lang_code = self.current_language
                if file_lang_code.startswith('zh'):
                    file_lang_code = 'zh'
                elif file_lang_code.startswith('pt'):
                    file_lang_code = 'pt'
                
                modifiers = _build_modifiers_string(subtitle_parsed)
                
                output_filename = pattern.format(
                    original_name=name_part, 
                    lang_code=file_lang_code,
                    modifiers=modifiers
                )
                
                output_filename = _clean_filename_dots(output_filename)
                output_file = os.path.join(original_dir, output_filename)
    
                if (os.path.exists(output_file) and 
                    os.path.normpath(self.input_file_path) != os.path.normpath(output_file)):
                    
                    input_parsed = _parse_subtitle_filename(os.path.basename(self.input_file_path))
                    output_parsed = _parse_subtitle_filename(os.path.basename(output_file))
                    
                    safe_to_delete = True
                    if (input_parsed and output_parsed and 
                        input_parsed['base_name'] == output_parsed['base_name'] and
                        input_parsed['modifiers_string'] == output_parsed['modifiers_string']):
                        
                        input_lang_normalized = _normalize_language_code(input_parsed['lang_code']) if input_parsed['lang_code'] else None
                        output_lang_normalized = _normalize_language_code(output_parsed['lang_code']) if output_parsed['lang_code'] else None
                        
                        if input_lang_normalized == output_lang_normalized == self.current_language:
                            safe_to_delete = False
                    
                    if safe_to_delete:
                        for attempt in range(3):
                            try:
                                os.remove(output_file)
                                break
                            except (PermissionError, OSError):
                                if attempt < 2:
                                    import time
                                    time.sleep(0.5)
                                else:
                                    pass
                
                if self.queue_manager:
                    self.queue_manager.mark_language_queued(self.input_file_path, self.current_language)
            
            if self.queue_manager:
                files_to_delete = set()
                
                state_managed_subtitle = self.queue_manager.get_extracted_subtitle_file(self.input_file_path)
                if state_managed_subtitle:
                    files_to_delete.add(state_managed_subtitle)
    
                queue_entry = self.queue_manager.state["queue_state"].get(self.input_file_path, {})
                source_file_for_naming = queue_entry.get("video_file") or self.input_file_path
                
                base_dir = os.path.dirname(source_file_for_naming)
                file_name_without_ext = os.path.splitext(os.path.basename(source_file_for_naming))[0]
                file_name_without_ext = _strip_language_codes_from_name(file_name_without_ext)
    
                predicted_subtitle_path = os.path.join(base_dir, f"{file_name_without_ext}_extracted.srt")
                files_to_delete.add(predicted_subtitle_path)
    
                for file_path in files_to_delete:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                
                should_cleanup_audio = self.settings.get("cleanup_audio_on_cancel", False)
                
                if should_cleanup_audio:
                    audio_file = self.queue_manager.get_extracted_audio_file(self.input_file_path)
                    if audio_file and os.path.exists(audio_file):
                        try:
                            os.remove(audio_file)
                        except:
                            pass
                    
                    self.queue_manager.cleanup_extracted_audio(self.input_file_path)
                else:
                    if self.input_file_path in self.queue_manager.state["queue_state"]:
                        self.queue_manager.state["queue_state"][self.input_file_path]["extracted_subtitle_file"] = None
                        self.queue_manager._save_queue_state()
                
                if should_cleanup_audio:
                    queue_entry = self.queue_manager.state["queue_state"].get(self.input_file_path, {})
                    if queue_entry.get("requires_audio_extraction", False):
                        self.queue_manager.set_audio_extraction_status(self.input_file_path, "pending")
            
            app_dir = get_app_directory()
            default_output = os.path.join(app_dir, "translated.srt")
            if os.path.exists(default_output):
                os.remove(default_output)
                
        except Exception as e:
            pass
    
    def force_cancel(self):
        self.force_cancelled = True
        self.status_message.emit(self.task_index, "Force cancelling...")
        
        process = self.process
        if process and process.poll() is None:
            self._send_interrupt_signal()
    
    def cancel(self):
        self.force_cancel()

class CustomLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._right_text = ""
        self._right_text_font = QFont()
        self._right_text_color = QColor(128, 128, 128)
        self._right_text_margin = 10
        self._base_right_margin = 0
        
    def set_right_text(self, text, font_size=10, bold=False, italic=False, color=None):
        self._right_text = text
        
        self._right_text_font = QFont()
        self._right_text_font.setPointSize(font_size)
        self._right_text_font.setBold(bold)
        self._right_text_font.setItalic(italic)
        
        if color:
            if isinstance(color, str):
                self._right_text_color = QColor(color)
            elif isinstance(color, QColor):
                self._right_text_color = color
            elif isinstance(color, tuple) and len(color) == 3:
                self._right_text_color = QColor(color[0], color[1], color[2])
        
        self._update_text_margins()
        self.update()
    
    def set_right_text_margin(self, margin):
        self._right_text_margin = margin
        self._update_text_margins()
        self.update()
    
    def clear_right_text(self):
        self._right_text = ""
        self._update_text_margins()
        self.update()
    
    def _update_text_margins(self):
        if self._right_text:
            font_metrics = QFontMetrics(self._right_text_font)
            right_text_width = font_metrics.horizontalAdvance(self._right_text)
            
            right_margin = right_text_width + self._right_text_margin + self._base_right_margin
            
            margins = self.textMargins()
            self.setTextMargins(margins.left(), margins.top(), right_margin, margins.bottom())
        else:
            margins = self.textMargins()
            self.setTextMargins(margins.left(), margins.top(), self._base_right_margin, margins.bottom())
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._right_text:
            self._update_text_margins()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        if not self._right_text:
            return
        
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            
            painter.setFont(self._right_text_font)
            painter.setPen(self._right_text_color)
            
            font_metrics = QFontMetrics(self._right_text_font)
            text_width = font_metrics.horizontalAdvance(self._right_text)
            text_height = font_metrics.height()
            
            widget_rect = self.rect()
            
            text_x = widget_rect.width() - text_width - self._right_text_margin
            text_y = (widget_rect.height() + text_height) // 2 - font_metrics.descent()
            
            painter.drawText(text_x, text_y, self._right_text)
        finally:
            painter.end()

class CustomTitleBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(40)
        self.setObjectName("CustomTitleBar")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(5)
        
        self.title_widget = GradientTitleWidget("Gemini SRT Translator")
        self.setObjectName("AppTitle")
        layout.addWidget(self.title_widget)
        
        layout.addStretch()
        
        self.language_selection_btn = HoverPushButton(get_resource_path("Files/language.svg"))
        self.language_selection_btn.setObjectName("TitleBarButton")
        self.language_selection_btn.setFixedHeight(30)
        self.language_selection_btn.setText("Language Selection")
        layout.addWidget(self.language_selection_btn)
        
        self.settings_btn = HoverPushButton(get_resource_path("Files/cog.svg"))
        self.settings_btn.setObjectName("TitleBarButton")
        self.settings_btn.setFixedHeight(30)
        self.settings_btn.setText("Settings")
        
        layout.addWidget(self.settings_btn)
        
        separator = QFrame()
        separator.setObjectName("TitleBarSeparator")
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        window_controls_layout = QHBoxLayout()
        window_controls_layout.setContentsMargins(0, 0, 0, 0)
        
        self.minimize_btn = HoverToolButton(get_resource_path("Files/window-minimize.svg"))
        self.minimize_btn.setObjectName("WindowControlButton")
        self.minimize_btn.setFixedSize(40, 40)
        self.minimize_btn.clicked.connect(self.minimize_window)
        
        self.maximize_btn = HoverToolButton(get_resource_path("Files/window-maximize.svg"))
        self.maximize_btn.setObjectName("WindowControlButton")
        self.maximize_btn.setFixedSize(40, 40)
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        
        self.close_btn = HoverToolButton(
            get_resource_path("Files/window-close.svg"),
            normal_color="#A0A0A0",
            hover_color="white"
        )
        self.close_btn.setObjectName("WindowCloseButton")
        self.close_btn.setFixedSize(40, 40)
        self.close_btn.clicked.connect(self.close_window)
        
        self.maximize_normal_icon = load_svg(get_resource_path("Files/window-maximize.svg"), "#A0A0A0")
        self.restore_normal_icon = load_svg(get_resource_path("Files/window-restore.svg"), "#A0A0A0")
        self.maximize_hover_icon = load_svg(get_resource_path("Files/window-maximize.svg"), "white")
        self.restore_hover_icon = load_svg(get_resource_path("Files/window-restore.svg"), "white")
        
        window_controls_layout.addWidget(self.minimize_btn)
        window_controls_layout.addWidget(self.maximize_btn)
        window_controls_layout.addWidget(self.close_btn)
        
        window_controls_widget = QWidget()
        window_controls_widget.setLayout(window_controls_layout)
        layout.addWidget(window_controls_widget)
    
    def minimize_window(self):
        if self.parent_window:
            self.parent_window.minimize()
    
    def toggle_maximize(self):
        if self.parent_window:
            self.parent_window.toggleMaximize()
            
            if self.parent_window.isMaximized():
                self.maximize_btn.normal_icon = self.restore_normal_icon
                self.maximize_btn.hover_icon = self.restore_hover_icon
                self.maximize_btn.setIcon(self.restore_normal_icon)
            else:
                self.maximize_btn.normal_icon = self.maximize_normal_icon
                self.maximize_btn.hover_icon = self.maximize_hover_icon
                self.maximize_btn.setIcon(self.maximize_normal_icon)
    
    def close_window(self):
        if self.parent_window:
            self.parent_window.close()

class MainWindow(FramelessWidget):
    def __init__(self):
        super().__init__(hint=['min', 'max', 'close'])
        
        ffmpeg_available = setup_ffmpeg_path()
        if not ffmpeg_available:
            print("Warning: FFmpeg not found. Video+subtitle tasks may fail.")
        
        self.setWindowTitle("Gemini SRT Translator")
        
        window_width = 1100
        window_height = 750
        self.resize(window_width, window_height)
        
        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.move(x, y)
        
        icon_path = get_resource_path("Files/icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.tasks = []
        self.current_task_index = -1
        self.settings = self._load_settings()
        self.active_thread = None
        self.active_worker = None
        self.clipboard_description = ""
        self.is_running = False
        self.stop_after_current_task = False
        self._exit_timer = None
        
        self.api_key1_validated = False
        self.api_key2_validated = False
        self.last_validated_key1 = ""
        self.last_validated_key2 = ""
        
        self.tmdb_lookup_workers = {}
        self.tmdb_threads = {}
        self.tmdb_api_key_validated = False
        self.last_validated_tmdb_key = ""
        
        title_bar = self.getTitleBar()
        title_bar.setTitleBarFont(QFont('Arial', 12))
        title_bar.setIconSize(24, 24)
        
        self.custom_title_bar = CustomTitleBarWidget(self)
        
        title_bar_layout = title_bar.layout()
        if title_bar_layout:
            while title_bar_layout.count():
                child = title_bar_layout.takeAt(0)
                if child.widget():
                    child.widget().setParent(None)
            title_bar_layout.addWidget(self.custom_title_bar)
        
        self.custom_title_bar.settings_btn.clicked.connect(self.open_settings_dialog)
        self.custom_title_bar.language_selection_btn.clicked.connect(self.open_language_selection)
        
        main_layout = self.layout()
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(6, 6, 6, 6)
        
        config_layout = QFormLayout()

        api_keys_model_layout = QHBoxLayout()
        
        self.api_key_edit = CustomLineEdit()
        self.api_key_edit.setPlaceholderText("Enter Gemini API Key")
        self.api_key_edit.set_right_text("API Key 1", font_size=9, italic=False, color="#555555")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setText(self.settings.get("gemini_api_key", ""))
        self.api_key_edit.textChanged.connect(self.on_api_key1_changed)
        api_keys_model_layout.addWidget(self.api_key_edit)
        
        self.api_key2_edit = CustomLineEdit()
        self.api_key2_edit.setPlaceholderText("Enter Gemini API Key (optional)")
        self.api_key2_edit.set_right_text("API Key 2", font_size=9, italic=False, color="#555555")
        self.api_key2_edit.setEchoMode(QLineEdit.Password)
        self.api_key2_edit.setText(self.settings.get("gemini_api_key2", ""))
        self.api_key2_edit.textChanged.connect(self.on_api_key2_changed)
        api_keys_model_layout.addWidget(self.api_key2_edit)
        
        self.tmdb_api_key_edit = CustomLineEdit()
        self.tmdb_api_key_edit.setPlaceholderText("Enter TMDB API Key (optional)")
        self.tmdb_api_key_edit.set_right_text("TMDB API Key", font_size=9, italic=False, color="#555555")
        self.tmdb_api_key_edit.setEchoMode(QLineEdit.Password)
        self.tmdb_api_key_edit.setText(self.settings.get("tmdb_api_key", ""))
        self.tmdb_api_key_edit.textChanged.connect(self.on_tmdb_api_key_changed)
        api_keys_model_layout.addWidget(self.tmdb_api_key_edit)
        
        self.model_name_edit = CustomLineEdit()
        self.model_name_edit.setText(self.settings.get("model_name", "gemini-2.5-flash"))
        self.model_name_edit.set_right_text("Model Used", font_size=9, italic=False, color="#555555")
        self.model_name_edit.textChanged.connect(lambda text: self.settings.update({"model_name": text}))
        api_keys_model_layout.addWidget(self.model_name_edit)
        
        config_layout.addRow(api_keys_model_layout)
        
        content_layout.addLayout(config_layout)
        
        self.tree_view = QTreeView()
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setRootIsDecorated(True)
        self.tree_view.setUniformRowHeights(False)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)
        
        self.model = CustomTaskModel(self)
        self.model.setHorizontalHeaderLabels(["Files", "Movie", "Description", "Status"])
        self.model.itemChanged.connect(self.on_item_changed)
        
        self.custom_delegate = CustomTaskDelegate()
        self.tree_view.setItemDelegate(self.custom_delegate)
        self.tree_view.setModel(self.model)
        
        self.tree_view.setColumnWidth(0, 350)
        self.tree_view.setColumnWidth(1, 150)
        self.tree_view.setColumnWidth(2, 250)
        self.tree_view.setColumnWidth(3, 150)
        self.tree_view.setMinimumHeight(250)
        
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.AscendingOrder)
        
        header = self.tree_view.header()
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
        
        content_layout.addWidget(self.tree_view)
        
        controls_widget = QWidget()
        controls_widget.setFixedHeight(30)
        
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        controls_layout.addStretch()
        
        button_group = QWidget()
        button_layout = QHBoxLayout(button_group)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.add_btn = HoverPushButton(get_resource_path("Files/add.svg"))
        self.add_btn.setObjectName("ControlButton")
        self.add_btn.setText("Add Subtitles")
        self.add_btn.setFixedWidth(120)
        self.add_btn.setFixedHeight(28)
        self.add_btn.clicked.connect(self.add_files_action)
        button_layout.addWidget(self.add_btn)
        
        self.start_stop_btn = QPushButton("Start Translating")
        self.start_stop_btn.setObjectName("ControlButton")
        
        button_font = self.start_stop_btn.font()
        button_font.setBold(True)
        self.start_stop_btn.setFont(button_font)
        
        self.start_stop_btn.setFixedWidth(320)
        self.start_stop_btn.setFixedHeight(30)
        self.start_stop_btn.clicked.connect(self.toggle_start_stop)
        button_layout.addWidget(self.start_stop_btn)
        
        self.clear_btn = HoverPushButton(
            get_resource_path("Files/clear.svg"),
            normal_color="#A0A0A0", 
            hover_color="#d32f2f"
        )
        self.clear_btn.setObjectName("ControlButton")
        self.clear_btn.setText("Clear Queue")
        self.clear_btn.setFixedWidth(120)
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.clicked.connect(self.clear_queue_action)
        self.clear_btn.setEnabled(False)
        button_layout.addWidget(self.clear_btn)
        
        controls_layout.addWidget(button_group)
        
        controls_layout.addStretch()
        
        self.selected_languages = self.settings.get("selected_languages", ["en"])
        
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setTextVisible(True)
        self.overall_progress_bar.setFormat("%p% - Current Task")
        self.overall_progress_bar.setVisible(False)
        content_layout.addWidget(self.overall_progress_bar)
        
        content_layout.addWidget(controls_widget)
        
        main_layout.addWidget(content_widget)
        
        queue_state_file = get_persistent_path(os.path.join("Files", "queue_state.json"))
        self.queue_manager = QueueStateManager(queue_state_file)
        
        self._sync_ui_with_queue_state()
        
        self.update_button_states()
        
    def _sync_ui_with_queue_state(self):
        queue_state = self.queue_manager.state.get("queue_state", {})
        
        for subtitle_path, subtitle_data in queue_state.items():
            if not os.path.exists(subtitle_path):
                continue
                
            target_languages = subtitle_data.get("target_languages", [])
            description = subtitle_data.get("description", "")
            task_type = subtitle_data.get("task_type", "subtitle")
            video_file = subtitle_data.get("video_file")
            
            if task_type == "video+subtitle":
                if not video_file or not os.path.exists(video_file):
                    task_type = "subtitle"
                    subtitle_data["task_type"] = "subtitle"
                    subtitle_data["video_file"] = None
                    subtitle_data["requires_audio_extraction"] = False
                    self.queue_manager._save_queue_state()
            
            task_exists = any(task['path'] == subtitle_path and task['languages'] == target_languages for task in self.tasks)
            
            if not task_exists:
                self._add_task_to_ui(subtitle_path, target_languages, description, task_type)
                
                for task in self.tasks:
                    if task['path'] == subtitle_path:
                        summary = self.queue_manager.get_language_progress_summary(subtitle_path)
                        task["status_item"].setText(summary)
                        break
    
    def _add_task_to_ui(self, file_path, languages, description, task_type="subtitle"):
        lang_display = self._get_language_display_text(languages)
        
        if task_type == "video+subtitle":
            if is_video_file(file_path):
                video_path = file_path
                subtitle_path = self._find_subtitle_pair(file_path)
            else:
                subtitle_path = file_path
                video_path = self._find_video_pair(file_path)
            
            video_item = QStandardItem(os.path.basename(video_path))
            video_item.setToolTip(os.path.dirname(video_path))
            video_item.setEditable(False)
            
            movie_item = QStandardItem("")
            movie_item.setEditable(False)
            
            desc_item = QStandardItem(description)
            desc_item.setEditable(True)
            desc_item.setToolTip(description)
            
            status_item = QStandardItem("Queued")
            status_item.setEditable(False)
            
            subtitle_child = QStandardItem(f"{os.path.basename(subtitle_path)}")
            subtitle_child.setToolTip(f"Subtitle: {subtitle_path}")
            subtitle_child.setEditable(False)
            
            video_item.appendRow([subtitle_child, QStandardItem(""), QStandardItem(""), QStandardItem("")])
            
            self.model.appendRow([video_item, movie_item, desc_item, status_item])
            
            self.tasks.append({
                "path": subtitle_path,
                "video_path": video_path,
                "path_item": video_item, 
                "movie_item": movie_item,
                "desc_item": desc_item, 
                "status_item": status_item, 
                "description": description,
                "description_source": "Manual",
                "languages": languages.copy(),
                "task_type": task_type,
                "worker": None, 
                "thread": None
            })
            
        else:
            path_item = QStandardItem(os.path.basename(file_path))
            path_item.setToolTip(os.path.dirname(file_path))
            path_item.setEditable(False)
            
            movie_item = QStandardItem("")
            movie_item.setEditable(False)
            
            desc_item = QStandardItem(description)
            desc_item.setEditable(True)
            desc_item.setToolTip(description)
            
            status_item = QStandardItem("Queued")
            status_item.setEditable(False)
            
            self.model.appendRow([path_item, movie_item, desc_item, status_item])
            self.tasks.append({
                "path": file_path, 
                "path_item": path_item, 
                "movie_item": movie_item,
                "desc_item": desc_item, 
                "status_item": status_item, 
                "description": description,
                "description_source": "Manual",
                "languages": languages.copy(),
                "task_type": task_type,
                "worker": None, 
                "thread": None
            })
        
    def _get_language_display_text(self, lang_codes):
        if len(lang_codes) <= 2:
            language_names = self._get_language_names_from_codes(lang_codes)
            return ", ".join(language_names)
        else:
            return ", ".join(lang_codes)

    def toggle_start_stop(self):
        if self.is_running:
            if self.stop_after_current_task:
                current_task_name = ""
                if 0 <= self.current_task_index < len(self.tasks):
                    task_path = self.tasks[self.current_task_index]["path"]
                    current_task_name = os.path.basename(task_path)
                
                reply = CustomMessageBox.question(
                    self, 
                    'Force Cancel Current Language', 
                    f'Force cancel the current translation?\n\nFile: {current_task_name}',
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.No,
                    "WARNING: This will immediately stop the translation and DELETE progress for the current language. Completed languages will be preserved."
                )
                if reply == QMessageBox.Yes:
                    self.force_stop_translation()
            else:
                self.stop_translation_action()
        else:
            self.start_translation_queue()
            
    def force_stop_translation(self):
        if self.active_worker and self.is_running:
            self.stop_after_current_task = True
            self.start_stop_btn.setText("Cancelling...")
            self.start_stop_btn.setEnabled(False)
            
            self.active_worker.force_cancel()

    def on_item_changed(self, item):
        if item.column() == 2:
            row = item.row()
            if 0 <= row < len(self.tasks):
                self.tasks[row]["description"] = item.text()
                self.tasks[row]["description_source"] = "Manual"
                item.setToolTip(item.text())

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            current_index = self.tree_view.currentIndex()
            if current_index.isValid() and current_index.column() == 3:
                item = self.model.itemFromIndex(current_index)
                if item:
                    self.clipboard_description = item.text()
        elif event.matches(QKeySequence.Paste):
            current_index = self.tree_view.currentIndex()
            if current_index.isValid() and current_index.column() == 3:
                item = self.model.itemFromIndex(current_index)
                if item:
                    item.setText(self.clipboard_description)
                    item.setToolTip(self.clipboard_description)
                    row = current_index.row()
                    if 0 <= row < len(self.tasks):
                        self.tasks[row]["description"] = self.clipboard_description
        else:
            super().keyPressEvent(event)

    def _on_sort_indicator_changed(self, logical_index, order):
        if self.active_thread and self.active_thread.isRunning():
            CustomMessageBox.warning(self, "Cannot Sort", 
                              "Translation in progress. Stop it before sorting.")
            self.tree_view.setSortingEnabled(False)
            self._rebuild_model_from_tasks()
            self.tree_view.setSortingEnabled(True)
            return
        
        QTimer.singleShot(0, self._sync_tasks_with_sorted_model)

    def _sync_tasks_with_sorted_model(self):
        if self.active_thread and self.active_thread.isRunning():
            return
        
        new_tasks = []
        for row in range(self.model.rowCount()):
            path_item = self.model.item(row, 0)
            lang_item = self.model.item(row, 1)
            type_item = self.model.item(row, 2)
            desc_item = self.model.item(row, 3)
            status_item = self.model.item(row, 4)
            
            for task in self.tasks:
                if (task["path_item"] is path_item and 
                    task["lang_item"] is lang_item and 
                    task["type_item"] is type_item and
                    task["desc_item"] is desc_item and
                    task["status_item"] is status_item):
                    new_tasks.append(task)
                    break
        
        self.tasks = new_tasks
        self.current_task_index = -1

    def _rebuild_model_from_tasks(self):
        col_widths = []
        for i in range(self.model.columnCount()):
            col_widths.append(self.tree_view.columnWidth(i))
        
        header = self.tree_view.header()
        sort_column = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        
        was_sorting_enabled = self.tree_view.isSortingEnabled()
        self.tree_view.setSortingEnabled(False)
        
        self.model.clear()
        self.model.setHorizontalHeaderLabels(["File Name", "Output Languages", "Type", "Description", "Status"])
        
        for task in self.tasks:
            self.model.appendRow([task["path_item"], task["lang_item"], task["type_item"], task["desc_item"], task["status_item"]])
        
        for i, width in enumerate(col_widths):
            if i < self.model.columnCount():
                self.tree_view.setColumnWidth(i, width)
        
        if was_sorting_enabled:
            self.tree_view.setSortingEnabled(True)
            if sort_column >= 0:
                self.tree_view.sortByColumn(sort_column, sort_order)
    
    def _format_language_tooltip(self, lang_codes, max_display=5):
        language_names = self._get_language_names_from_codes(lang_codes)
        if len(language_names) <= max_display:
            return ", ".join(language_names)
        else:
            displayed = ", ".join(language_names[:max_display])
            remaining = len(language_names) - max_display
            return f"{displayed} and {remaining} more..."
                
    def open_language_selection(self):
        dialog = LanguageSelectionDialog(self.selected_languages, self)
        if dialog.exec():
            old_languages = self.selected_languages.copy()
            self.selected_languages = dialog.get_selected_languages()
            self.settings["selected_languages"] = self.selected_languages
            
            if (old_languages != self.selected_languages and 
                self.settings.get("update_existing_queue_languages", True)):
                
                new_lang_display = self._get_language_display_text(self.selected_languages)
                new_lang_tooltip = self._format_language_tooltip(self.selected_languages)
                
                for task in self.tasks:
                    if task["languages"] == old_languages:
                        task["lang_item"].setText(new_lang_display)
                        task["lang_item"].setToolTip(new_lang_tooltip)
                        task["languages"] = self.selected_languages.copy()
                        
                        self.queue_manager.update_subtitle_languages(
                            task["path"], 
                            self.selected_languages, 
                            task["description"],
                            self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.srt")
                        )
            
            self._save_settings()
    
    @Slot(int, str, bool)
    def on_language_completed(self, task_idx, lang_code, success):
        pass

    def show_context_menu(self, position):
        if self.active_thread and self.active_thread.isRunning():
            return
            
        item = self.tree_view.indexAt(position)
        if not item.isValid():
            return
        
        if item.parent().isValid():
            return
        
        selected_rows = self._get_selected_task_rows()
        if not selected_rows:
            return
        
        menu = QMenu(self)
        
        if len(selected_rows) == 1:
            edit_desc_action = QAction("Edit Description", self)
            edit_desc_action.triggered.connect(self.edit_single_description)
            menu.addAction(edit_desc_action)
            
            row = selected_rows[0]
            if 0 <= row < len(self.tasks):
                current_desc = self.tasks[row]["description"]
                if current_desc:
                    copy_desc_action = QAction("Copy Description", self)
                    copy_desc_action.triggered.connect(self.copy_description)
                    menu.addAction(copy_desc_action)
        
        if len(selected_rows) > 1:
            bulk_edit_action = QAction("Bulk Edit Description", self)
            bulk_edit_action.triggered.connect(self.bulk_edit_description)
            menu.addAction(bulk_edit_action)
        
        if self.clipboard_description:
            should_show_apply = True
            if len(selected_rows) == 1:
                row = selected_rows[0]
                if 0 <= row < len(self.tasks):
                    current_desc = self.tasks[row]["description"]
                    if current_desc == self.clipboard_description:
                        should_show_apply = False
            
            if should_show_apply:
                preview = self.clipboard_description[:10] + "..." if len(self.clipboard_description) > 10 else self.clipboard_description
                apply_desc_action = QAction(f"Apply Copied Description ({preview})", self)
                apply_desc_action.triggered.connect(self.apply_copied_description)
                menu.addAction(apply_desc_action)
        
        if menu.actions():
            menu.addSeparator()
        
        edit_languages_action = QAction("Edit Languages", self)
        edit_languages_action.triggered.connect(self.edit_selected_languages)
        menu.addAction(edit_languages_action)
        
        if self.settings.get("use_tmdb", False) and self.tmdb_api_key_edit.text().strip():
            menu.addSeparator()
            refresh_tmdb_action = QAction("Refresh TMDB Info", self)
            refresh_tmdb_action.triggered.connect(self.refresh_tmdb_info)
            menu.addAction(refresh_tmdb_action)
        
        if menu.actions():
            menu.addSeparator()
        
        move_to_top_action = QAction("Move to Top", self)
        move_to_top_action.triggered.connect(self.move_selected_to_top)
        menu.addAction(move_to_top_action)
        
        move_up_action = QAction("Move Up", self)
        move_up_action.triggered.connect(self.move_selected_up)
        menu.addAction(move_up_action)
        
        move_down_action = QAction("Move Down", self)
        move_down_action.triggered.connect(self.move_selected_down)
        menu.addAction(move_down_action)
        
        move_to_bottom_action = QAction("Move to Bottom", self)
        move_to_bottom_action.triggered.connect(self.move_selected_to_bottom)
        menu.addAction(move_to_bottom_action)
        
        menu.addSeparator()
        
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(self.remove_selected_items)
        menu.addAction(remove_action)
        
        has_non_queued = False
        for row in selected_rows:
            if 0 <= row < len(self.tasks):
                if self.tasks[row]["status_item"].text() != "Queued":
                    has_non_queued = True
                    break
        
        if has_non_queued:
            reset_action = QAction("Reset Status", self)
            reset_action.triggered.connect(self.reset_selected_status)
            menu.addAction(reset_action)
        
        menu.exec(self.tree_view.mapToGlobal(position))

    def copy_description(self):
        selected_rows = self._get_selected_task_rows()
        if len(selected_rows) == 1:
            row = selected_rows[0]
            if 0 <= row < len(self.tasks):
                self.clipboard_description = self.tasks[row]["description"]
    
    def apply_copied_description(self):
        if not self.clipboard_description:
            return
        
        selected_rows = self._get_selected_task_rows()
        for row in selected_rows:
            if 0 <= row < len(self.tasks):
                self.tasks[row]["desc_item"].setText(self.clipboard_description)
                self.tasks[row]["desc_item"].setToolTip(self.clipboard_description)
                self.tasks[row]["description"] = self.clipboard_description
                self.tasks[row]["description_source"] = "Manual"
    
    def edit_single_description(self):
        selected_rows = self._get_selected_task_rows()
        if len(selected_rows) != 1:
            return
        
        row = selected_rows[0]
        if 0 <= row < len(self.tasks):
            current_desc = self.tasks[row]["description"]
            dialog = BulkDescriptionDialog(current_desc, self)
            dialog.setWindowTitle("Edit Description")
            if dialog.exec():
                new_description = dialog.get_description()
                self.tasks[row]["desc_item"].setText(new_description)
                self.tasks[row]["desc_item"].setToolTip(new_description)
                self.tasks[row]["description"] = new_description
                self.tasks[row]["description_source"] = "Manual"
    
    def bulk_edit_description(self):
        selected_rows = self._get_selected_task_rows()
        if not selected_rows:
            return
        
        current_desc = ""
        if len(selected_rows) == 1:
            row = selected_rows[0]
            if 0 <= row < len(self.tasks):
                current_desc = self.tasks[row]["description"]
        else:
            descriptions = []
            for row in selected_rows:
                if 0 <= row < len(self.tasks):
                    desc = self.tasks[row]["description"]
                    if desc:
                        descriptions.append(desc)
            
            if len(descriptions) == 1:
                current_desc = descriptions[0]
        
        dialog = BulkDescriptionDialog(current_desc, self)
        if dialog.exec():
            new_description = dialog.get_description()
            for row in selected_rows:
                if 0 <= row < len(self.tasks):
                    self.tasks[row]["desc_item"].setText(new_description)
                    self.tasks[row]["desc_item"].setToolTip(new_description)
                    self.tasks[row]["description"] = new_description
                    self.tasks[row]["description_source"] = "Manual"

    def move_selected_to_top(self):
        if self.active_thread and self.active_thread.isRunning():
            return
            
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        rows = sorted([index.row() for index in selected_indexes])
        
        selected_tasks = [self.tasks[row] for row in rows if 0 <= row < len(self.tasks)]
        
        for row in reversed(rows):
            if 0 <= row < len(self.tasks):
                self.tasks.pop(row)
        
        for i, task in enumerate(selected_tasks):
            self.tasks.insert(i, task)
        
        self._rebuild_model_from_tasks()
        
        self.tree_view.clearSelection()
        for i in range(len(selected_tasks)):
            self.tree_view.selectionModel().select(
                self.model.index(i, 0), 
                QItemSelectionModel.Select | QItemSelectionModel.Rows
            )

    def move_selected_up(self):
        if self.active_thread and self.active_thread.isRunning():
            return
            
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        rows = sorted([index.row() for index in selected_indexes])
        
        if rows[0] == 0:
            return
        
        for row in rows:
            if row > 0:
                self.tasks[row], self.tasks[row-1] = self.tasks[row-1], self.tasks[row]
        
        self._rebuild_model_from_tasks()
        
        self.tree_view.clearSelection()
        for row in rows:
            new_row = max(0, row - 1)
            self.tree_view.selectionModel().select(
                self.model.index(new_row, 0), 
                QItemSelectionModel.Select | QItemSelectionModel.Rows
            )

    def move_selected_down(self):
        if self.active_thread and self.active_thread.isRunning():
            return
            
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        rows = sorted([index.row() for index in selected_indexes], reverse=True)
        
        if rows[0] >= len(self.tasks) - 1:
            return
        
        for row in rows:
            if row < len(self.tasks) - 1:
                self.tasks[row], self.tasks[row+1] = self.tasks[row+1], self.tasks[row]
        
        self._rebuild_model_from_tasks()
        
        self.tree_view.clearSelection()
        for row in reversed(rows):
            new_row = min(len(self.tasks) - 1, row + 1)
            self.tree_view.selectionModel().select(
                self.model.index(new_row, 0), 
                QItemSelectionModel.Select | QItemSelectionModel.Rows
            )

    def move_selected_to_bottom(self):
        if self.active_thread and self.active_thread.isRunning():
            return
            
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        rows = sorted([index.row() for index in selected_indexes], reverse=True)
        
        selected_tasks = []
        for row in rows:
            if 0 <= row < len(self.tasks):
                selected_tasks.append(self.tasks.pop(row))
        
        selected_tasks.reverse()
        
        start_index = len(self.tasks)
        for task in selected_tasks:
            self.tasks.append(task)
        
        self._rebuild_model_from_tasks()
        
        self.tree_view.clearSelection()
        for i in range(len(selected_tasks)):
            row_index = start_index + i
            self.tree_view.selectionModel().select(
                self.model.index(row_index, 0), 
                self.tree_view.selectionModel().Select | self.tree_view.selectionModel().Rows
            )

    def remove_selected_items(self):
        if self.active_thread and self.active_thread.isRunning():
            return
            
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        rows_to_remove = sorted([index.row() for index in selected_indexes], reverse=True)
        
        for row in rows_to_remove:
            if 0 <= row < len(self.tasks):
                task = self.tasks[row]
                
                self._cleanup_task_audio_and_extracted_files(task["path"], "remove")
                
                self.queue_manager.remove_subtitle_from_queue(task["path"])
                
                self.tasks.pop(row)
                self.model.removeRow(row)
        
        self.update_button_states()

    def reset_selected_status(self):
        if self.active_thread and self.active_thread.isRunning():
            return
            
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        selected_rows = self._get_selected_task_rows()
        if not selected_rows:
            return
        
        reset_count = 0
        for row in selected_rows:
            if 0 <= row < len(self.tasks):
                task = self.tasks[row]
                task_path = task["path"]
                current_status = task["status_item"].text()
                
                if current_status != "Queued":
                    task["status_item"].setText("Queued")
                    
                    if task_path in self.queue_manager.state["queue_state"]:
                        languages = self.queue_manager.state["queue_state"][task_path].get("languages", {})
                        for lang_code in languages.keys():
                            self.queue_manager.mark_language_queued(task_path, lang_code)
                    
                    original_basename = os.path.basename(task_path)
                    original_dir = os.path.dirname(task_path)
                    
                    subtitle_parsed = _parse_subtitle_filename(original_basename)
                    if subtitle_parsed and subtitle_parsed['base_name']:
                        name_part = subtitle_parsed['base_name']
                    else:
                        name_part = _strip_language_codes_from_name(os.path.splitext(original_basename)[0])
                    
                    progress_file = os.path.join(original_dir, f"{name_part}.progress")
                    if os.path.exists(progress_file):
                        try:
                            os.remove(progress_file)
                        except Exception as e:
                            pass
                            
                    extracted_subtitle = self.queue_manager.get_extracted_subtitle_file(task_path)
                    if extracted_subtitle and os.path.exists(extracted_subtitle):
                        try:
                            os.remove(extracted_subtitle)
                        except Exception as e:
                            pass
                    
                    should_cleanup_audio = self.settings.get("cleanup_audio_on_cancel", False)
                    if should_cleanup_audio:
                        audio_file = self.queue_manager.get_extracted_audio_file(task_path)
                        if audio_file and os.path.exists(audio_file):
                            try:
                                os.remove(audio_file)
                            except Exception as e:
                                pass
                        
                        self.queue_manager.cleanup_extracted_audio(task_path)
                    else:
                        if task_path in self.queue_manager.state["queue_state"]:
                            self.queue_manager.state["queue_state"][task_path]["extracted_subtitle_file"] = None
                            self.queue_manager._save_queue_state()
                    
                    if task_path in self.queue_manager.state["queue_state"]:
                        queue_entry = self.queue_manager.state["queue_state"][task_path]
                        if queue_entry.get("requires_audio_extraction", False):
                            if should_cleanup_audio:
                                self.queue_manager.set_audio_extraction_status(task_path, "pending")
                            else:
                                audio_file = self.queue_manager.get_extracted_audio_file(task_path)
                                if audio_file and os.path.exists(audio_file):
                                    self.queue_manager.set_audio_extraction_status(task_path, "completed", audio_file)
                                else:
                                    self.queue_manager.set_audio_extraction_status(task_path, "pending")
                    
                    reset_count += 1
        
        if reset_count > 0:
            self.update_button_states()

    def _load_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    loaded_s = json.load(f)
                    s = DEFAULT_SETTINGS.copy()
                    s.update(loaded_s)
                    return s
        except Exception as e:
            pass
        
        return DEFAULT_SETTINGS.copy()

    def _save_settings(self):
        try:
            self.settings["gemini_api_key"] = self.api_key_edit.text()
            self.settings["gemini_api_key2"] = self.api_key2_edit.text()
            self.settings["tmdb_api_key"] = self.tmdb_api_key_edit.text()
            self.settings["model_name"] = self.model_name_edit.text()
            self.settings["selected_languages"] = self.selected_languages
            
            config_dir = os.path.dirname(CONFIG_FILE)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir, exist_ok=True)
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            CustomMessageBox.warning(self, "Save Settings Error", f"Could not save settings: {e}")

    def closeEvent(self, event):
        self._save_settings()
        if self.active_thread and self.active_thread.isRunning():
            current_task_name = ""
            if 0 <= self.current_task_index < len(self.tasks):
                task_path = self.tasks[self.current_task_index]["path"]
                current_task_name = f"\n\nCurrent file: {os.path.basename(task_path)}"
            
            reply = CustomMessageBox.question(
                self, 
                'Confirm Exit', 
                f"Force cancel translation and exit?{current_task_name}",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No,
                "WARNING: This will immediately stop the translation and DELETE progress for the current language. Completed languages will be preserved."
            )
            if reply == QMessageBox.Yes:
                if self.active_worker:
                    self.active_worker.force_cancel()
                
                self._exit_timer = QTimer()
                self._exit_timer.timeout.connect(lambda: self._check_translation_stopped(event))
                self._exit_timer.start(100)
                
                event.ignore()
            else:
                event.ignore()
        else:
            self._perform_exit()
            event.accept()
    
    def _check_translation_stopped(self, event):
        if not self.is_running and (not self.active_thread or not self.active_thread.isRunning()):
            self._exit_timer.stop()
            self._exit_timer = None
            self._perform_exit()
            self.close()
    
    def _perform_exit(self):
        queue_on_exit = self.settings.get("queue_on_exit", "clear_if_translated")
        
        for task in self.tasks:
            task_path = task["path"]
            extracted_subtitle_file = self.queue_manager.get_extracted_subtitle_file(task_path)
            if extracted_subtitle_file and os.path.exists(extracted_subtitle_file):
                try:
                    os.remove(extracted_subtitle_file)
                except Exception as e:
                    pass
        
        if queue_on_exit == "clear":
            self._cleanup_all_task_files()
            self.queue_manager.clear_all_state()
        elif queue_on_exit == "clear_if_translated":
            all_translated = True
            for task in self.tasks:
                summary = self.queue_manager.get_language_progress_summary(task["path"])
                if summary != "Translated":
                    all_translated = False
                    break
            
            if all_translated:
                self._cleanup_all_task_files()
                self.queue_manager.clear_all_state()

    def add_files_action(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Subtitle or Video Files", 
            "", 
            "Media Files (*.srt *.mp4 *.mkv *.avi *.mov);;SRT Files (*.srt);;Video Files (*.mp4 *.mkv *.avi *.mov);;All Files (*)"
        )
        if files:
            video_files = [f for f in files if is_video_file(f)]
            subtitle_files = [f for f in files if is_subtitle_file(f)]
            
            processed_files = set()
            tasks_to_add = []
            
            for subtitle_path in subtitle_files:
                if subtitle_path in processed_files:
                    continue
                    
                video_pair = None
                for video_path in video_files:
                    if video_path in processed_files:
                        continue
                        
                    if self._files_are_pair(subtitle_path, video_path):
                        video_pair = video_path
                        break
                
                if video_pair:
                    task_type = "video+subtitle"
                    primary_file = subtitle_path
                    
                    processed_files.add(subtitle_path)
                    processed_files.add(video_pair)
                    
                    tasks_to_add.append({
                        'primary_file': primary_file,
                        'video_file': video_pair,
                        'task_type': task_type,
                        'requires_extraction': True
                    })
                else:
                    processed_files.add(subtitle_path)
                    tasks_to_add.append({
                        'primary_file': subtitle_path,
                        'video_file': None,
                        'task_type': 'subtitle',
                        'requires_extraction': False
                    })
            
            for video_path in video_files:
                if video_path not in processed_files:
                    tasks_to_add.append({
                        'primary_file': video_path,
                        'video_file': video_path,
                        'task_type': 'video',
                        'requires_extraction': False
                    })
            
            for task_info in tasks_to_add:
                primary_file = task_info['primary_file']
                
                if any(task['path'] == primary_file and task['languages'] == self.selected_languages for task in self.tasks):
                    continue
                
                self.queue_manager.add_subtitle_to_queue(
                    primary_file, 
                    self.selected_languages.copy(), 
                    "", 
                    self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.srt"),
                    task_info['task_type'],
                    task_info['video_file'],
                    task_info['requires_extraction']
                )
                
                self._add_task_to_ui(primary_file, self.selected_languages.copy(), "", task_info['task_type'])
                
                video_file_for_lookup = task_info.get('video_file', primary_file)
                self._start_tmdb_lookup(video_file_for_lookup if video_file_for_lookup != primary_file else primary_file)
            
            self.update_button_states()

    def start_translation_queue(self):
        key_status = self.validate_both_api_keys()
        
        if not key_status['key1_provided']:
            CustomMessageBox.warning(self, "API Key Missing", "Please enter a primary Gemini API Key.")
            self.api_key_edit.setFocus()
            return
        
        if not key_status['key1_valid']:
            CustomMessageBox.warning(self, "Invalid Primary API Key", 
                                   "The primary API key is invalid. Please verify your key.")
            self.api_key_edit.setFocus()
            return
        
        if key_status['key2_provided'] and not key_status['key2_valid']:
            CustomMessageBox.warning(self, "Invalid Secondary API Key", 
                                   "The secondary API key is invalid. Please verify your key.")
            self.api_key2_edit.setFocus()
            return
                
        if self.active_thread and self.active_thread.isRunning():
            CustomMessageBox.information(self, "In Progress", "A translation is already in progress.")
            return
        
        if not self.queue_manager.has_any_work_remaining():
            CustomMessageBox.information(self, "Queue Status", "No work remaining in queue.")
            return
            
        self.model.blockSignals(True)
        for task in self.tasks:
            if task.get("desc_item"):
                task["desc_item"].setEditable(False)
        self.model.blockSignals(False)
        
        first_task_with_work = -1
        for i, task_data in enumerate(self.tasks):
            next_lang = self.queue_manager.get_next_language_to_process(task_data["path"])
            if next_lang:
                first_task_with_work = i
                break
                
        if first_task_with_work == -1:
            CustomMessageBox.information(self, "Queue Status", "No work remaining in queue.")
            return
            
        self.current_task_index = first_task_with_work
        self._process_task_at_index(self.current_task_index)
        self.update_button_states()
    
    def _process_task_at_index(self, task_idx):
        if not (0 <= task_idx < len(self.tasks)):
            self._handle_queue_finished()
            return
            
        task = self.tasks[task_idx]
        
        next_lang = self.queue_manager.get_next_language_to_process(task["path"])
        if not next_lang:
            self._find_and_process_next_queued_task()
            return
            
        self.current_task_index = task_idx
        task["status_item"].setText("Preparing")
        self.overall_progress_bar.setVisible(True)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setFormat("Starting...")
        self.is_running = True
        
        self.active_worker = TranslationWorker(
            task_index=task_idx, 
            input_file_path=task["path"], 
            target_languages=task["languages"],
            api_key=self.api_key_edit.text().strip(), 
            api_key2=self.api_key2_edit.text().strip(),
            model_name=self.model_name_edit.text().strip(), 
            settings=self.settings,
            description=task["description"],
            queue_manager=self.queue_manager,
            main_window=self
        )
        
        self.active_thread = QThread(self)
        self.active_worker.moveToThread(self.active_thread)
        self.active_worker.status_message.connect(self.on_worker_status_message)
        self.active_worker.progress_update.connect(self.on_worker_progress_update)
        self.active_worker.finished.connect(self.on_worker_finished)
        self.active_worker.language_completed.connect(self.on_language_completed)
        self.active_thread.started.connect(self.active_worker.run)
        self.active_thread.finished.connect(self.active_worker.deleteLater)
        self.active_thread.finished.connect(self.active_thread.deleteLater)
        self.active_thread.start()
        self.update_button_states()

    def _find_and_process_next_queued_task(self):
        if self.stop_after_current_task:
            self.stop_after_current_task = False
            self.is_running = False
            self.overall_progress_bar.setFormat("Stopped")
            self.overall_progress_bar.setValue(0)
            self._handle_queue_finished()
            return
            
        for i, task in enumerate(self.tasks):
            next_lang = self.queue_manager.get_next_language_to_process(task["path"])
            if next_lang:
                self._process_task_at_index(i)
                return
        
        self._handle_queue_finished()

    def _handle_queue_finished(self):
        self.overall_progress_bar.setVisible(False)
        self.is_running = False
        self.stop_after_current_task = False
        self.update_button_states()
        self.current_task_index = -1
        self._set_queue_items_editable(True)

    @Slot(int, str)
    def on_worker_status_message(self, task_idx, message):
        if 0 <= task_idx < len(self.tasks) and self.current_task_index == task_idx:
            self.tasks[task_idx]["status_item"].setText(message)

    @Slot(int, int, str)
    def on_worker_progress_update(self, task_idx, percentage, progress_text):
        if 0 <= task_idx < len(self.tasks):
            if self.current_task_index == task_idx:
                self.overall_progress_bar.setValue(percentage)
                self.overall_progress_bar.setFormat(progress_text)

    @Slot(int, str, bool)
    def on_worker_finished(self, task_idx, message, success):
        if 0 <= task_idx < len(self.tasks):
            task_path = self.tasks[task_idx]["path"]
            self.tasks[task_idx]["status_item"].setText(message)
            
            self.queue_manager.sync_audio_extraction_status(task_path)
            
            if success:
                progress_summary = self.queue_manager.get_language_progress_summary(task_path)
                if progress_summary == "Translated":
                    self._cleanup_task_audio_and_extracted_files(task_path, "success")
                else:
                    self._cleanup_task_audio_and_extracted_files(task_path, "partial_success")
            else:
                self._cleanup_task_audio_and_extracted_files(task_path, "failure")
            
        if self.active_thread and self.active_thread.isRunning():
            self.active_thread.quit()
            self.active_thread.wait(1000)
            
        self.active_worker = None
        self.active_thread = None
        
        if self.stop_after_current_task:
            self.stop_after_current_task = False
            self.is_running = False
            self.overall_progress_bar.setFormat("Stopped after task completion")
            self.overall_progress_bar.setValue(0)
            QTimer.singleShot(500, self._handle_queue_finished)
            return
        
        if not success:
            self.overall_progress_bar.setFormat("Error") 
            self.overall_progress_bar.setValue(0)
        else:
            self.overall_progress_bar.setValue(100)
            self.overall_progress_bar.setFormat("Completed")
        
        if success and self.is_running:
            QTimer.singleShot(500, self._find_and_process_next_queued_task)
        else:
            QTimer.singleShot(500, self._handle_queue_finished)
            
        self.update_button_states()

    def stop_translation_action(self):
        if self.active_worker and self.is_running:
            self.stop_after_current_task = True
            self.start_stop_btn.setText("Finishing Current Translation...")
            self.start_stop_btn.setEnabled(True)
            
        elif not self.is_running:
            CustomMessageBox.information(self, "Stop", "No active translation to stop.")
            self.update_button_states()
            self._set_queue_items_editable(True)
    
    @Slot()
    def clear_queue_action(self):
        if self.active_thread and self.active_thread.isRunning():
            return
            
        reply = CustomMessageBox.question(self, "Clear Queue", "Remove all items from queue?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._cleanup_all_task_files()
            
            self.queue_manager.clear_all_state()
            
            self.tasks.clear()
            self.model.removeRows(0, self.model.rowCount())
            self.current_task_index = -1
            self.overall_progress_bar.setVisible(False)
            self.active_thread = None
            self.active_worker = None
            self.is_running = False
            self.update_button_states()

    @Slot()
    def open_settings_dialog(self):
        dialog = SettingsDialog(self.settings.copy(), self)
        if dialog.exec():
            self.settings.update(dialog.get_settings())
            self._save_settings()

    def update_button_states(self):
        has_work_remaining = self.queue_manager.has_any_work_remaining()
        is_processing = self.active_thread is not None and self.active_thread.isRunning()
        has_any_tasks = len(self.tasks) > 0
        has_tmdb_operations = bool(self.tmdb_lookup_workers)
        
        key_status = self.validate_both_api_keys()
        
        if self.stop_after_current_task and is_processing:
            self.start_stop_btn.setText("Force Cancel Current Language")
            self.start_stop_btn.setEnabled(True)
        elif self.is_running or is_processing:
            self.start_stop_btn.setText("Stop After Current Language")  
            self.start_stop_btn.setEnabled(True)
        elif has_tmdb_operations:
            self.start_stop_btn.setText("Fetching TMDB Info...")
            self.start_stop_btn.setEnabled(False)
        else:
            if not key_status['key1_provided']:
                self.start_stop_btn.setText("Missing Primary API Key")
                self.start_stop_btn.setEnabled(False)
            elif not key_status['key1_valid']:
                self.start_stop_btn.setText("Invalid Primary API Key")
                self.start_stop_btn.setEnabled(False)
            elif key_status['key2_provided'] and not key_status['key2_valid']:
                self.start_stop_btn.setText("Invalid Secondary API Key")
                self.start_stop_btn.setEnabled(False)
            else:
                self.start_stop_btn.setText("Start Translating")
                self.start_stop_btn.setEnabled(has_work_remaining)
        
        is_busy = is_processing or self.is_running or has_tmdb_operations
        
        self.clear_btn.setEnabled(has_any_tasks and not is_busy)
        self.custom_title_bar.language_selection_btn.setEnabled(not is_busy)
        self.custom_title_bar.settings_btn.setEnabled(not is_busy)
        
    def _get_language_names_from_codes(self, lang_codes):
        unique_codes = list(dict.fromkeys(lang_codes))
        names = []
        for code in unique_codes:
            found_name = None
            for name, (two_letter, three_letter) in LANGUAGES.items():
                if two_letter == code:
                    found_name = name
                    break
            
            if found_name:
                names.append(found_name)
            else:
                names.append(code.upper())
        return names
        
    def edit_selected_languages(self):
        selected_rows = self._get_selected_task_rows()
        if not selected_rows:
            return
        
        current_languages = self.selected_languages.copy()
        
        if len(selected_rows) == 1:
            row = selected_rows[0]
            if 0 <= row < len(self.tasks):
                current_languages = self.tasks[row]["languages"].copy()
        elif len(selected_rows) > 1:
            first_languages = None
            all_same = True
            
            for row in selected_rows:
                if 0 <= row < len(self.tasks):
                    task_languages = self.tasks[row]["languages"]
                    if first_languages is None:
                        first_languages = task_languages.copy()
                    elif set(task_languages) != set(first_languages):
                        all_same = False
                        break
            
            if all_same and first_languages:
                current_languages = first_languages
        
        dialog = LanguageSelectionDialog(current_languages, self)
        dialog.set_title("Edit Output Languages")
        
        if dialog.exec():
            new_languages = dialog.get_selected_languages()
            if not new_languages:
                return
            
            new_lang_display = self._get_language_display_text(new_languages)
            new_lang_tooltip = self._format_language_tooltip(new_languages)
            
            for row in selected_rows:
                if 0 <= row < len(self.tasks):
                    self.tasks[row]["languages"] = new_languages.copy()
                    self.tasks[row]["lang_item"].setText(new_lang_display)
                    self.tasks[row]["lang_item"].setToolTip(new_lang_tooltip)
                    
                    self.queue_manager.update_subtitle_languages(
                        self.tasks[row]["path"], 
                        new_languages, 
                        self.tasks[row]["description"],
                        self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.srt")
                    )
                    
    def _set_queue_items_editable(self, is_editable):
        self.model.blockSignals(True)
        for task in self.tasks:
            if task.get("desc_item"):
                task["desc_item"].setEditable(is_editable)
        self.model.blockSignals(False)
    
    def _find_video_pair(self, subtitle_path):
        subtitle_info = _parse_subtitle_filename(os.path.basename(subtitle_path))
        if not subtitle_info:
            return None
        
        base_dir = os.path.dirname(subtitle_path)
        base_name = subtitle_info['base_name']
        
        for ext in VIDEO_EXTENSIONS:
            video_path = os.path.join(base_dir, base_name + ext)
            if os.path.exists(video_path):
                return video_path
        
        return None
    
    def _find_subtitle_pair(self, video_path):
        base_dir = os.path.dirname(video_path)
        video_name = os.path.basename(video_path)
        video_base = os.path.splitext(video_name)[0]
        
        subtitle_path = os.path.join(base_dir, video_base + ".srt")
        if os.path.exists(subtitle_path):
            return subtitle_path
        
        all_codes = _get_all_language_codes()
        
        for code in all_codes:
            subtitle_path = os.path.join(base_dir, f"{video_base}.{code}.srt")
            if os.path.exists(subtitle_path):
                return subtitle_path
            
            for modifier in ['forced', 'sdh']:
                subtitle_path = os.path.join(base_dir, f"{video_base}.{code}.{modifier}.srt")
                if os.path.exists(subtitle_path):
                    return subtitle_path
            
            subtitle_path = os.path.join(base_dir, f"{video_base}.{code}.forced.sdh.srt")
            if os.path.exists(subtitle_path):
                return subtitle_path
        
        return None
        
    def _should_cleanup_audio(self, scenario):
        scenario_map = {
            "success": "cleanup_audio_on_success",
            "partial_success": None,
            "failure": "cleanup_audio_on_failure", 
            "cancel": "cleanup_audio_on_cancel",
            "remove": "cleanup_audio_on_remove",
            "exit": "cleanup_audio_on_exit"
        }
        
        setting_key = scenario_map.get(scenario)
        if not setting_key:
            return False
            
        should_cleanup = self.settings.get(setting_key, False)
        
        if scenario == "exit" and should_cleanup:
            queue_setting = self.settings.get("queue_on_exit", "clear_if_translated")
            if queue_setting == "clear":
                return True
            elif queue_setting == "clear_if_translated":
                all_translated = all(self.queue_manager.get_language_progress_summary(task["path"]) == "Translated" 
                          for task in self.tasks)
                return all_translated
            elif queue_setting == "keep":
                return False
        
        return should_cleanup
                    
    def _get_selected_task_rows(self):
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        task_rows = []
        
        for index in selected_indexes:
            if not index.parent().isValid():
                task_rows.append(index.row())
        
        return task_rows
        
    def _files_are_pair(self, subtitle_path, video_path):
        subtitle_dir = os.path.dirname(subtitle_path)
        video_dir = os.path.dirname(video_path)
        
        if subtitle_dir != video_dir:
            return False
        
        subtitle_info = _parse_subtitle_filename(os.path.basename(subtitle_path))
        if not subtitle_info:
            return False
        
        video_name = os.path.basename(video_path)
        video_base = os.path.splitext(video_name)[0]
        
        return subtitle_info['base_name'] == video_base
        
    def _cleanup_task_audio_and_extracted_files(self, task_path, scenario="success"):
        files_to_delete = set()
    
        state_managed_subtitle = self.queue_manager.get_extracted_subtitle_file(task_path)
        if state_managed_subtitle:
            files_to_delete.add(state_managed_subtitle)
    
        queue_entry = self.queue_manager.state["queue_state"].get(task_path, {})
        source_file_for_naming = queue_entry.get("video_file") or task_path
        
        base_dir = os.path.dirname(source_file_for_naming)
        file_name_without_ext = os.path.splitext(os.path.basename(source_file_for_naming))[0]
        file_name_without_ext = _strip_language_codes_from_name(file_name_without_ext)
        
        predicted_subtitle_path = os.path.join(base_dir, f"{file_name_without_ext}_extracted.srt")
        files_to_delete.add(predicted_subtitle_path)
    
        for file_path in files_to_delete:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    pass
    
        if scenario == "partial_success":
            if task_path in self.queue_manager.state["queue_state"]:
                self.queue_manager.state["queue_state"][task_path]["extracted_subtitle_file"] = None
                self.queue_manager._save_queue_state()
        else:
            should_cleanup_audio = self._should_cleanup_audio(scenario)
            
            if should_cleanup_audio:
                audio_file, _ = self.queue_manager.sync_audio_extraction_status(task_path)
                
                if audio_file and os.path.exists(audio_file):
                    try:
                        os.remove(audio_file)
                    except Exception as e:
                        pass
                
                self.queue_manager.cleanup_extracted_audio(task_path)
            else:
                if task_path in self.queue_manager.state["queue_state"]:
                    self.queue_manager.state["queue_state"][task_path]["extracted_subtitle_file"] = None
                    self.queue_manager._save_queue_state()
                
    def _cleanup_all_task_files(self):
        for task in self.tasks:
            task_path = task["path"]
            
            try:
                original_basename = os.path.basename(task_path)
                original_dir = os.path.dirname(task_path)
                
                subtitle_parsed = _parse_subtitle_filename(original_basename)
                if subtitle_parsed and subtitle_parsed['base_name']:
                    name_part = subtitle_parsed['base_name']
                else:
                    name_part = _strip_language_codes_from_name(os.path.splitext(original_basename)[0])
                
                progress_file = os.path.join(original_dir, f"{name_part}.progress")
                if os.path.exists(progress_file):
                    os.remove(progress_file)
                
                app_dir_progress = os.path.join(get_app_directory(), f"{name_part}.progress")
                if os.path.exists(app_dir_progress):
                    os.remove(app_dir_progress)
                
                pattern = self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.{modifiers}.srt")
                
                for lang_code in task["languages"]:
                    file_lang_code = lang_code
                    if file_lang_code.startswith('zh'):
                        file_lang_code = 'zh'
                    elif file_lang_code.startswith('pt'):
                        file_lang_code = 'pt'
                    
                    modifiers = _build_modifiers_string(subtitle_parsed)
                    
                    output_filename = pattern.format(
                        original_name=name_part, 
                        lang_code=file_lang_code,
                        modifiers=modifiers
                    )
                    
                    output_filename = _clean_filename_dots(output_filename)
                    output_file = os.path.join(original_dir, output_filename)
                    
                    if not os.path.exists(output_file):
                        continue
                        
                    if os.path.normpath(task_path) == os.path.normpath(output_file):
                        continue
                    
                    input_parsed = _parse_subtitle_filename(os.path.basename(task_path))
                    output_parsed = _parse_subtitle_filename(os.path.basename(output_file))
                    
                    if (input_parsed and output_parsed and 
                        input_parsed['base_name'] == output_parsed['base_name'] and
                        input_parsed['modifiers_string'] == output_parsed['modifiers_string']):
                        
                        input_lang_normalized = _normalize_language_code(input_parsed['lang_code']) if input_parsed['lang_code'] else None
                        output_lang_normalized = _normalize_language_code(output_parsed['lang_code']) if output_parsed['lang_code'] else None
                        
                        if input_lang_normalized == output_lang_normalized == lang_code:
                            continue
                    
                    os.remove(output_file)
                    
                self._cleanup_task_audio_and_extracted_files(task_path, "exit")
                        
            except Exception as e:
                print(f"Error cleaning up files for task {task_path}: {e}")
                continue
        
        app_dir = get_app_directory()
        default_output = os.path.join(app_dir, "translated.srt")
        if os.path.exists(default_output):
            os.remove(default_output)
        
        try:
            files = os.listdir(app_dir)
            for file in files:
                if file.endswith('.progress'):
                    os.remove(os.path.join(app_dir, file))
        except:
            pass
                
    def validate_api_key_cached(self, api_key, key_number=1):
        if key_number == 1:
            if api_key == self.last_validated_key1 and self.api_key1_validated:
                return True
            cache_attr = 'api_key1_validated'
            last_key_attr = 'last_validated_key1'
        else:
            if api_key == self.last_validated_key2 and self.api_key2_validated:
                return True
            cache_attr = 'api_key2_validated'
            last_key_attr = 'last_validated_key2'
        
        if not api_key.strip() and key_number == 2:
            setattr(self, cache_attr, True)
            setattr(self, last_key_attr, api_key)
            return True
        
        if len(api_key.strip()) < 35:
            setattr(self, cache_attr, False)
            return False
        
        try:
            from google import genai
            client = genai.Client(api_key=api_key.strip())
            result = client.models.count_tokens(model="gemini-2.5-flash-lite-preview-06-17", contents="test")
            
            setattr(self, cache_attr, True)
            setattr(self, last_key_attr, api_key)
            return True
        except Exception as e:
            setattr(self, cache_attr, False)
            print(f"API Key {key_number} validation failed: {e}")
            return False
    
    def validate_both_api_keys(self):
        key1 = self.api_key_edit.text().strip()
        key2 = self.api_key2_edit.text().strip()
        
        key1_valid = self.validate_api_key_cached(key1, 1)
        key2_valid = self.validate_api_key_cached(key2, 2) if key2 else True
        
        return {
            'key1_valid': key1_valid,
            'key2_valid': key2_valid,
            'key1_provided': bool(key1),
            'key2_provided': bool(key2),
            'at_least_one_valid': key1_valid or (key2_valid and key2),
            'both_provided_both_valid': key1_valid and key2_valid if key2 else key1_valid
        }
    
    def on_api_key1_changed(self):
        self.api_key1_validated = False
        self.settings.update({"gemini_api_key": self.api_key_edit.text()})
        self.update_button_states()
    
    def on_api_key2_changed(self):
        self.api_key2_validated = False
        self.settings.update({"gemini_api_key2": self.api_key2_edit.text()})
        self.update_button_states()
        
    def refresh_tmdb_info(self):
        selected_rows = self._get_selected_task_rows()
        api_key = self.tmdb_api_key_edit.text().strip()
        
        if not api_key:
            return
        
        for row in selected_rows:
            if 0 <= row < len(self.tasks):
                task_path = self.tasks[row]["path"]
                self._start_tmdb_lookup(task_path, force=True)
    
    def _start_tmdb_lookup(self, file_path, force=False):
        api_key = self.tmdb_api_key_edit.text().strip()
        
        if not api_key or not self.settings.get("use_tmdb", False):
            return
        
        task = None
        for t in self.tasks:
            if t["path"] == file_path:
                task = t
                break
        
        if not task:
            return
        
        if not force and task["description"]:
            return
        
        if file_path in self.tmdb_lookup_workers:
            return
        
        movie_template = self.settings.get("tmdb_movie_template", "Overview: {movie.overview}\n\n{movie.title} - {movie.year}\nGenre(s): {movie.genres}")
        episode_template = self.settings.get("tmdb_episode_template", "Episode Overview: {episode.overview}\n\n{show.title} {episode.number} - {episode.title}\nShow Overview: {show.overview}")
        
        worker = TMDBLookupWorker(file_path, api_key, movie_template, episode_template)
        thread = QThread(self)
        
        worker.moveToThread(thread)
        worker.status_update.connect(self._on_tmdb_status_update)
        worker.finished.connect(self._on_tmdb_finished)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        
        self.tmdb_lookup_workers[file_path] = worker
        self.tmdb_threads[file_path] = thread
        
        thread.start()
        self.update_button_states()
    
    def _on_tmdb_status_update(self, file_path, status):
        for task in self.tasks:
            if task["path"] == file_path:
                task["status_item"].setText(status)
                break
    
    def _on_tmdb_finished(self, file_path, description, success):
        if file_path in self.tmdb_lookup_workers:
            del self.tmdb_lookup_workers[file_path]
        
        if file_path in self.tmdb_threads:
            thread = self.tmdb_threads[file_path]
            if thread.isRunning():
                thread.quit()
                thread.wait()
            del self.tmdb_threads[file_path]
        
        for task in self.tasks:
            if task["path"] == file_path:
                if success and description:
                    task["description"] = description
                    task["desc_item"].setText(description)
                    task["desc_item"].setToolTip(description)
                    task["description_source"] = "Auto"
                    
                    movie_name = self._extract_movie_name_from_description(description)
                    if movie_name:
                        task["movie_item"].setText(movie_name)
                        task["movie_item"].setToolTip(movie_name)
                    
                    if file_path in self.queue_manager.state["queue_state"]:
                        self.queue_manager.state["queue_state"][file_path]["description"] = description
                        self.queue_manager.state["queue_state"][file_path]["tmdb_info"] = description
                        self.queue_manager._save_queue_state()
                
                task["status_item"].setText("Queued")
                break
        
        self.update_button_states()
        
    def on_tmdb_api_key_changed(self):
        self.tmdb_api_key_validated = False
        self.settings.update({"tmdb_api_key": self.tmdb_api_key_edit.text()})
    
    def validate_tmdb_api_key_cached(self, api_key):
        if api_key == self.last_validated_tmdb_key and self.tmdb_api_key_validated:
            return True
        
        if not api_key.strip():
            self.tmdb_api_key_validated = True
            self.last_validated_tmdb_key = api_key
            return True
        
        is_valid = _validate_tmdb_api_key(api_key)
        self.tmdb_api_key_validated = is_valid
        if is_valid:
            self.last_validated_tmdb_key = api_key
        
        return is_valid
        
    def _extract_movie_name_from_description(self, description):
        if not description:
            return ""
        
        lines = description.split('\n')
        if len(lines) < 3:
            return ""
        
        title_line = lines[2].strip()
        
        if ' - ' in title_line:
            parts = title_line.split(' - ')
            if len(parts) >= 2:
                if ' S' in parts[0] and 'E' in parts[0]:
                    return parts[0].rsplit(' S', 1)[0].strip()
                else:
                    return parts[0].strip()
        
        return title_line

if __name__ == "__main__":
    if "--run-gst-subprocess" in sys.argv:
        run_gst_translation_subprocess()
    elif "--run-audio-extraction" in sys.argv:
        run_audio_extraction_subprocess()
    else:
        app = QApplication(sys.argv)

        def sigint_handler(*args):
            return
            
        signal.signal(signal.SIGINT, sigint_handler)
            
        timer = QTimer()
        timer.start(200)
        timer.timeout.connect(lambda: None)

        app.setStyleSheet(load_stylesheet())
        window = MainWindow()
        window.show()
        sys.exit(app.exec())