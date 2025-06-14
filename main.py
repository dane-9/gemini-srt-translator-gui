import sys
import os
import json
import shutil
import subprocess
import re
import argparse
import time

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
    base_path = get_app_directory()
    full_path = os.path.join(base_path, relative_path)
    return full_path

if "--run-gst-subprocess" not in sys.argv:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QTreeView, QLineEdit, QLabel, QFileDialog, QMessageBox,
        QComboBox, QGroupBox, QToolBar, QProgressBar, QDialog, QFormLayout,
        QSpinBox, QDoubleSpinBox, QCheckBox, QDialogButtonBox, QMenu, QTextEdit
    )
    from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QIcon, QKeySequence
    from PySide6.QtCore import Qt, QThread, Slot, QObject, Signal, QProcessEnvironment, QTimer, QItemSelectionModel
else:
    pass

import gemini_srt_translator as gst

CONFIG_FILE = get_resource_path("config.json")

DEFAULT_SETTINGS = {
    "gemini_api_key": "", "gemini_api_key2": "", "target_language": "Swedish",
    "model_name": "gemini-2.5-flash-preview-05-20", "output_file_naming_pattern": "{original_name}.{lang_code}.srt",
    "use_gst_parameters": False, "use_model_tuning": False,
    "output_file": "", "start_line": 1, "description": "", "batch_size": 300,
    "free_quota": True, "skip_upgrade": False, "use_colors": True, "progress_log": False, "thoughts_log": False,
    "temperature": 0.7, "top_p": 0.95, "top_k": 40, "streaming": True, "thinking": True, "thinking_budget": 2048,
}

LANGUAGES = {
    "Swedish": "Swedish", "English": "English", "Spanish": "Spanish", "French": "French",
    "German": "German", "Italian": "Italian", "Portuguese": "Portuguese", "Dutch": "Dutch",
    "Russian": "Russian", "Japanese": "Japanese", "Korean": "Korean", "Chinese (Simplified)": "Chinese (Simplified)",
    "Arabic": "Arabic", "Hindi": "Hindi", "Turkish": "Turkish", "Polish": "Polish",
    "Vietnamese": "Vietnamese", "Thai": "Thai", "Indonesian": "Indonesian", "Danish": "Danish",
}

SHORT_LANG_CODES = {
    "Swedish": "sv", "English": "en", "Spanish": "es", "French": "fr", "German": "de",
    "Italian": "it", "Portuguese": "pt", "Dutch": "nl", "Russian": "ru", "Japanese": "ja",
    "Korean": "ko", "Chinese (Simplified)": "zh-CN", "Arabic": "ar", "Hindi": "hi",
    "Turkish": "tr", "Polish": "pl", "Vietnamese": "vi", "Thai": "th", "Indonesian": "id",
    "Danish": "da",
}

PROGRESS_RE = re.compile(r"Translating:\s*\|.*\|\s*(\d+)%\s*\(([^)]+)\)(.*)")
THINKING_RE = re.compile(r"Thinking", re.IGNORECASE)
PROCESSING_RE = re.compile(r"Processing", re.IGNORECASE)
VALIDATING_RE = re.compile(r"Validating token size", re.IGNORECASE)
COMPLETION_STR = "Translation completed successfully!"
DEFAULT_GST_OUTPUT_NAME = "translated.srt"

def run_gst_translation_subprocess():
    parser = argparse.ArgumentParser(description="Run Gemini SRT Translator for a single file (subprocess mode).")
    parser.add_argument("--run-gst-subprocess", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--api_key", required=True, help="Gemini API Key")
    parser.add_argument("--target_language", required=True, help="Target language")
    parser.add_argument("--input_file", required=True, help="Input SRT file path")
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
    
    try:
        gst.gemini_api_key = args.api_key
        gst.target_language = args.target_language
        gst.input_file = args.input_file
        gst.output_file = DEFAULT_GST_OUTPUT_NAME
        if args.model_name: gst.model_name = args.model_name
        if args.gemini_api_key2: gst.gemini_api_key2 = args.gemini_api_key2
        if args.output_file: gst.output_file = args.output_file
        if args.start_line is not None: gst.start_line = args.start_line
        if args.description: gst.description = args.description
        if args.batch_size is not None: gst.batch_size = args.batch_size
        if args.free_quota is not None: gst.free_quota = args.free_quota
        if args.skip_upgrade is not None: gst.skip_upgrade = args.skip_upgrade
        if args.use_colors is not None: gst.use_colors = args.use_colors
        if args.progress_log is not None: gst.progress_log = args.progress_log
        if args.thoughts_log is not None: gst.thoughts_log = args.thoughts_log
        if args.temperature is not None: gst.temperature = args.temperature
        if args.top_p is not None: gst.top_p = args.top_p
        if args.top_k is not None: gst.top_k = args.top_k
        if args.streaming is not None: gst.streaming = args.streaming
        if args.thinking is not None: gst.thinking = args.thinking
        if args.thinking_budget is not None: gst.thinking_budget = args.thinking_budget
        gst.translate()
        sys.exit(0)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

if "--run-gst-subprocess" not in sys.argv:
    class BulkDescriptionDialog(QDialog):
        def __init__(self, current_text="", parent=None):
            super().__init__(parent)
            self.setWindowTitle("Bulk Edit Description")
            self.setMinimumSize(400, 200)
            layout = QVBoxLayout(self)
            
            layout.addWidget(QLabel("Description:"))
            self.text_edit = QTextEdit()
            self.text_edit.setPlainText(current_text)
            layout.addWidget(self.text_edit)
            
            self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)
            layout.addWidget(self.button_box)
        
        def get_description(self):
            return self.text_edit.toPlainText().strip()

    class SettingsDialog(QDialog):
        def __init__(self, current_settings, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Advanced Settings")
            self.setMinimumWidth(500)
            self.settings = current_settings.copy()
            layout = QVBoxLayout(self)
            
            basic_group = QGroupBox("Basic Configuration")
            basic_layout = QFormLayout()
            self.output_naming_pattern_edit = QLineEdit(self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.srt"))
            basic_layout.addRow("Output Naming Pattern:", self.output_naming_pattern_edit)
            basic_group.setLayout(basic_layout)
            layout.addWidget(basic_group)
            
            self.gst_group = QGroupBox("GST Parameters")
            self.gst_group.setCheckable(True)
            self.gst_group.setChecked(self.settings.get("use_gst_parameters", False))
            self.gst_group.toggled.connect(self.toggle_gst_settings)
            gst_layout = QFormLayout()
            self.output_file_edit = QLineEdit(self.settings.get("output_file", ""))
            gst_layout.addRow("Output File:", self.output_file_edit)
            self.start_line_spin = QSpinBox()
            self.start_line_spin.setRange(1, 999999)
            self.start_line_spin.setValue(self.settings.get("start_line", 1))
            gst_layout.addRow("Start Line:", self.start_line_spin)
            self.batch_size_spin = QSpinBox()
            self.batch_size_spin.setRange(1, 10000)
            self.batch_size_spin.setValue(self.settings.get("batch_size", 300))
            gst_layout.addRow("Batch Size:", self.batch_size_spin)
            self.free_quota_checkbox = QCheckBox()
            self.free_quota_checkbox.setChecked(self.settings.get("free_quota", True))
            gst_layout.addRow("Free Quota:", self.free_quota_checkbox)
            self.skip_upgrade_checkbox = QCheckBox()
            self.skip_upgrade_checkbox.setChecked(self.settings.get("skip_upgrade", False))
            gst_layout.addRow("Skip Upgrade:", self.skip_upgrade_checkbox)
            self.use_colors_checkbox = QCheckBox()
            self.use_colors_checkbox.setChecked(self.settings.get("use_colors", True))
            gst_layout.addRow("Use Colors:", self.use_colors_checkbox)
            self.progress_log_checkbox = QCheckBox()
            self.progress_log_checkbox.setChecked(self.settings.get("progress_log", False))
            gst_layout.addRow("Progress Log:", self.progress_log_checkbox)
            self.thoughts_log_checkbox = QCheckBox()
            self.thoughts_log_checkbox.setChecked(self.settings.get("thoughts_log", False))
            gst_layout.addRow("Thoughts Log:", self.thoughts_log_checkbox)
            self.gst_group.setLayout(gst_layout)
            layout.addWidget(self.gst_group)
            
            self.model_group = QGroupBox("Model Tuning Parameters")
            self.model_group.setCheckable(True)
            self.model_group.setChecked(self.settings.get("use_model_tuning", False))
            self.model_group.toggled.connect(self.toggle_model_settings)
            model_layout = QFormLayout()
            self.temperature_spin = QDoubleSpinBox()
            self.temperature_spin.setRange(0.0, 2.0)
            self.temperature_spin.setSingleStep(0.1)
            self.temperature_spin.setValue(self.settings.get("temperature", 0.7))
            model_layout.addRow("Temperature:", self.temperature_spin)
            self.top_p_spin = QDoubleSpinBox()
            self.top_p_spin.setRange(0.0, 1.0)
            self.top_p_spin.setSingleStep(0.1)
            self.top_p_spin.setValue(self.settings.get("top_p", 0.95))
            model_layout.addRow("Top P:", self.top_p_spin)
            self.top_k_spin = QSpinBox()
            self.top_k_spin.setRange(0, 1000)
            self.top_k_spin.setValue(self.settings.get("top_k", 40))
            model_layout.addRow("Top K:", self.top_k_spin)
            self.streaming_checkbox = QCheckBox()
            self.streaming_checkbox.setChecked(self.settings.get("streaming", True))
            model_layout.addRow("Streaming:", self.streaming_checkbox)
            self.thinking_checkbox = QCheckBox()
            self.thinking_checkbox.setChecked(self.settings.get("thinking", True))
            model_layout.addRow("Thinking:", self.thinking_checkbox)
            self.thinking_budget_spin = QSpinBox()
            self.thinking_budget_spin.setRange(0, 24576)
            self.thinking_budget_spin.setValue(self.settings.get("thinking_budget", 2048))
            model_layout.addRow("Thinking Budget:", self.thinking_budget_spin)
            self.model_group.setLayout(model_layout)
            layout.addWidget(self.model_group)
            
            self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            self.button_box.accepted.connect(self.accept)
            self.button_box.rejected.connect(self.reject)
            layout.addWidget(self.button_box)
            
            self.toggle_gst_settings(self.gst_group.isChecked())
            self.toggle_model_settings(self.model_group.isChecked())
        
        def toggle_gst_settings(self, enabled):
            pass
        
        def toggle_model_settings(self, enabled):
            pass
        
        def get_settings(self):
            s = self.settings
            s["use_gst_parameters"] = self.gst_group.isChecked()
            s["use_model_tuning"] = self.model_group.isChecked()
            s["output_file_naming_pattern"] = self.output_naming_pattern_edit.text().strip()
            s["output_file"] = self.output_file_edit.text().strip()
            s["start_line"] = self.start_line_spin.value()
            s["batch_size"] = self.batch_size_spin.value()
            s["free_quota"] = self.free_quota_checkbox.isChecked()
            s["skip_upgrade"] = self.skip_upgrade_checkbox.isChecked()
            s["use_colors"] = self.use_colors_checkbox.isChecked()
            s["progress_log"] = self.progress_log_checkbox.isChecked()
            s["thoughts_log"] = self.thoughts_log_checkbox.isChecked()
            s["temperature"] = self.temperature_spin.value()
            s["top_p"] = self.top_p_spin.value()
            s["top_k"] = self.top_k_spin.value()
            s["streaming"] = self.streaming_checkbox.isChecked()
            s["thinking"] = self.thinking_checkbox.isChecked()
            s["thinking_budget"] = self.thinking_budget_spin.value()
            return s

    class SubprocessWorker(QObject):
        finished = Signal(int, str, bool)
        progress_update = Signal(int, int, str)
        status_message = Signal(int, str)
        
        def __init__(self, task_index, input_file_path, target_lang_gst_value, api_key, api_key2, model_name, advanced_settings_for_gst_runner, description=""):
            super().__init__()
            self.task_index = task_index
            self.input_file_path = input_file_path
            self.target_lang_gst_value = target_lang_gst_value
            self.api_key = api_key
            self.api_key2 = api_key2
            self.model_name = model_name
            self.advanced_settings = advanced_settings_for_gst_runner
            self.description = description
            self.process = None
            self.is_cancelled = False
            
        def _generate_final_filename(self):
            original_basename = os.path.basename(self.input_file_path)
            name_part, ext = os.path.splitext(original_basename)
            target_lang_code = SHORT_LANG_CODES.get(self.target_lang_gst_value, self.target_lang_gst_value.lower())
            pattern = self.advanced_settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.srt")
            
            for code in SHORT_LANG_CODES.values():
                if name_part.endswith(f".{code}"):
                    name_part = name_part[:-len(f".{code}")]
                    break
            
            final_name = pattern.format(original_name=name_part, lang_code=target_lang_code)
            return final_name
        
        def _fix_newline_issues(self, file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if '\\n' in content:
                    fixed_content = content.replace('\\n', '\n')
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(fixed_content)
                    return True
                else:
                    return False
            except Exception as e:
                return False
        
        def _cleanup_progress_files(self):
            subprocess_cwd = get_app_directory()
            original_input_dir = os.path.dirname(self.input_file_path)
            progress_file_pattern = f"{os.path.basename(self.input_file_path)}.progress"
            
            for cleanup_dir in [subprocess_cwd, original_input_dir]:
                progress_file_path = os.path.join(cleanup_dir, progress_file_pattern)
                if os.path.exists(progress_file_path):
                    try:
                        os.remove(progress_file_path)
                    except Exception as e:
                        pass
        
        def _cleanup_translated_srt(self):
            subprocess_cwd = get_app_directory()
            default_output_file_path = os.path.join(subprocess_cwd, DEFAULT_GST_OUTPUT_NAME)
            
            if os.path.exists(default_output_file_path):
                try:
                    os.remove(default_output_file_path)
                except Exception as e:
                    pass
        
        @Slot()
        def run(self):
            if self.is_cancelled:
                self.finished.emit(self.task_index, "Cancelled before start", False)
                return
            
            self.status_message.emit(self.task_index, "Preparing subprocess...")
            subprocess_cwd = get_app_directory()
            default_output_file_path = os.path.join(subprocess_cwd, DEFAULT_GST_OUTPUT_NAME)
            
            if os.path.exists(default_output_file_path):
                try:
                    os.remove(default_output_file_path)
                    self.status_message.emit(self.task_index, f"Cleaned old {DEFAULT_GST_OUTPUT_NAME}")
                except OSError as e:
                    self.finished.emit(self.task_index, f"Error cleaning old output: {e}", False)
                    return
            
            executable_path = get_executable_path()
            
            if not os.path.exists(executable_path):
                self.finished.emit(self.task_index, f"Executable not found: {executable_path}", False)
                return
            
            if is_compiled():
                cmd = [executable_path, "--run-gst-subprocess"]
            else:
                cmd = [sys.executable, executable_path, "--run-gst-subprocess"]
            
            cmd.extend([
                "--api_key", self.api_key,
                "--target_language", self.target_lang_gst_value,
                "--input_file", self.input_file_path,
            ])
            
            if self.model_name:
                cmd.extend(["--model_name", self.model_name])
            
            if self.api_key2:
                cmd.extend(["--gemini_api_key2", self.api_key2])
            
            if self.description:
                cmd.extend(["--description", self.description])
            
            if self.advanced_settings.get("use_gst_parameters", False):
                if self.advanced_settings.get("output_file"):
                    cmd.extend(["--output_file", self.advanced_settings["output_file"]])
                if self.advanced_settings.get("start_line") is not None:
                    cmd.extend(["--start_line", str(self.advanced_settings["start_line"])])
                if self.advanced_settings.get("batch_size") is not None:
                    cmd.extend(["--batch_size", str(self.advanced_settings["batch_size"])])
                if self.advanced_settings.get("free_quota") is not None:
                    cmd.extend(["--free_quota", str(self.advanced_settings["free_quota"])])
                if self.advanced_settings.get("skip_upgrade") is not None:
                    cmd.extend(["--skip_upgrade", str(self.advanced_settings["skip_upgrade"])])
                if self.advanced_settings.get("use_colors") is not None:
                    cmd.extend(["--use_colors", str(self.advanced_settings["use_colors"])])
                if self.advanced_settings.get("progress_log") is True:
                    cmd.extend(["--progress_log", str(self.advanced_settings["progress_log"])])
                if self.advanced_settings.get("thoughts_log") is True:
                    cmd.extend(["--thoughts_log", str(self.advanced_settings["thoughts_log"])])
                    
            if self.advanced_settings.get("use_model_tuning", False):
                if self.advanced_settings.get("temperature") is not None:
                    cmd.extend(["--temperature", str(self.advanced_settings["temperature"])])
                if self.advanced_settings.get("top_p") is not None:
                    cmd.extend(["--top_p", str(self.advanced_settings["top_p"])])
                if self.advanced_settings.get("top_k") is not None:
                    cmd.extend(["--top_k", str(self.advanced_settings["top_k"])])
                if self.advanced_settings.get("streaming") is not None:
                    cmd.extend(["--streaming", str(self.advanced_settings["streaming"])])
                if self.advanced_settings.get("thinking") is not None:
                    cmd.extend(["--thinking", str(self.advanced_settings["thinking"])])
                if self.advanced_settings.get("thinking_budget") is not None:
                    cmd.extend(["--thinking_budget", str(self.advanced_settings["thinking_budget"])])
            
            self.status_message.emit(self.task_index, "Starting translation subprocess...")
            
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUNBUFFERED"] = "1"
                
                creationflags = 0
                if os.name == 'nt': 
                    creationflags = subprocess.CREATE_NO_WINDOW
                
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                
                self.process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, cwd=subprocess_cwd, env=env, bufsize=1,
                    creationflags=creationflags, startupinfo=startupinfo,
                    encoding='utf-8', errors='replace'
                )
                
                found_completion_string = False
                stderr_output = []
                stdout_lines = []
                last_known_percent = 0
                current_status_text = "Starting..."
                last_progress_update_time = 0
                
                def strip_ansi_sequences(text):
                    ansi_escape = re.compile(r'\x1b\[[0-9;]*[mK]|\x1b\[F')
                    return ansi_escape.sub('', text)
                
                if self.process.stdout:
                    try:
                        for line in self.process.stdout:
                            if self.is_cancelled:
                                break
                            
                            clean_line = strip_ansi_sequences(line).strip()
                            if not clean_line or clean_line.isspace():
                                continue
                                
                            stdout_lines.append(clean_line)
        
                            if COMPLETION_STR in clean_line:
                                found_completion_string = True
                                self.progress_update.emit(self.task_index, 100, "Translation completed successfully!")
                                continue
        
                            progress_match = PROGRESS_RE.search(clean_line)
                            if progress_match:
                                percent = int(progress_match.group(1))
                                last_known_percent = percent
                                details = progress_match.group(2)
                                status_suffix = progress_match.group(3).strip()
                                
                                if "Thinking" in status_suffix:
                                    status = "Thinking"
                                elif "Processing" in status_suffix:
                                    status = "Processing"
                                else:
                                    status = "Waiting..."
                                
                                current_status_text = f"{status} ({details})"
                                self.progress_update.emit(self.task_index, percent, current_status_text)
                                last_progress_update_time = time.time()
                                continue
                            
                            if "Starting translation of" in clean_line:
                                lines_match = re.search(r"Starting translation of (\d+) lines", clean_line)
                                if lines_match:
                                    total_lines = lines_match.group(1)
                                    current_status_text = f"Starting translation of {total_lines} lines..."
                                    self.progress_update.emit(self.task_index, 0, current_status_text)
                                continue
                            
                            current_time = time.time()
                            if current_time - last_progress_update_time > 2.0:
                                if VALIDATING_RE.search(clean_line):
                                    current_status_text = "Validating token size..."
                                    self.progress_update.emit(self.task_index, last_known_percent, current_status_text)
                                    continue
                                
                                if "Token size validated" in clean_line:
                                    current_status_text = "Token size validated. Starting translation..."
                                    self.progress_update.emit(self.task_index, last_known_percent, current_status_text)
                                    continue
                                
                    except ValueError as e:
                        pass
                
                if self.process.stderr:
                    try:
                        stderr_data = self.process.stderr.read()
                        if stderr_data:
                            stderr_output.extend(stderr_data.strip().split('\n'))
                    except ValueError as e:
                        pass
                
                try:
                    return_code = self.process.wait(timeout=600)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    stderr_output.append("GST subprocess timed out and was killed.")
                    try:
                        return_code = self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        stderr_output.append("GST subprocess unresponsive after kill.")
                        return_code = -1
        
                if self.is_cancelled:
                    if self.process and self.process.poll() is None:
                        self.process.terminate()
                        try: 
                            self.process.wait(timeout=5)
                        except subprocess.TimeoutExpired: 
                            self.process.kill()
                    self._cleanup_progress_files()
                    self._cleanup_translated_srt()
                    self.finished.emit(self.task_index, "Translation cancelled.", False)
                    return
        
                if return_code == 0 and found_completion_string:
                    self.status_message.emit(self.task_index, "Finalizing...")
                    
                    if os.path.exists(default_output_file_path):
                        self.status_message.emit(self.task_index, "Checking for formatting issues...")
                        newline_fixed = self._fix_newline_issues(default_output_file_path)
                        if newline_fixed:
                            self.status_message.emit(self.task_index, "Fixed newline formatting...")
                        
                        original_input_dir = os.path.dirname(self.input_file_path)
                        final_name = self._generate_final_filename()
                        final_path = os.path.join(original_input_dir, final_name)
                        
                        try:
                            if os.path.exists(final_path): 
                                os.remove(final_path)
                            
                            shutil.move(default_output_file_path, final_path)
                            self.finished.emit(self.task_index, f"Translated", True)
                        except Exception as e_move:
                            self._cleanup_progress_files()
                            self.finished.emit(self.task_index, f"Error moving file: {e_move}", False)
                    else:
                        self._cleanup_progress_files()
                        self.finished.emit(self.task_index, f"Error: {DEFAULT_GST_OUTPUT_NAME} not found post-translation.", False)
                else:
                    self._cleanup_progress_files()
                    self._cleanup_translated_srt()
                    err_msg = f"GST process failed (code {return_code})."
                    if not found_completion_string and return_code == 0: 
                        err_msg = "GST process ended (ok) but completion string not found."
                    clean_stderr = [s.strip() for s in stderr_output if s.strip() and "GST_SUBPROCESS_ERROR" not in s]
                    if clean_stderr: 
                        err_msg += " Stderr: " + " | ".join(clean_stderr)[:250]
                    else: 
                        err_msg += " (No specific stderr from GST)"
                    self.finished.emit(self.task_index, err_msg, False)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._cleanup_progress_files()
                self._cleanup_translated_srt()
                self.finished.emit(self.task_index, f"Subprocess worker error: {type(e).__name__} - {e}", False)
            finally:
                if self.process and self.process.poll() is None:
                    self.process.kill()
                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass
                self.process = None

        def cancel(self):
            self.is_cancelled = True
            self.status_message.emit(self.task_index, "Cancelling subprocess...")
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    QTimer.singleShot(2000, self._ensure_killed)
                except Exception as e:
                    pass
        
        def _ensure_killed(self):
            if self.process and self.process.poll() is None:
                try:
                    self.process.kill()
                except Exception as e:
                    pass

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            
            self.setWindowTitle("Gemini SRT Translator")
            
            window_width = 1000
            window_height = 700
            self.resize(window_width, window_height)
            
            screen = QApplication.primaryScreen().geometry()
            screen_width = screen.width()
            screen_height = screen.height()
            
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            self.move(x, y)
            
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
            self.setWindowIcon(QIcon(icon_path))
            self.tasks = []
            self.current_task_index = -1
            self.settings = self._load_settings()
            self.active_thread = None
            self.active_worker = None
            self.clipboard_description = ""
            
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            
            toolbar = QToolBar("Main Toolbar")
            self.addToolBar(toolbar)
            add_action = QAction(QIcon.fromTheme("document-open"), "Add Subtitles", self)
            add_action.triggered.connect(self.add_files_action)
            toolbar.addAction(add_action)
            self.start_action = QAction(QIcon.fromTheme("media-playback-start"), "Start Queue", self)
            self.start_action.triggered.connect(self.start_translation_queue)
            toolbar.addAction(self.start_action)
            self.stop_action = QAction(QIcon.fromTheme("media-playback-stop"), "Stop Current/Queue", self)
            self.stop_action.triggered.connect(self.stop_translation_action)
            self.stop_action.setEnabled(False)
            toolbar.addAction(self.stop_action)
            settings_action = QAction(QIcon.fromTheme("preferences-system"), "Settings", self)
            settings_action.triggered.connect(self.open_settings_dialog)
            toolbar.addAction(settings_action)
            toolbar.addSeparator()
            self.clear_action = QAction(QIcon.fromTheme("edit-clear"), "Clear Queue", self)
            self.clear_action.triggered.connect(self.clear_queue_action)
            self.clear_action.setEnabled(False)
            toolbar.addAction(self.clear_action)
            
            config_group = QGroupBox("Basic Configuration")
            config_layout = QFormLayout(config_group)
            
            api_keys_layout = QHBoxLayout()
            self.api_key_edit = QLineEdit()
            self.api_key_edit.setPlaceholderText("Enter your Gemini API Key")
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            self.api_key_edit.setText(self.settings.get("gemini_api_key", ""))
            self.api_key_edit.textChanged.connect(lambda text: self.settings.update({"gemini_api_key": text}))
            api_keys_layout.addWidget(self.api_key_edit)
            
            self.api_key2_edit = QLineEdit()
            self.api_key2_edit.setPlaceholderText("Second API Key (optional)")
            self.api_key2_edit.setEchoMode(QLineEdit.Password)
            self.api_key2_edit.setText(self.settings.get("gemini_api_key2", ""))
            self.api_key2_edit.textChanged.connect(lambda text: self.settings.update({"gemini_api_key2": text}))
            api_keys_layout.addWidget(self.api_key2_edit)
            
            config_layout.addRow("API Keys:", api_keys_layout)
            
            self.target_lang_combo = QComboBox()
            self.target_lang_combo.addItems(LANGUAGES.keys())
            current_gst_lang_val = self.settings.get("target_language", "Swedish")
            display_key_for_value = current_gst_lang_val
            for k, v in LANGUAGES.items():
                if v == current_gst_lang_val:
                    display_key_for_value = k
                    break
            self.target_lang_combo.setCurrentText(display_key_for_value)
            self.target_lang_combo.currentTextChanged.connect(
                lambda text: self.settings.update({"target_language": LANGUAGES.get(text, text)})
            )
            config_layout.addRow("Target Language:", self.target_lang_combo)
            
            self.model_name_edit = QLineEdit()
            self.model_name_edit.setText(self.settings.get("model_name", "gemini-2.5-flash-preview-05-20"))
            self.model_name_edit.textChanged.connect(lambda text: self.settings.update({"model_name": text}))
            config_layout.addRow("Model Name:", self.model_name_edit)
            
            main_layout.addWidget(config_group)
            
            self.tree_view = QTreeView()
            self.tree_view.setAlternatingRowColors(True)
            self.tree_view.setRootIsDecorated(False)
            self.tree_view.setUniformRowHeights(True)
            self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
            self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)
            self.model = QStandardItemModel()
            self.model.setHorizontalHeaderLabels(["File Name", "Target Language", "Description", "Status"])
            self.model.itemChanged.connect(self.on_item_changed)
            self.tree_view.setModel(self.model)
            self.tree_view.setColumnWidth(0, 480)
            self.tree_view.setColumnWidth(1, 120)
            self.tree_view.setColumnWidth(2, 200)
            self.tree_view.setColumnWidth(3, 150)
            self.tree_view.setMinimumHeight(250)
            
            self.tree_view.setSortingEnabled(True)
            self.tree_view.sortByColumn(0, Qt.AscendingOrder)
            
            header = self.tree_view.header()
            header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
            
            main_layout.addWidget(self.tree_view)
            
            self.overall_progress_bar = QProgressBar()
            self.overall_progress_bar.setTextVisible(True)
            self.overall_progress_bar.setFormat("%p% - Current Task")
            self.overall_progress_bar.setVisible(False)
            main_layout.addWidget(self.overall_progress_bar)
            
            self.update_button_states()

        def on_item_changed(self, item):
            if item.column() == 2:
                row = item.row()
                if 0 <= row < len(self.tasks):
                    self.tasks[row]["description"] = item.text()
                    item.setToolTip(item.text())

        def keyPressEvent(self, event):
            if event.matches(QKeySequence.Copy):
                current_index = self.tree_view.currentIndex()
                if current_index.isValid() and current_index.column() == 2:
                    item = self.model.itemFromIndex(current_index)
                    if item:
                        self.clipboard_description = item.text()
            elif event.matches(QKeySequence.Paste):
                current_index = self.tree_view.currentIndex()
                if current_index.isValid() and current_index.column() == 2:
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
                QMessageBox.warning(self, "Cannot Sort", 
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
                desc_item = self.model.item(row, 2)
                status_item = self.model.item(row, 3)
                
                for task in self.tasks:
                    if (task["path_item"] is path_item and 
                        task["lang_item"] is lang_item and 
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
            self.model.setHorizontalHeaderLabels(["File Name", "Target Language", "Description", "Status"])
            
            for task in self.tasks:
                self.model.appendRow([task["path_item"], task["lang_item"], task["desc_item"], task["status_item"]])
            
            for i, width in enumerate(col_widths):
                if i < self.model.columnCount():
                    self.tree_view.setColumnWidth(i, width)
            
            if was_sorting_enabled:
                self.tree_view.setSortingEnabled(True)
                if sort_column >= 0:
                    self.tree_view.sortByColumn(sort_column, sort_order)

        def show_context_menu(self, position):
            if self.active_thread and self.active_thread.isRunning():
                return
                
            item = self.tree_view.indexAt(position)
            if not item.isValid():
                return
            
            selected_indexes = self.tree_view.selectionModel().selectedRows()
            if not selected_indexes:
                return
            
            menu = QMenu(self)
            
            if len(selected_indexes) == 1:
                edit_desc_action = QAction("Edit Description", self)
                edit_desc_action.triggered.connect(self.edit_single_description)
                menu.addAction(edit_desc_action)
                
                row = selected_indexes[0].row()
                if 0 <= row < len(self.tasks):
                    current_desc = self.tasks[row]["description"]
                    if current_desc:
                        copy_desc_action = QAction("Copy Description", self)
                        copy_desc_action.triggered.connect(self.copy_description)
                        menu.addAction(copy_desc_action)
            
            if len(selected_indexes) > 1:
                bulk_edit_action = QAction("Bulk Edit Description", self)
                bulk_edit_action.triggered.connect(self.bulk_edit_description)
                menu.addAction(bulk_edit_action)
            
            if self.clipboard_description:
                should_show_apply = True
                if len(selected_indexes) == 1:
                    row = selected_indexes[0].row()
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
            for index in selected_indexes:
                row = index.row()
                if 0 <= row < len(self.tasks):
                    if self.tasks[row]["status_item"].text() != "Queued":
                        has_non_queued = True
                        break
            
            if has_non_queued:
                reset_action = QAction("Reset Status", self)
                reset_action.triggered.connect(self.reset_selected_status)
                menu.addAction(reset_action)
            
            menu.exec(self.tree_view.mapToGlobal(position))

        def copy_description_to_selected(self, description):
            selected_indexes = self.tree_view.selectionModel().selectedRows()
            for index in selected_indexes:
                row = index.row()
                if 0 <= row < len(self.tasks):
                    self.tasks[row]["desc_item"].setText(description)
                    self.tasks[row]["desc_item"].setToolTip(description)
                    self.tasks[row]["description"] = description

        def copy_description(self):
            selected_indexes = self.tree_view.selectionModel().selectedRows()
            if len(selected_indexes) == 1:
                row = selected_indexes[0].row()
                if 0 <= row < len(self.tasks):
                    self.clipboard_description = self.tasks[row]["description"]

        def apply_copied_description(self):
            if not self.clipboard_description:
                return
            
            selected_indexes = self.tree_view.selectionModel().selectedRows()
            for index in selected_indexes:
                row = index.row()
                if 0 <= row < len(self.tasks):
                    self.tasks[row]["desc_item"].setText(self.clipboard_description)
                    self.tasks[row]["desc_item"].setToolTip(self.clipboard_description)
                    self.tasks[row]["description"] = self.clipboard_description

        def edit_single_description(self):
            selected_indexes = self.tree_view.selectionModel().selectedRows()
            if len(selected_indexes) != 1:
                return
            
            row = selected_indexes[0].row()
            if 0 <= row < len(self.tasks):
                current_desc = self.tasks[row]["description"]
                dialog = BulkDescriptionDialog(current_desc, self)
                dialog.setWindowTitle("Edit Description")
                if dialog.exec():
                    new_description = dialog.get_description()
                    self.tasks[row]["desc_item"].setText(new_description)
                    self.tasks[row]["desc_item"].setToolTip(new_description)
                    self.tasks[row]["description"] = new_description

        def bulk_edit_description(self):
            selected_indexes = self.tree_view.selectionModel().selectedRows()
            if not selected_indexes:
                return
            
            current_desc = ""
            if len(selected_indexes) == 1:
                row = selected_indexes[0].row()
                if 0 <= row < len(self.tasks):
                    current_desc = self.tasks[row]["description"]
            else:
                descriptions = []
                for index in selected_indexes:
                    row = index.row()
                    if 0 <= row < len(self.tasks):
                        desc = self.tasks[row]["description"]
                        if desc:
                            descriptions.append(desc)
                
                if len(descriptions) == 1:
                    current_desc = descriptions[0]
            
            dialog = BulkDescriptionDialog(current_desc, self)
            if dialog.exec():
                new_description = dialog.get_description()
                for index in selected_indexes:
                    row = index.row()
                    if 0 <= row < len(self.tasks):
                        self.tasks[row]["desc_item"].setText(new_description)
                        self.tasks[row]["desc_item"].setToolTip(new_description)
                        self.tasks[row]["description"] = new_description

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
                    self.tasks.pop(row)
                    self.model.removeRow(row)
            
            self.update_button_states()

        def reset_selected_status(self):
            if self.active_thread and self.active_thread.isRunning():
                return
                
            selected_indexes = self.tree_view.selectionModel().selectedRows()
            if not selected_indexes:
                return
            
            reset_count = 0
            for index in selected_indexes:
                row = index.row()
                if 0 <= row < len(self.tasks):
                    current_status = self.tasks[row]["status_item"].text()
                    if current_status != "Queued":
                        self.tasks[row]["status_item"].setText("Queued")
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
                else:
                    pass
            except Exception as e:
                pass
            
            return DEFAULT_SETTINGS.copy()

        def _save_settings(self):
            try:
                self.settings["gemini_api_key"] = self.api_key_edit.text()
                self.settings["gemini_api_key2"] = self.api_key2_edit.text()
                self.settings["model_name"] = self.model_name_edit.text()
                current_display_lang = self.target_lang_combo.currentText()
                self.settings["target_language"] = LANGUAGES.get(current_display_lang, current_display_lang)
                
                config_dir = os.path.dirname(CONFIG_FILE)
                if not os.path.exists(config_dir):
                    os.makedirs(config_dir, exist_ok=True)
                
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(self.settings, f, indent=4)
            except Exception as e:
                QMessageBox.warning(self, "Save Settings Error", f"Could not save settings: {e}")

        def _cleanup_all_progress_files(self):
            script_dir = get_app_directory()
            
            try:
                files = os.listdir(script_dir)
                for file in files:
                    if file.endswith('.progress'):
                        file_path = os.path.join(script_dir, file)
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            pass
            except Exception as e:
                pass

        def _cleanup_translated_srt_file(self):
            script_dir = get_app_directory()
            default_output_file_path = os.path.join(script_dir, DEFAULT_GST_OUTPUT_NAME)
            
            if os.path.exists(default_output_file_path):
                try:
                    os.remove(default_output_file_path)
                except Exception as e:
                    pass
            else:
                pass

        def closeEvent(self, event):
            self._save_settings()
            if self.active_thread and self.active_thread.isRunning():
                reply = QMessageBox.question(self, 'Confirm Exit', "Translation in progress. Stop and exit?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.stop_translation_action(force_quit=True)
                    if self.active_thread and not self.active_thread.wait(3000):
                        QMessageBox.warning(self, "Exiting", "Thread did not stop gracefully. Forcing exit.")
                        if self.active_worker and self.active_worker.process:
                             try:
                                 self.active_worker.process.kill()
                             except:
                                 pass
                        self.active_thread.terminate()
                        self.active_thread.wait()
                    self._cleanup_all_progress_files()
                    self._cleanup_translated_srt_file()
                    event.accept()
                else:
                    event.ignore()
            else:
                event.accept()

        def add_files_action(self):
            files, _ = QFileDialog.getOpenFileNames(self, "Select Subtitle Files", "", "SRT Files (*.srt);;All Files (*)")
            if files:
                selected_target_lang_display = self.target_lang_combo.currentText()
                selected_target_lang_value = LANGUAGES.get(selected_target_lang_display, selected_target_lang_display)
                
                for file_path in files:
                    if any(task['path'] == file_path and task['lang_value'] == selected_target_lang_value for task in self.tasks):
                        continue
                        
                    path_item = QStandardItem(os.path.basename(file_path))
                    path_item.setToolTip(os.path.dirname(file_path))
                    path_item.setEditable(False)
                    lang_item = QStandardItem(selected_target_lang_display)
                    lang_item.setEditable(False)
                    desc_item = QStandardItem("")
                    desc_item.setEditable(True)
                    desc_item.setToolTip("")
                    status_item = QStandardItem("Queued")
                    status_item.setEditable(False)
                    self.model.appendRow([path_item, lang_item, desc_item, status_item])
                    self.tasks.append({
                        "path": file_path, "path_item": path_item, "lang_item": lang_item,
                        "desc_item": desc_item, "status_item": status_item, "description": "",
                        "lang_display": selected_target_lang_display,
                        "lang_value": selected_target_lang_value, "worker": None, "thread": None
                    })
                    
                self.update_button_states()
            else:
                pass

        def start_translation_queue(self):
            if not self.api_key_edit.text().strip():
                QMessageBox.warning(self, "API Key Missing", "Please enter your Gemini API Key.")
                self.api_key_edit.setFocus()
                return
                
            if self.active_thread and self.active_thread.isRunning():
                QMessageBox.information(self, "In Progress", "A translation is already in progress.")
                return
                
            first_queued_idx = -1
            for i, task_data in enumerate(self.tasks):
                if task_data["status_item"].text() == "Queued":
                    first_queued_idx = i
                    break
                    
            if first_queued_idx == -1:
                QMessageBox.information(self, "Queue Status", "No subtitles in 'Queued' state.")
                return
                
            self.current_task_index = first_queued_idx
            self._process_task_at_index(self.current_task_index)
            self.update_button_states()

        def _process_task_at_index(self, task_idx):
            if not (0 <= task_idx < len(self.tasks)):
                self._handle_queue_finished()
                return
                
            task = self.tasks[task_idx]
            if task["status_item"].text() != "Queued":
                self._find_and_process_next_queued_task()
                return
                
            self.current_task_index = task_idx
            task["status_item"].setText("Preparing...")
            self.overall_progress_bar.setVisible(True)
            self.overall_progress_bar.setValue(0)
            self.overall_progress_bar.setFormat("%p% - Current Task")
            self.stop_action.setEnabled(True)
            
            self.active_worker = SubprocessWorker(
                task_index=task_idx, input_file_path=task["path"], target_lang_gst_value=task["lang_value"],
                api_key=self.api_key_edit.text().strip(), api_key2=self.api_key2_edit.text().strip(),
                model_name=self.model_name_edit.text().strip(), advanced_settings_for_gst_runner=self.settings,
                description=task["description"]
            )
            self.active_thread = QThread(self)
            self.active_worker.moveToThread(self.active_thread)
            self.active_worker.status_message.connect(self.on_worker_status_message)
            self.active_worker.progress_update.connect(self.on_worker_progress_update)
            self.active_worker.finished.connect(self.on_worker_finished)
            self.active_thread.started.connect(self.active_worker.run)
            self.active_thread.finished.connect(self.active_worker.deleteLater)
            self.active_thread.finished.connect(self.active_thread.deleteLater)
            self.active_thread.start()
            self.update_button_states()

        def _find_and_process_next_queued_task(self):
            next_idx = -1
            for i in range(len(self.tasks)):
                if self.tasks[i]["status_item"].text() == "Queued":
                    next_idx = i
                    break
                    
            if next_idx != -1:
                self._process_task_at_index(next_idx)
            else:
                self._handle_queue_finished()

        def _handle_queue_finished(self):
            self.overall_progress_bar.setVisible(False)
            self.update_button_states()
            self.current_task_index = -1

        @Slot(int, str)
        def on_worker_status_message(self, task_idx, message):
            if 0 <= task_idx < len(self.tasks) and self.current_task_index == task_idx:
                if not PROGRESS_RE.search(message) and \
                   not THINKING_RE.search(message) and \
                   not PROCESSING_RE.search(message) and \
                   not VALIDATING_RE.search(message):
                    self.tasks[task_idx]["status_item"].setText(message)

        @Slot(int, int, str)
        def on_worker_progress_update(self, task_idx, percentage, status_text):
            if 0 <= task_idx < len(self.tasks):
                if self.current_task_index == task_idx :
                    self.tasks[task_idx]["status_item"].setText(status_text)
                    self.overall_progress_bar.setValue(percentage)

        @Slot(int, str, bool)
        def on_worker_finished(self, task_idx, message, success):
            if 0 <= task_idx < len(self.tasks):
                self.tasks[task_idx]["status_item"].setText(message)
                
            if self.active_thread and self.active_thread.isRunning():
                self.active_thread.quit()
                self.active_thread.wait(1000)
                
            self.active_worker = None
            self.active_thread = None
            self.overall_progress_bar.setFormat("Error" if not success else "Completed")
            
            if not success:
                self.overall_progress_bar.setValue(0)
            else:
                self.overall_progress_bar.setValue(100)
                
            QTimer.singleShot(500, self._find_and_process_next_queued_task)
            self.update_button_states()

        @Slot()
        def stop_translation_action(self, force_quit=False):
            if self.active_worker:
                self.active_worker.cancel()
                if 0 <= self.current_task_index < len(self.tasks):
                     self.tasks[self.current_task_index]["status_item"].setText("Cancelling...")
            elif not force_quit:
                stopped_any_queued = False
                for i in range(len(self.tasks)):
                    if self.tasks[i]["status_item"].text() == "Queued":
                        self.tasks[i]["status_item"].setText("Cancelled (Queue Stopped)")
                        stopped_any_queued = True
                if stopped_any_queued:
                    self._cleanup_all_progress_files()
                    self._cleanup_translated_srt_file()
                else:
                    QMessageBox.information(self, "Stop", "No active translation to stop.")
                    
            if not force_quit:
                stopped_any_queued = False
                for i in range(len(self.tasks)):
                    if self.tasks[i]["status_item"].text() == "Queued":
                        self.tasks[i]["status_item"].setText("Cancelled (Queue Stopped)")
                        stopped_any_queued = True
                if stopped_any_queued:
                    self._cleanup_all_progress_files()
                    self._cleanup_translated_srt_file()
                if not self.active_worker:
                    self._find_and_process_next_queued_task()
            self.update_button_states()

        @Slot()
        def clear_queue_action(self):
            if self.active_thread and self.active_thread.isRunning():
                return
                
            reply = QMessageBox.question(self, "Clear Queue", "Remove all items from queue?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.tasks.clear()
                self.model.removeRows(0, self.model.rowCount())
                self.current_task_index = -1
                self.overall_progress_bar.setVisible(False)
                self.active_thread = None
                self.active_worker = None
                self.update_button_states()

        @Slot()
        def open_settings_dialog(self):
            dialog = SettingsDialog(self.settings.copy(), self)
            if dialog.exec():
                self.settings.update(dialog.get_settings())
                self._save_settings()

        def update_button_states(self):
            has_queued_tasks = any(task["status_item"].text() == "Queued" for task in self.tasks)
            is_processing = self.active_thread is not None and self.active_thread.isRunning()
            has_any_tasks = len(self.tasks) > 0
            has_api_key = bool(self.api_key_edit.text().strip())
            
            start_enabled = has_queued_tasks and not is_processing and has_api_key
            self.start_action.setEnabled(start_enabled)
            
            if start_enabled:
                self.stop_action.setEnabled(False)
            else:
                self.stop_action.setEnabled(is_processing or has_queued_tasks)
            
            self.clear_action.setEnabled(has_any_tasks and not is_processing)

if __name__ == "__main__":
    if "--run-gst-subprocess" in sys.argv:
        run_gst_translation_subprocess()
    else:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        exit_code = app.exec()
        sys.exit(exit_code)