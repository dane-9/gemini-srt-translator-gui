**Gemini SRT Translator GUI** is a user-friendly graphical interface for the powerful [Gemini SRT Translator](https://github.com/MaKTaiL/gemini-srt-translator) library, built with PySide6.

## Features

- **Batch Processing** - Add multiple SRT files and process them in sequence
- **Visual Queue Management** - Drag, drop, sort, and manage translation jobs
- **Real-time Progress** - Live progress bars and status updates
- **Full GST Integration** - Access to all advanced GST parameters and model tuning
- **Context Management** - Add descriptions and copy/paste between files
- **Smart Resume** - Automatically continues to next file after completion
- **Modern Interface** - Clean, intuitive design with keyboard shortcuts
- **Persistent Settings** - All configurations saved automatically

## Installation

### Download Exectuable

1. **Download** the latest release from [Releases](https://github.com/yourusername/gemini-srt-translator-gui/releases)
2. **Extract** the downloaded file to your desired location
3. **Run** `Gemini SRT Translator.exe` to launch

**That's it!** No Python installation, no dependencies, no setup required. Everything is bundled in the executable.

### Alternative: Run from Source

If you prefer to run from source code:

```bash
git clone https://github.com/dane-9/gemini-srt-translator-gui.git
```
```bash
cd gemini-srt-translator-gui
```
```bash
pip install PySide6 gemini-srt-translator
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

Translated files are saved in the same directory as the source files with the naming pattern:

```
original_file.sv.srt  # Swedish translation
original_file.fr.srt  # French translation
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