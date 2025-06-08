import sys
import os
import json
import re
import subprocess
import signal
import time
import gemini_srt_translator as gst

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTreeView, QLineEdit, QLabel, QFileDialog, QMessageBox,
    QComboBox, QProgressBar, QDialog, QFormLayout,
    QSpinBox, QDoubleSpinBox, QCheckBox, QDialogButtonBox, QMenu, QTextEdit,
    QToolButton, QFrame, QStackedWidget, QStyle, QListWidget, QListWidgetItem
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction, QIcon, QKeySequence, QFont, QPixmap, QPainter, QLinearGradient, QColor, QPen, QFontMetrics
from PySide6.QtCore import Qt, QThread, Slot, QObject, Signal, QTimer, QItemSelectionModel, QRect
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
    base_path = get_app_directory()
    full_path = os.path.join(base_path, relative_path)
    return full_path

def load_colored_svg(svg_path, color="#A0A0A0"):
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()

        svg_content = re.sub(r'<path\s+d=', f'<path fill="{color}" d=', svg_content)
        svg_content = re.sub(r'<path\s+fill="[^"]*"\s+d=', f'<path fill="{color}" d=', svg_content)

        svg_bytes = svg_content.encode('utf-8')
        pixmap = QPixmap()
        pixmap.loadFromData(svg_bytes, 'SVG')

        return QIcon(pixmap)

    except Exception as e:
        print(f"Error loading SVG {svg_path}: {e}")
        return QIcon()

def load_stylesheet():
    try:
        qss_file_path = get_resource_path("dark.qss")
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

CONFIG_FILE = get_resource_path("config.json")

DEFAULT_SETTINGS = {
    "gemini_api_key": "", 
    "gemini_api_key2": "", 
    "target_language": "Swedish",
    "selected_languages": ["sv"],
    "model_name": "gemini-2.5-flash-preview-05-20",
    "output_file_naming_pattern": "{original_name}.{lang_code}.srt",
    "update_existing_queue_languages": False,
    "queue_on_exit": "clear_if_translated",
    "use_gst_parameters": False,
    "use_model_tuning": False,
    "description": "", 
    "batch_size": 30,
    "free_quota": True, 
    "skip_upgrade": False, 
    "progress_log": False, 
    "thoughts_log": False,
    "auto_resume": True,
    "temperature": 0.7, 
    "top_p": 0.95, 
    "top_k": 40, 
    "streaming": True, 
    "thinking": True, 
    "thinking_budget": 2048,
}

LANGUAGES = {
    "Afrikaans": "af", "Albanian": "sq", "Amharic": "am", "Arabic": "ar",
    "Armenian": "hy", "Azerbaijani": "az", "Basque": "eu", "Belarusian": "be",
    "Bengali": "bn", "Bosnian": "bs", "Bulgarian": "bg", "Catalan": "ca",
    "Cebuano": "ceb", "Chinese (Simplified)": "zh", "Chinese (Traditional)": "zh",
    "Corsican": "co", "Croatian": "hr", "Czech": "cs", "Danish": "da",
    "Dutch": "nl", "English": "en", "Estonian": "et", "Finnish": "fi",
    "French": "fr", "Frisian": "fy", "Galician": "gl", "Georgian": "ka",
    "German": "de", "Greek": "el", "Gujarati": "gu", "Haitian Creole": "ht",
    "Hausa": "ha", "Hebrew": "he", "Hindi": "hi", "Hungarian": "hu",
    "Icelandic": "is", "Igbo": "ig", "Indonesian": "id", "Italian": "it",
    "Japanese": "ja", "Javanese": "jv", "Kannada": "kn", "Kazakh": "kk",
    "Khmer": "km", "Korean": "ko", "Kurdish": "ku", "Kyrgyz": "ky",
    "Lao": "lo", "Latvian": "lv", "Lithuanian": "lt", "Luxembourgish": "lb",
    "Macedonian": "mk", "Malay": "ms", "Malayalam": "ml", "Maltese": "mt",
    "Marathi": "mr", "Mongolian": "mn", "Myanmar": "my", "Nepali": "ne",
    "Norwegian": "no", "Pashto": "ps", "Persian": "fa", "Polish": "pl",
    "Brazilian Portuguese": "pt", "Portuguese": "pt", "Punjabi": "pa",
    "Romanian": "ro", "Russian": "ru", "Samoan": "sm", "Serbian": "sr",
    "Sindhi": "sd", "Sinhala": "si", "Slovak": "sk", "Slovenian": "sl",
    "Somali": "so", "Spanish": "es", "Sundanese": "su", "Swahili": "sw",
    "Swedish": "sv", "Tajik": "tg", "Tamil": "ta", "Telugu": "te",
    "Thai": "th", "Turkish": "tr", "Ukrainian": "uk", "Urdu": "ur",
    "Uzbek": "uz", "Vietnamese": "vi", "Xhosa": "xh", "Yiddish": "yi",
    "Yoruba": "yo", "Zulu": "zu"
}

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
    
    def _save_queue_state(self):
        try:
            queue_dir = os.path.dirname(self.queue_file_path)
            if not os.path.exists(queue_dir):
                os.makedirs(queue_dir, exist_ok=True)
            
            with open(self.queue_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving queue state: {e}")
    
    def add_subtitle_to_queue(self, subtitle_path, languages, description, output_pattern):
        if subtitle_path not in self.state["queue_state"]:
            self.state["queue_state"][subtitle_path] = {
                "languages": {},
                "description": description,
                "target_languages": languages.copy(),
                "output_pattern": output_pattern
            }
        
        subtitle_dir = os.path.dirname(subtitle_path)
        subtitle_basename = os.path.basename(subtitle_path)
        name_part, ext = os.path.splitext(subtitle_basename)
        
        for code in LANGUAGES.values():
            if name_part.endswith(f".{code}"):
                name_part = name_part[:-len(f".{code}")]
                break
        
        for lang_code in languages:
            if lang_code not in self.state["queue_state"][subtitle_path]["languages"]:
                output_filename = output_pattern.format(original_name=name_part, lang_code=lang_code)
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
    
    def get_next_subtitle_with_work(self):
        for subtitle_path, subtitle_data in self.state["queue_state"].items():
            next_lang = self.get_next_language_to_process(subtitle_path)
            if next_lang:
                return subtitle_path
        return None
    
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
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = True
            self.mouse_pos = event.globalPosition().toPoint()
    
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
        
        self.normal_icon = load_colored_svg(svg_path, normal_color)
        self.hover_icon = load_colored_svg(svg_path, hover_color)
        self.disabled_icon = load_colored_svg(svg_path, disabled_color)
        
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
        
        self.normal_icon = load_colored_svg(svg_path, normal_color)
        self.hover_icon = load_colored_svg(svg_path, hover_color)
        self.disabled_icon = load_colored_svg(svg_path, disabled_color)
        
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
        basic_item.setIcon(load_colored_svg(get_resource_path("Files/cog-box.svg"), "#A0A0A0"))
        basic_item.setEditable(False)
        
        gst_item = QStandardItem("GST Parameters")
        gst_item.setIcon(load_colored_svg(get_resource_path("Files/gst-params.svg"), "#A0A0A0"))
        gst_item.setEditable(False)
        
        model_item = QStandardItem("Model Tuning")
        model_item.setIcon(load_colored_svg(get_resource_path("Files/model-tuning.svg"), "#A0A0A0"))
        model_item.setEditable(False)
        
        self.tree_model.appendRow(basic_item)
        self.tree_model.appendRow(gst_item)
        self.tree_model.appendRow(model_item)
        
        self.category_tree.setModel(self.tree_model)
        self.category_tree.selectionModel().currentChanged.connect(self.on_category_changed)
        
        main_layout.addWidget(self.category_tree)
        
        self.pages_widget = QStackedWidget()
        
        self.basic_page = self._build_basic_page()
        self.gst_page = self._build_gst_page()
        self.model_page = self._build_model_page()
        
        self.pages_widget.addWidget(self.basic_page)
        self.pages_widget.addWidget(self.gst_page)
        self.pages_widget.addWidget(self.model_page)
        
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
        
        main_layout.addLayout(form_layout)
        
        self.auto_resume_checkbox = QCheckBox("Resume Stopped Translations")
        self.auto_resume_checkbox.setChecked(self.settings.get("auto_resume", True))
        self.auto_resume_checkbox.setToolTip("Resumes stopped translations from where they left off")
        main_layout.addWidget(self.auto_resume_checkbox)
        
        self.update_queue_languages_checkbox = QCheckBox("Auto-Update Queue Languages")
        self.update_queue_languages_checkbox.setChecked(self.settings.get("update_existing_queue_languages", True))
        self.update_queue_languages_checkbox.setToolTip("When enabled, changing the language selection will update all existing queue items that match the previous selection")
        main_layout.addWidget(self.update_queue_languages_checkbox)
        
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
        
        # Form layout for batch size
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
    
    def reset_defaults(self):
        self.output_naming_pattern_edit.setText("{original_name}.{lang_code}.srt")
        self.queue_on_exit_combo.setCurrentIndex(1)
        self.auto_resume_checkbox.setChecked(True)
        self.update_queue_languages_checkbox.setChecked(True)
        
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
        
        self.toggle_gst_settings(False)
        self.toggle_model_settings(False)
    
    def get_settings(self):
        s = self.settings.copy()
        
        s["output_file_naming_pattern"] = self.output_naming_pattern_edit.text().strip()
        s["queue_on_exit"] = self.queue_on_exit_combo.currentData()
        s["auto_resume"] = self.auto_resume_checkbox.isChecked()
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
        
        return s

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
        
        for lang_name, lang_code in sorted_languages:
            item = QListWidgetItem()
            
            checkbox = QCheckBox(f"{lang_name} ({lang_code})")
            checkbox.setChecked(lang_code in self.selected_languages)
            checkbox.setProperty("lang_code", lang_code)
            
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

class TranslationWorker(QObject):
    finished = Signal(int, str, bool)
    progress_update = Signal(int, int, str)
    status_message = Signal(int, str)
    language_completed = Signal(int, str, bool)
    
    def __init__(self, task_index, input_file_path, target_languages, api_key, api_key2, model_name, settings, description="", queue_manager=None):
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
        self.is_cancelled = False
        self.current_language = None
        self.process = None
    
    def _generate_output_filename(self, lang_code):
        original_basename = os.path.basename(self.input_file_path)
        name_part, ext = os.path.splitext(original_basename)
        pattern = self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.srt")
        
        for code in LANGUAGES.values():
            if name_part.endswith(f".{code}"):
                name_part = name_part[:-len(f".{code}")]
                break
        
        final_name = pattern.format(original_name=name_part, lang_code=lang_code)
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
            
            output_file = self._generate_output_filename(target_language)
            if os.path.exists(output_file):
                os.remove(output_file)
                
        except Exception as e:
            print(f"Error cleaning up files for fresh start: {e}")
    
    def _build_cli_command(self, target_language):
        cmd = ["gst", "translate"]
        
        cmd.extend(["-k", self.api_key])
        cmd.extend(["-l", target_language])
        cmd.extend(["-i", self.input_file_path])
        cmd.extend(["-m", self.model_name])
        
        output_path = self._generate_output_filename(target_language)
        cmd.extend(["-o", output_path])
        
        if self.api_key2:
            cmd.extend(["-k2", self.api_key2])
        
        if self.description:
            cmd.extend(["-d", self.description])
        
        progress_line, progress_lang = self._detect_progress_file()
        auto_resume_enabled = self.settings.get("auto_resume", True)
        
        if auto_resume_enabled and progress_line is not None and progress_lang == target_language and progress_line >= 5:
            cmd.append("--resume")
        elif progress_line is not None:
            self._cleanup_for_fresh_start(target_language)
        
        if self.settings.get("use_gst_parameters", False):
            cmd.extend(["-b", str(self.settings.get("batch_size", 30))])
            
            if not self.settings.get("free_quota", True):
                cmd.append("--paid-quota")
            if self.settings.get("skip_upgrade", False):
                cmd.append("--skip-upgrade")
            if self.settings.get("progress_log", False):
                cmd.append("--progress-log")
            if self.settings.get("thoughts_log", False):
                cmd.append("--thoughts-log")
    
        cmd.append("--no-colors")
    
        if self.settings.get("use_model_tuning", False):
            cmd.extend(["--temperature", str(self.settings.get("temperature", 0.7))])
            cmd.extend(["--top-p", str(self.settings.get("top_p", 0.95))])
            cmd.extend(["--top-k", str(self.settings.get("top_k", 40))])
            cmd.extend(["--thinking-budget", str(self.settings.get("thinking_budget", 2048))])
            
            if not self.settings.get("streaming", True):
                cmd.append("--no-streaming")
            if not self.settings.get("thinking", True):
                cmd.append("--no-thinking")
        
        return cmd
    
    def _get_language_name(self, lang_code):
        for name, code in LANGUAGES.items():
            if code == lang_code:
                return name
        return lang_code.upper()
    
    def _send_interrupt_signal(self):
        if self.process and self.process.poll() is None:
            try:
                if os.name == 'nt':
                    try:
                        import ctypes
                        ctypes.windll.kernel32.GenerateConsoleCtrlEvent(0, 0)
                    except:
                        try:
                            self.process.send_signal(signal.SIGTERM)
                        except:
                            self.process.terminate()
                else:
                    try:
                        self.process.send_signal(signal.SIGINT)
                    except:
                        self.process.send_signal(signal.SIGTERM)
            except Exception as e:
                print(f"Error sending interrupt signal: {e}")
                self.process.terminate()
    
    @Slot()
    def run(self):
        if self.is_cancelled:
            self.finished.emit(self.task_index, "Cancelled before start", False)
            return

        if not self.queue_manager:
            self.finished.emit(self.task_index, "Queue manager not available", False)
            return

        completed_count = 0
        total_languages = len(self.target_languages)
        
        while True:
            if self.is_cancelled:
                break
            
            next_lang = self.queue_manager.get_next_language_to_process(self.input_file_path)
            if not next_lang:
                break
            
            self.current_language = next_lang
            lang_name = self._get_language_name(next_lang)
            
            try:
                self.queue_manager.mark_language_in_progress(self.input_file_path, next_lang)
                
                progress_line, progress_lang = self._detect_progress_file()
                if (progress_line and progress_lang == next_lang and 
                    self.settings.get("auto_resume", True) and progress_line >= 5):
                    self.status_message.emit(self.task_index, f"Resuming {lang_name} from line {progress_line}")
                else:
                    if progress_line and progress_line < 5:
                        self.status_message.emit(self.task_index, f"Cleaning up and starting fresh for {lang_name} (progress < 5 lines)")
                    elif progress_line and progress_lang != next_lang:
                        self.status_message.emit(self.task_index, f"Cleaning up and starting fresh for {lang_name} (different language)")
                    else:
                        self.status_message.emit(self.task_index, f"Translating to {lang_name}...")
                
                cmd = self._build_cli_command(next_lang)
                
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUNBUFFERED"] = "1"

                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=0,
                    env=env,
                    creationflags=0
                )

                found_completion = False
                line_count = 0

                for line in iter(self.process.stdout.readline, ''):
                    line_count += 1
                    if self.is_cancelled:
                        self._send_interrupt_signal()
                        
                        progress_saved = False
                        timeout_counter = 0
                        max_timeout = 50
                        
                        while timeout_counter < max_timeout and not progress_saved:
                            try:
                                stdout_line = self.process.stdout.readline()
                                if stdout_line and "Progress saved." in stdout_line:
                                    progress_saved = True
                                    break
                            except:
                                pass
                                
                            try:
                                stderr_line = self.process.stderr.readline()
                                if stderr_line and "Progress saved." in stderr_line:
                                    progress_saved = True
                                    break
                            except:
                                pass
                            
                            if self.process.poll() is not None:
                                break
                                
                            time.sleep(0.1)
                            timeout_counter += 1
                        
                        if not progress_saved and self.process.poll() is None:
                            self.process.terminate()
                        
                        break

                    line = line.strip()
                    if not line:
                        continue

                    if "Resuming from line" in line:
                        resume_match = re.search(r"Resuming from line (\d+)", line)
                        if resume_match:
                            resume_line = resume_match.group(1)
                            self.status_message.emit(self.task_index, f"Resuming {lang_name} from line {resume_line}")
                        continue

                    progress_match = re.search(r"Translating:\s*\|.*\|\s*(\d+)%\s*\(([^)]+)\)[^|]*\|\s*(Thinking|Processing)", line)
                    
                    if progress_match:
                        lang_percent = int(progress_match.group(1))
                        details = progress_match.group(2)
                        state = progress_match.group(3)
                        
                        overall_progress = int((completed_count / total_languages) * 100 + (lang_percent / total_languages))
                        status_text = f"{state}... {lang_name} ({details}) - {completed_count + 1}/{total_languages}"
                        
                        self.progress_update.emit(self.task_index, overall_progress, status_text)
                        continue

                    elif "Translation completed successfully!" in line:
                        found_completion = True
                        break

                if self.process.stderr:
                    try:
                        stderr_output = self.process.stderr.read()
                        if stderr_output:
                            print(f"GST stderr output: {stderr_output}")
                    except:
                        pass

                return_code = self.process.wait()
                self.process = None

                if self.is_cancelled:
                    summary = self.queue_manager.get_language_progress_summary(self.input_file_path)
                    self.finished.emit(self.task_index, summary, False)
                    return

                if return_code == 0 and found_completion:
                    self.queue_manager.mark_language_completed(self.input_file_path, next_lang)
                    completed_count += 1
                    self.language_completed.emit(self.task_index, next_lang, True)
                else:
                    self.queue_manager.mark_language_queued(self.input_file_path, next_lang)
                    self.language_completed.emit(self.task_index, next_lang, False)

            except Exception as e:
                print(f"Exception during translation of {next_lang}: {e}")
                if self.is_cancelled:
                    summary = self.queue_manager.get_language_progress_summary(self.input_file_path)
                    self.finished.emit(self.task_index, summary, False)
                    return
                else:
                    self.queue_manager.mark_language_queued(self.input_file_path, next_lang)
                    self.language_completed.emit(self.task_index, next_lang, False)

        if self.is_cancelled:
            summary = self.queue_manager.get_language_progress_summary(self.input_file_path)
            self.finished.emit(self.task_index, summary, False)
        else:
            final_summary = self.queue_manager.get_language_progress_summary(self.input_file_path)
            if final_summary == "Translated":
                self.queue_manager.cleanup_completed_subtitle(self.input_file_path)
                self.finished.emit(self.task_index, "Translated", True)
            else:
                self.finished.emit(self.task_index, final_summary, False)
    
    def cancel(self):
        self.is_cancelled = True
        self.status_message.emit(self.task_index, "Cancelling...")

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
        
        self.maximize_normal_icon = load_colored_svg(get_resource_path("Files/window-maximize.svg"), "#A0A0A0")
        self.restore_normal_icon = load_colored_svg(get_resource_path("Files/window-restore.svg"), "#A0A0A0")
        self.maximize_hover_icon = load_colored_svg(get_resource_path("Files/window-maximize.svg"), "white")
        self.restore_hover_icon = load_colored_svg(get_resource_path("Files/window-restore.svg"), "white")
        
        window_controls_layout.addWidget(self.minimize_btn)
        window_controls_layout.addWidget(self.maximize_btn)
        window_controls_layout.addWidget(self.close_btn)
        
        window_controls_widget = QWidget()
        window_controls_widget.setLayout(window_controls_layout)
        layout.addWidget(window_controls_widget)
        
        self.mouse_pressed = False
        self.mouse_pos = None
        self.was_maximized = False
        self.restore_geometry = None
    
    def minimize_window(self):
        if self.parent_window:
            self.parent_window.showMinimized()
    
    def toggle_maximize(self):
        if self.parent_window:
            if self.parent_window.isMaximized():
                self.parent_window.showNormal()
                self.maximize_btn.normal_icon = self.maximize_normal_icon
                self.maximize_btn.hover_icon = self.maximize_hover_icon
                self.maximize_btn.setIcon(self.maximize_normal_icon)
            else:
                self.restore_geometry = self.parent_window.geometry()
                self.parent_window.showMaximized()
                self.maximize_btn.normal_icon = self.restore_normal_icon
                self.maximize_btn.hover_icon = self.restore_hover_icon
                self.maximize_btn.setIcon(self.restore_normal_icon)
    
    def close_window(self):
        if self.parent_window:
            self.parent_window.close()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = True
            self.mouse_pos = event.globalPosition().toPoint()
            
            if self.parent_window:
                self.was_maximized = self.parent_window.isMaximized()
                
                if self.was_maximized and not self.restore_geometry:
                    screen = QApplication.primaryScreen().geometry()
                    restore_width = int(screen.width() * 0.8)
                    restore_height = int(screen.height() * 0.8)
                    restore_x = (screen.width() - restore_width) // 2
                    restore_y = (screen.height() - restore_height) // 2
                    
                    self.restore_geometry = QRect(restore_x, restore_y, restore_width, restore_height)
    
    def mouseMoveEvent(self, event):
        if self.mouse_pressed and self.mouse_pos and self.parent_window:
            current_pos = event.globalPosition().toPoint()
            
            if self.was_maximized:
                if self.restore_geometry:
                    self.parent_window.setGeometry(self.restore_geometry)
                else:
                    self.parent_window.showNormal()
                
                self.maximize_btn.normal_icon = self.maximize_normal_icon
                self.maximize_btn.hover_icon = self.maximize_hover_icon
                self.maximize_btn.setIcon(self.maximize_normal_icon)
                
                title_bar_width = self.width()
                click_ratio = (self.mouse_pos.x() - self.parent_window.geometry().left()) / self.parent_window.width() if self.parent_window.width() > 0 else 0.5
                
                new_x = current_pos.x() - int(self.parent_window.width() * click_ratio)
                new_y = current_pos.y() - 20
                
                self.parent_window.move(new_x, new_y)
                
                self.mouse_pos = current_pos
                self.was_maximized = False
                
            else:
                diff = current_pos - self.mouse_pos
                self.parent_window.move(self.parent_window.pos() + diff)
                self.mouse_pos = current_pos
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_pressed = False
            self.mouse_pos = None
            self.was_maximized = False
    
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_maximize()

class MainWindow(FramelessWidget):
    def __init__(self):
        super().__init__(hint=['min', 'max', 'close'])
        
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
        
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(icon_path)
        
        self.tasks = []
        self.current_task_index = -1
        self.settings = self._load_settings()
        self.active_thread = None
        self.active_worker = None
        self.clipboard_description = ""
        self.is_running = False
        self._exit_timer = None
        
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
        self.api_key_edit.textChanged.connect(lambda text: (self.settings.update({"gemini_api_key": text}), self.update_button_states()))
        api_keys_model_layout.addWidget(self.api_key_edit)
        
        self.api_key2_edit = CustomLineEdit()
        self.api_key2_edit.setPlaceholderText("Enter Gemini API Key (optional)")
        self.api_key2_edit.set_right_text("API Key 2", font_size=9, italic=False, color="#555555")
        self.api_key2_edit.setEchoMode(QLineEdit.Password)
        self.api_key2_edit.setText(self.settings.get("gemini_api_key2", ""))
        self.api_key2_edit.textChanged.connect(lambda text: self.settings.update({"gemini_api_key2": text}))
        api_keys_model_layout.addWidget(self.api_key2_edit)
        
        self.model_name_edit = CustomLineEdit()
        self.model_name_edit.setText(self.settings.get("model_name", "gemini-2.5-flash-preview-05-20"))
        self.model_name_edit.set_right_text("Model Used", font_size=9, italic=False, color="#555555")
        self.model_name_edit.textChanged.connect(lambda text: self.settings.update({"model_name": text}))
        api_keys_model_layout.addWidget(self.model_name_edit)
        
        config_layout.addRow(api_keys_model_layout)
        
        content_layout.addLayout(config_layout)
        
        self.tree_view = QTreeView()
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setRootIsDecorated(False)
        self.tree_view.setUniformRowHeights(True)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.show_context_menu)
        self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["File Name", "Output Languages", "Description", "Status"])
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
        
        self.start_stop_btn = QPushButton("Start Translations")
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
        
        self.selected_languages = self.settings.get("selected_languages", ["sv"])
        
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setTextVisible(True)
        self.overall_progress_bar.setFormat("%p% - Current Task")
        self.overall_progress_bar.setVisible(False)
        content_layout.addWidget(self.overall_progress_bar)
        
        content_layout.addWidget(controls_widget)
        
        main_layout.addWidget(content_widget)
        
        queue_state_file = get_resource_path("queue_state.json")
        self.queue_manager = QueueStateManager(queue_state_file)
        
        self._sync_ui_with_queue_state()
        
        self.update_button_states()
        
    def _sync_ui_with_queue_state(self):
        queue_state = self.queue_manager.state.get("queue_state", {})
        
        for subtitle_path, subtitle_data in queue_state.items():
            if os.path.exists(subtitle_path):
                target_languages = subtitle_data.get("target_languages", [])
                description = subtitle_data.get("description", "")
                
                task_exists = any(task['path'] == subtitle_path and task['languages'] == target_languages for task in self.tasks)
                
                if not task_exists:
                    self._add_task_to_ui(subtitle_path, target_languages, description)
                    
                    for task in self.tasks:
                        if task['path'] == subtitle_path:
                            summary = self.queue_manager.get_language_progress_summary(subtitle_path)
                            task["status_item"].setText(summary)
                            break
    
    def _add_task_to_ui(self, file_path, languages, description):
        lang_display = self._get_language_display_text(languages)
        lang_tooltip = self._format_language_tooltip(languages)
        
        path_item = QStandardItem(os.path.basename(file_path))
        path_item.setToolTip(os.path.dirname(file_path))
        path_item.setEditable(False)
        
        lang_item = QStandardItem(lang_display)
        lang_item.setToolTip(lang_tooltip)
        lang_item.setEditable(False)
        
        desc_item = QStandardItem(description)
        desc_item.setEditable(True)
        desc_item.setToolTip(description)
        
        status_item = QStandardItem("Queued")
        status_item.setEditable(False)
        
        self.model.appendRow([path_item, lang_item, desc_item, status_item])
        self.tasks.append({
            "path": file_path, 
            "path_item": path_item, 
            "lang_item": lang_item,
            "desc_item": desc_item, 
            "status_item": status_item, 
            "description": description,
            "languages": languages.copy(),
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
            self.stop_translation_action()
        else:
            self.start_translation_queue()

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
        self.model.setHorizontalHeaderLabels(["File Name", "Output Languages", "Description", "Status"])
        
        for task in self.tasks:
            self.model.appendRow([task["path_item"], task["lang_item"], task["desc_item"], task["status_item"]])
        
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
    
    def _cleanup_task_files(self, task):
        original_basename = os.path.basename(task["path"])
        name_part, ext = os.path.splitext(original_basename)
        original_dir = os.path.dirname(task["path"])
        
        progress_file = os.path.join(original_dir, f"{name_part}.progress")
        if os.path.exists(progress_file):
            try:
                os.remove(progress_file)
            except Exception:
                pass
        
        pattern = self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.srt")
        for code in LANGUAGES.values():
            if name_part.endswith(f".{code}"):
                name_part = name_part[:-len(f".{code}")]
                break
        
        for lang_code in task["languages"]:
            output_filename = pattern.format(original_name=name_part, lang_code=lang_code)
            output_file = os.path.join(original_dir, output_filename)
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except Exception:
                    pass
    
    def _cleanup_all_task_files(self):
        for task in self.tasks:
            self._cleanup_task_files(task)
                
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
        
        edit_languages_action = QAction("Edit Languages", self)
        edit_languages_action.triggered.connect(self.edit_selected_languages)
        menu.addAction(edit_languages_action)
        
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
                task = self.tasks[row]
                
                self.queue_manager.remove_subtitle_from_queue(task["path"])
                
                self._cleanup_task_files(task)
                
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
        except Exception as e:
            pass
        
        return DEFAULT_SETTINGS.copy()

    def _save_settings(self):
        try:
            self.settings["gemini_api_key"] = self.api_key_edit.text()
            self.settings["gemini_api_key2"] = self.api_key2_edit.text()
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
            queue_on_exit = self.settings.get("queue_on_exit", "clear_if_translated")
            
            if queue_on_exit == "clear":
                secondary_text = "Queue will stop gracefully but queue will be cleared on exit."
            elif queue_on_exit == "clear_if_translated":
                all_translated = True
                for task in self.tasks:
                    summary = self.queue_manager.get_language_progress_summary(task["path"])
                    if summary != "Translated":
                        all_translated = False
                        break
                
                if all_translated:
                    secondary_text = "Queue will stop gracefully and queue will be cleared on exit."
                else:
                    secondary_text = "Queue will stop gracefully and progress will be saved."
            else:
                secondary_text = "Queue will stop gracefully and progress will be saved."
            
            reply = CustomMessageBox.question(
                self, 
                'Confirm Exit', 
                "Translation in progress. Stop and exit?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No,
                secondary_text
            )
            if reply == QMessageBox.Yes:
                self.stop_translation_action()
                
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
        auto_resume = self.settings.get("auto_resume", True)
        
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
            elif not auto_resume:
                self._cleanup_all_task_files()
        elif queue_on_exit == "keep":
            if not auto_resume:
                self._cleanup_all_task_files()

    def add_files_action(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Subtitle Files", "", "SRT Files (*.srt);;All Files (*)")
        if files:
            for file_path in files:
                if any(task['path'] == file_path and task['languages'] == self.selected_languages for task in self.tasks):
                    continue
                
                self.queue_manager.add_subtitle_to_queue(
                    file_path, 
                    self.selected_languages.copy(), 
                    "", 
                    self.settings.get("output_file_naming_pattern", "{original_name}.{lang_code}.srt")
                )
                
                self._add_task_to_ui(file_path, self.selected_languages.copy(), "")
                
            self.update_button_states()

    def start_translation_queue(self):
        if len(self.api_key_edit.text().strip()) < 12:
            CustomMessageBox.warning(self, "API Key Invalid", "Please enter a valid Gemini API Key.")
            self.api_key_edit.setFocus()
            return
            
        if self.active_thread and self.active_thread.isRunning():
            CustomMessageBox.information(self, "In Progress", "A translation is already in progress.")
            return
        
        if not self.queue_manager.has_any_work_remaining():
            CustomMessageBox.information(self, "Queue Status", "No work remaining in queue.")
            return
        
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
        task["status_item"].setText("Preparing...")
        self.overall_progress_bar.setVisible(True)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setFormat("%p% - Current Task")
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
            queue_manager=self.queue_manager
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
        for i, task in enumerate(self.tasks):
            next_lang = self.queue_manager.get_next_language_to_process(task["path"])
            if next_lang:
                self._process_task_at_index(i)
                return
        
        self._handle_queue_finished()

    def _handle_queue_finished(self):
        self.overall_progress_bar.setVisible(False)
        self.is_running = False
        self.update_button_states()
        self.current_task_index = -1

    @Slot(int, str)
    def on_worker_status_message(self, task_idx, message):
        if 0 <= task_idx < len(self.tasks) and self.current_task_index == task_idx:
            current_text = self.tasks[task_idx]["status_item"].text()
            if not (current_text.startswith("Thinking") or current_text.startswith("Processing")):
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
        
        if not success and "cancelled" in message.lower():
            self.overall_progress_bar.setFormat("Stopped")
            self.overall_progress_bar.setValue(0)
        elif not success:
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

    @Slot()
    def stop_translation_action(self, force_quit=False):
        if self.active_worker:
            current_task_idx = self.current_task_index
            if 0 <= current_task_idx < len(self.tasks):
                current_task_path = self.tasks[current_task_idx]["path"]
                current_lang = self.queue_manager.get_current_language_in_progress(current_task_path)
                
                self.active_worker.cancel()
                self.tasks[current_task_idx]["status_item"].setText("Cancelling...")
                
                if current_lang:
                    self.queue_manager.mark_language_queued(current_task_path, current_lang)
        elif not force_quit:
            CustomMessageBox.information(self, "Stop", "No active translation to stop.")
        
        self.is_running = False
        self.update_button_states()
    
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
        api_key_valid = len(self.api_key_edit.text().strip()) >= 12
        
        if self.is_running or is_processing:
            self.start_stop_btn.setText("Stop Translating")
            self.start_stop_btn.setEnabled(True)
        else:
            if not api_key_valid:
                self.start_stop_btn.setText("Missing API Key")
                self.start_stop_btn.setEnabled(False)
            else:
                self.start_stop_btn.setText("Start Translating")
                self.start_stop_btn.setEnabled(has_work_remaining)
        
        self.clear_btn.setEnabled(has_any_tasks and not is_processing and not self.is_running)
        
    def _get_language_names_from_codes(self, lang_codes):
        names = []
        for code in lang_codes:
            for name, lang_code in LANGUAGES.items():
                if lang_code == code:
                    names.append(name)
                    break
            else:
                names.append(code.upper())
        return names
        
    def edit_selected_languages(self):
        selected_indexes = self.tree_view.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        current_languages = self.selected_languages.copy()
        
        if len(selected_indexes) == 1:
            row = selected_indexes[0].row()
            if 0 <= row < len(self.tasks):
                current_languages = self.tasks[row]["languages"].copy()
        
        dialog = LanguageSelectionDialog(current_languages, self)
        dialog.set_title("Edit Output Languages")
        
        if dialog.exec():
            new_languages = dialog.get_selected_languages()
            if not new_languages:
                return
            
            new_lang_display = self._get_language_display_text(new_languages)
            new_lang_tooltip = self._format_language_tooltip(new_languages)
            
            for index in selected_indexes:
                row = index.row()
                if 0 <= row < len(self.tasks):
                    self.tasks[row]["languages"] = new_languages.copy()
                    
                    self.tasks[row]["lang_item"].setText(new_lang_display)
                    self.tasks[row]["lang_item"].setToolTip(new_lang_tooltip)

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)

        def sigint_handler(*args):
            return
        
        signal.signal(signal.SIGINT, sigint_handler)
        
        timer = QTimer()
        timer.start(200) # ms
        timer.timeout.connect(lambda: None)

        app.setStyleSheet(load_stylesheet())
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except KeyboardInterrupt:
        sys.exit(0)