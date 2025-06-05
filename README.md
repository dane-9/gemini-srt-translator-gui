**Gemini SRT Translator GUI** is a user-friendly graphical interface for the powerful [Gemini SRT Translator](https://github.com/MaKTaiL/gemini-srt-translator) library, built with PySide6.

## Features

- **Intuitive Interface** - Easy to use Interface with intuitive functionality
- **Batch Processing** - Add multiple SRT files and process them in sequence from multiple directories at once. SRTs will be renamed and moved back to the source directory
- **Queue Management** - Use right-click context menu to reorder, reset, or remove files
- **Real-time Progress** - Live progress bars and status updates
- **Full GST Integration** - Access to all advanced GST parameters and model tuning
- **Easy Context Management** - Easily apply one description to multiple in queue

## Installation

### Download Exectuable

1. **Download** the latest release from [Releases](https://github.com/yourusername/gemini-srt-translator-gui/releases)
2. **Extract** the downloaded file to your desired location
3. **Run** `Gemini SRT Translator.exe` to launch

**That's it!** No Python installation, no dependencies, no setup required. Everything is bundled in the executable.

### Alternative: Run from Source (in Virtual Environment)

If you prefer to run from source code:
```bash
python -m venv venv
```
```bash
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```
```bash
pip install PySide6 gemini-srt-translator
```
```bash
git clone https://github.com/dane-9/gemini-srt-translator-gui.git
```
```bash
cd gemini-srt-translator-gui
```
```bash
python main.py
```

## Getting Your API Key

1. Go to [Google AI Studio API Key](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click **Generate API Key**
4. Copy and keep your key safe

## Quick Start

### Using the GUI

1. **Launch** - Double-click `Gemini SRT Translator.exe`
2. **Enter API Key** - Paste your Gemini API key in the API Keys field
3. **Select Language** - Choose target language from the dropdown
4. **Add Files** - Click "Add Subtitles" and select your SRT files
5. **Add Context** (Optional) - Right-click files to add descriptions for better translation
6. **Start Translation** - Click "Start Queue" and watch the progress

### File Output

Translated files are saved in the same directory as the source files with the naming pattern chosen:
{lang_code} is in accordance with ISO-639-1
```
original_file.sv.srt  # Swedish lang_code translation
original_file.fr.srt  # French lang_code translation
```

## Advanced Configuration

Access the Settings dialog for full control over GST parameters:

### GST Parameters

- **Start Line** - Resume translation from a specific line number
- **Batch Size** - Number of subtitle lines processed per request (default: 300)
- **Progress/Thoughts Logging** - Enable detailed logging files

### Model Tuning Parameters

- **Model Name** - Choose Gemini model (default: "gemini-2.5-flash-preview-05-20")
- **Temperature** - Controls randomness (0.0-2.0, default: 0.7)
- **Top P** - Nucleus sampling parameter (0.0-1.0, default: 0.95)
- **Top K** - Top-k sampling parameter (default: 40)
- **Thinking** - Enable AI reasoning for better accuracy (default: True)
- **Thinking Budget** - Token budget for thinking process (0-24576, default: 2048)

### Usage Tips

- **Dual API Keys** - Add a secondary key to avoid rate limits
- **Use Descriptions** - Add context like "Medical TV series", "Use medical terms" for domain-specific translations
- **Bulk-edit Descriptions** - Write one description then apply it to multiple subtitles
- **Queue Management** - Use right-click context menu to reorder, reset, or remove files

## Acknowledgments

This GUI is built on top of the excellent [Gemini SRT Translator](https://github.com/MaKTaiL/gemini-srt-translator) by [MaKTaiL](https://github.com/MaKTaiL).

## License

Distributed under the MIT License. See the [LICENSE](LICENSE) file for details.
