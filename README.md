**Gemini SRT Translator GUI** is a user-friendly graphical interface for the excellent [Gemini SRT Translator](https://github.com/MaKTaiL/gemini-srt-translator) tool, built with PySide6. It offers a modern, intuitive interface for batch processing subtitle and video files with queue management features.

## User Interface
<img src="https://i.imgur.com/IrGPGSh.png" alt="gui" width="700"/>

## Features

-   **Batch Processing** - Process multiple files at once, even from different directories. The queue can handle any combination of task types:
    -   **Subtitles Only:** Quickly translate a folder full of `.srt` files.
    -   **Video + Subtitle:** Add a video and its matching `.srt` file. The GUI automatically pairs them, using the video's audio for context to produce the highest quality translation.
    -   **Video Only:** Add a video by itself to extract audio and attempt to translate the first embedded subtitle track. (Note: This can fail if the embedded track is not in SRT format).
-   **Multi-Language Translation** - Translate a single file into dozens of languages at once using a searchable language selection dialog.
-   **Persistent Queue** - The queue is automatically saved on exit and reloaded on the next launch, so you never lose your workspace.
-   **Advanced Queue Management** - Use the right-click context menu to reorder, reset status, bulk-edit descriptions, and change target languages for items in the queue.
-   **Customizable File Output** - Control how your files are named with a flexible naming pattern that preserves language codes and modifiers (like `.forced` or `.sdh`).
-   **API Key Validation** - The GUI quickly checks if your API keys are valid as you type, giving you immediate feedback and preventing errors after the translation process has already begun.
-   **Modern User Interface** - A completely custom-built interface featuring a frameless window, a modern dark theme. All processing is handled on a background thread so the UI never freezes.
-   **Real-time Progress** - Live progress bars and status updates
-   **Full GST Integration** - Access advanced `gst` parameters and model tuning options through the Settings menu.

## Installation

### Download Executable

1.  **Download** the latest release from the [Releases](https://github.com/dane-9/gemini-srt-translator-gui/releases) page.
2.  **Place** the executable in your desired location.
3.  **Run** `GeminiSRTTranslator.exe` to launch.

*No Python or manual dependency installation required. **FFmpeg is bundled directly with the executable** to handle all video and audio processing out-of-the-box.*

### Alternative: Run from Source (in a Virtual Environment)

If you prefer to run from source code:
```bash
git clone https://github.com/dane-9/gemini-srt-translator-gui.git
```
```bash
cd gemini-srt-translator-gui
```
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```
```bash
pip install -r requirements.txt
```
```bash
python main.py
```

## Getting Your API Key

1.  Go to [Google AI Studio API Key](https://aistudio.google.com/apikey).
2.  Sign in with your Google account.
3.  Click **Generate API Key**.
4.  Copy and keep your key safe.

## Quick Start

### Using the GUI

1.  **Launch** - Double-click `Gemini SRT Translator.exe`.
2.  **Enter API Key** - Paste your Gemini API key into the "API Key 1" field.
3.  **Select Language(s)** - Click the "Language Selection" button in the title bar to choose one or more target languages.
4.  **Add Files** - Click "Add Files". **For best results, select both your `.srt` file and its matching video file (`.mp4`, `.mkv`) together.** The app will automatically pair them.
5.  **Add Context** (Optional) - Right-click items in the queue to add descriptions for better, more context-aware translations.
6.  **Start Translation** - Click "Start Translating" and watch the progress.

### File Output

Translated files are saved in the same directory as the source files. The default naming pattern is `{original_name}.{lang_code}.{modifiers}.srt`.
-   `{lang_code}` is in accordance with ISO-639-1 and can also detect ISO-639-2 from input files.
-   `{modifiers}` preserves tags like `.forced` or `.sdh` from the original filename.

**Examples:**
```
# Original: movie.srt -> Translated to French
movie.fr.srt

# Original: movie.en.forced.srt -> Translated to German
movie.de.forced.srt
```

## Advanced Configuration

Access the **Settings** dialog from the title bar for full control over `gst` parameters.

### GST Parameters

-   **Batch Size** - Number of subtitle lines processed per request (default: 300).
-   **Progress/Thoughts Logging** - Enable detailed logging files from the backend.

### Model Tuning Parameters

-   **Model Name** - Choose the Gemini model to use (default: "gemini-1.5-flash-latest").
-   **Temperature** - Controls randomness (0.0-2.0, default: 0.7).
-   **Top P / Top K** - Advanced sampling parameters.
-   **Thinking** - Enable AI reasoning for potentially better accuracy (default: True).
-   **Thinking Budget** - Token budget for the thinking process (default: 2048).

## Usage Tips

-   **Prefer Video + SRT Pairs over Video-Only** - It is ***highly recommended*** to add both the video and its corresponding `.srt` file. This ensures the correct source subtitle is used and provides audio context for the best translation quality. Adding a video-only file will attempt to extract the *first embedded subtitle track*, which may have an unknown language or be in a format other than SRT, causing the translation to fail.
-   **Dual API Keys** - Add a secondary key in the "API Key 2" field to avoid rate limits and increase your processing capacity.
-   **Use Descriptions** - Add context like *"Medical TV series, use formal medical terminology"* for domain-specific translations.
-   **Bulk-edit Descriptions** - Select multiple files, right-click, and choose "Bulk Edit Description" to apply the same context to many files at once.
-   **Manage Multiple Languages** - Right-click any task in the queue to change its target languages without having to re-add it.

## Acknowledgments

This GUI is built on top of the excellent [Gemini SRT Translator](https://github.com/MaKTaiL/gemini-srt-translator) library by [MaKTaiL](https://github.com/MaKTaiL).

## License

Distributed under the MIT License. See the [LICENSE](LICENSE) file for details.