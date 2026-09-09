# 🎙️ Whisper Video Transcriber Tool

A lightweight, high-performance command-line tool built on **faster-whisper** (CTranslate2) to transcribe video files (`.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`) into timestamped `.srt` subtitles and readable `.md` condensed summaries.

Supports **Windows** and **macOS** with **NVIDIA GPU acceleration** (up to ~10x realtime speed) and automatic **CPU fallback**.

---

## ✨ Features

- ⚡ **Super Fast**: Powered by `faster-whisper` and CTranslate2 engine.
- 💻 **Cross-Platform**: Automated 1-click setup scripts for Windows and macOS.
- 🚀 **Auto GPU / CPU Detection**: Uses NVIDIA CUDA GPU if available; automatically falls back to CPU on non-GPU laptops.
- 📝 **Dual Output Formats**:
  - `.srt` — Standard subtitle file (automatically recognized by VLC and video players).
  - `.md` — Condensed notes formatted with minute-by-minute timestamps for quick reading.
- 🔍 **Interactive Selection**: List all videos in the directory and pick by number or filename.

---

## 🛠️ First-Time Setup (Run Once)

Clone this repository or download the ZIP, then open the folder in **VS Code** or your Terminal.

### 🪟 On Windows
Open Command Prompt / VS Code Terminal in this folder and run:
```cmd
.\setup.bat
```

### 🍎 On macOS / Linux
Open Terminal in this folder and run:
```bash
chmod +x setup.sh
./setup.sh
```

*(This automatically creates a local `.venv` environment and installs all necessary libraries).*

---

## 🚀 How to Use

Copy your video files (`.mp4`, `.mkv`, `.mov`, etc.) into this folder or any subfolder.

### 1. View Available Videos
List all videos and check which ones are already transcribed:

**Windows**:
```cmd
.\.venv\Scripts\python transcribe.py --list
```
**macOS**:
```bash
./.venv/bin/python transcribe.py --list
```

*Example Output:*
```text
[ 1] done     CLASS-105-DOCKER INTRO/PART 1.mp4
[ 2] pending  CLASS-105-DOCKER INTRO/PART 2.mp4
[ 3] pending  CLASS-106-DOCKER IMAGES.mp4

1 of 3 transcribed, 2 pending.
```

### 2. Transcribe a Video
Transcribe by passing the video **number** from `--list` or part of the filename:

**Windows**:
```cmd
.\.venv\Scripts\python transcribe.py 2
```
**macOS**:
```bash
./.venv/bin/python transcribe.py 2
```

You can also use a partial filename match:
```cmd
.\.venv\Scripts\python transcribe.py "CLASS-106"
```

### 3. Batch Transcribe (PowerShell Loop)
To transcribe videos 5 through 10 sequentially:
```powershell
foreach ($n in 5..10) { .\.venv\Scripts\python transcribe.py $n }
```

---

## ⚙️ Advanced Options

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--model` | Model size (`tiny`, `base`, `small`, `medium`, `large-v3`) | `medium` |
| `--device` | Hardware device (`auto`, `cuda`, `cpu`) | `auto` |
| `--cpu-threads` | Number of CPU threads to use | `6` |
| `--beam-size` | Beam search size (`1` is ~2x faster, `5` is more accurate) | `5` |
| `--overwrite` | Force re-transcribing a video that already has an `.srt` | `Disabled` |
| `--condense` | Rebuild `.md` files from existing `.srt` files without re-transcribing | `Disabled` |

*Example:*
```cmd
.\.venv\Scripts\python transcribe.py 2 --model small --beam-size 1
```

---

## 📄 Output Files

For a video named `Lecture.mp4`, two files are generated right next to it:
1. `Lecture.srt` — Standard subtitle file.
2. `Lecture.md` — Markdown summary with timestamp headings every 60 seconds.

---

## 📜 License
Open-source under the MIT License.
