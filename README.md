# FreePoop — Deluxe Ultra (FreePoop V4)

FreePoop is a YouTube Poop (YTP) / YTPMV generator and editor built in Python 3.10 with a Tkinter GUI and a small CLI. This "Deluxe Ultra" release collects bug fixes, polishing and a number of production-ready features aimed at Windows 8.1 (but usable on other platforms with FFmpeg).

Highlights
- Robust stutter / scramble / reverse / pitch filter builders using ffprobe-derived durations (preserves audio+video alignment).
- GIF -> MP4 conversion with safe even-dimension scaling for overlays.
- FFmpeg YTP generation with concat helpers:
  - concat_all: join all project sources into one file.
  - concat_split: split sources into numbered concatenated outputs (e.g. "concat video (1).mp4").
- Real-time export progress reporting (parses ffmpeg stderr 'time=' tokens) surfaced in the GUI progress bar.
- Plugin system (plugins/ directory) with example sample_vocoder plugin; hooks:
  - `initialize(adaptor)`
  - `on_preprocess_audio(adaptor)` (e.g., vocoder transforms)
  - `on_before_export(adaptor, cmd_list)`
  - `on_run_export(adaptor, cmd_list)`
  - `run(adaptor, **kwargs)`
- Speech-to-text adapter supporting (preferred → fallback):
  - faster-whisper → whisper → speech_recognition (+ pocketsphinx / Google)
- Project save/load (JSON) and GUI for sources/overlays/presets/transcripts/poopify.
- CLI helpers (main.py) for scripted concat/export operations.
- PyInstaller spec included for building a Windows executable.

Requirements (minimal)
- Python 3.10
- FFmpeg (ffmpeg and ffprobe on PATH)
- Optional (for extra features):
  - yt-dlp (download remote sources)
  - faster-whisper or whisper (STT)
  - speechrecognition, pocketsphinx (STT fallback)
  - Pillow (if you extend overlay pre-processing)
  - PyInstaller (for packaging)

Quick start (Windows 8.1)
1. Install Python 3.10 and add it to PATH.
2. Install FFmpeg and add `ffmpeg.exe` and `ffprobe.exe` to PATH.
3. Clone/copy this project into a folder.
4. (Optional) Create and activate a virtualenv.
5. Install optional dependencies if you want extra features:
   pip install -r requirements.txt
   - or selectively install: pip install yt-dlp speechrecognition pocketsphinx whisper faster-whisper
6. Run the GUI:
   python app.py
   - or: python main.py export out.mp4 --source somefile.mp4
7. Use the GUI to add sources and overlays, choose a preset, and Export.

New / Notable features in Deluxe Ultra
- concat_all(output) and concat_split(...) to produce numbered "concat video (n).mp4" outputs.
- export_with_progress() — progress callback invoked with (percent, elapsed_seconds, ffmpeg_line).
- Robust trim/atrim + concat blocks for stutter and scramble; audio and video remain aligned.
- GIF conversion to MP4 with even scaling to ensure overlay compatibility on many platforms.
- Project JSON export/import for easy save/load.
- Plugin manager and sample plugin demonstrates how to add a vocoder or other effect pipeline.
- CLI (main.py) for automation and batch workflows.

Usage examples

GUI (recommended for interactive editing)
- python app.py
- Add local sources or URLs (yt-dlp if available).
- Add overlays (images, GIFs convert to MP4 automatically).
- Toggle effects (stutter/scramble/reverse/pitch).
- Choose a preset and click Export.
- Monitor progress bar and logs.

CLI
- Concatenate files into single output (re-encode):
  python main.py concat_all output.mp4 input1.mp4 input2.mp4 input3.mp4
- Concatenate files into multiple outputs, grouping 3 per output:
  python main.py concat_split outdir --per 3 --base "concat video" input1.mp4 input2.mp4 input3.mp4 input4.mp4
- Export single file via adaptor pipeline (apply preset JSON):
  python main.py export out.mp4 --source source.mp4 --preset mypreset.json

Plugin API (quick)
- Drop a .py file into the `plugins/` directory with exports:
  PLUGIN_NAME = "my_plugin"
  PLUGIN_DESC = "Do something"
  def initialize(adaptor): ...
  def on_preprocess_audio(adaptor): ...
  def on_before_export(adaptor, cmd_list): ...
  def run(adaptor, **kwargs): ...
- Enable via GUI plugin manager or by editing `.plugins.json`.

Common issues & troubleshooting
- "ffmpeg not found" or "ffprobe failed": Ensure ffmpeg and ffprobe binaries are installed and added to PATH. Test in a cmd window:
  ffmpeg -version
  ffprobe -version
- ffprobe errors parsing durations: some codecs/containers behave unexpectedly. Re-mux input into MP4/MKV first if ffprobe fails.
- "GIF conversion failed": check that ffmpeg can read the GIF; try with a different fps or re-export the GIF.
- STT not working: Make sure the optional packages are installed. Whisper/faster-whisper may require extra system libs.
- Invalid filter_complex errors: complex chains built from stutter/scramble/overlays can be long. If ffmpeg errors, inspect the generated command printed in the GUI log (or check logs) and try simpler combinations.

Packaging (Windows EXE)
- Use the provided `freepoop.spec` and PyInstaller on a Windows host:
  pyinstaller freepoop.spec
- Test the produced executable on a clean Windows environment that has the appropriate VC runtimes.

Development & extension ideas
- Add support for WebM/VP9 overlays with alpha channel preservation instead of MP4 fallback for GIFs.
- Add native vocoder plugin (e.g., interface to rubberband, world vocoder or a compiled binary).
- Add a plugin that exports "YTP packs" (zips containing overlays, MLG assets, green screen assets).
- Add timeline view with precise clip trimming and keyframe control.
- Add GPU-accelerated resize & transcode presets (NVENC, QSV) in `generate_command()` paths.

Project layout
- app.py — Tkinter GUI (Deluxe / V3–V4 UI)
- main.py — CLI helpers for concat/export
- ytpffmpeg_adaptor.py — core FFmpeg adaptor, concat helpers, filter builder, GIF conversion, export_with_progress
- plugin_manager.py — plugin discovery/enable/disable/run
- speech_to_text.py — STT adapter
- plugins/ — directory for plugin modules (sample_vocoder.py included)
- presets.json — example presets used by the GUI
- requirements.txt — optional dependencies list
- freepoop.spec — PyInstaller spec (example)

License
- MIT-style permissive. Use and extend as you like.

Contact / Next steps
- Tell me which feature you want prioritized next:
  - Add an example vocoder plugin that runs an external binary and replaces adaptor audio.
  - Add per-export progress bars for batch jobs and a job queue UI.
  - Implement a timeline editor with drag-select trimming.
  - Add unit tests that run ffmpeg dry runs to validate generated filter_complex strings.

Enjoy using FreePoop Deluxe Ultra — tell me what to build next.