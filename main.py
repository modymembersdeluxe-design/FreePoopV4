# main.py - FreePoopV4 Deluxe Ultra GUI (Tkinter)
# - GUI for adding sources/overlays, reordering, concat helpers and export with progress
# - Uses ytpffmpeg_adaptor.YTPFFmpegAdaptor for all heavy lifting
# Target: Python 3.10 on Windows 8.1

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import time
import json
from pathlib import Path
from typing import Optional

from ytpffmpeg_adaptor import YTPFFmpegAdaptor

# Optional speech-to-text adapter (if available)
try:
    import speech_to_text as stt_mod
except Exception:
    stt_mod = None

APP_TITLE = "FreePoop V4 — Deluxe Ultra (Tkinter GUI)"

class FreePoopGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x760")
        self.adaptor = YTPFFmpegAdaptor()
        self.presets = {}
        self._load_presets()
        self._build_ui()

    def _load_presets(self):
        try:
            here = Path(__file__).resolve().parent
            pf = here / "presets.json"
            if pf.exists():
                with pf.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    self.presets = data.get("presets", {})
                    return
        except Exception:
            pass
        # fallback basic presets
        self.presets = {
            "classic": {"stutter": True, "stutter_ms": 120, "stutter_repeats": 6, "scramble": True, "scramble_segments": 8, "reverse": False, "pitch_semitones": 3},
            "modern": {"stutter": True, "stutter_ms": 80, "stutter_repeats": 3, "scramble": False, "scramble_segments": 6, "reverse": True, "pitch_semitones": -5}
        }

    def _build_ui(self):
        # Toolbar
        toolbar = tk.Frame(self)
        toolbar.pack(side="top", fill="x", padx=8, pady=6)
        tk.Button(toolbar, text="Add Source", command=self.add_source).pack(side="left", padx=4)
        tk.Button(toolbar, text="Move Up", command=lambda: self.move_item(self.lst_sources, -1)).pack(side="left")
        tk.Button(toolbar, text="Move Down", command=lambda: self.move_item(self.lst_sources, 1)).pack(side="left")
        tk.Button(toolbar, text="Remove Source", command=self.remove_selected_source).pack(side="left", padx=4)
        tk.Button(toolbar, text="Concat All", command=self.concat_all_dialog).pack(side="left", padx=8)
        tk.Button(toolbar, text="Concat Split...", command=self.concat_split_dialog).pack(side="left")
        tk.Button(toolbar, text="Add Overlay", command=self.add_overlay).pack(side="left", padx=8)
        tk.Button(toolbar, text="Export", command=self.export).pack(side="left", padx=8)
        tk.Button(toolbar, text="Transcribe (STT)", command=self.transcribe_selected).pack(side="left", padx=8)
        tk.Button(toolbar, text="Preview", command=self.preview).pack(side="left", padx=8)

        main = tk.PanedWindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=8, pady=8)

        left = tk.Frame(main)
        main.add(left, width=420)
        right = tk.Frame(main)
        main.add(right)

        # Left: sources and overlays
        tk.Label(left, text="Sources (order matters for concat)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.lst_sources = tk.Listbox(left, width=60, height=12)
        self.lst_sources.pack(padx=6, pady=6)
        tk.Label(left, text="Overlays (images/videos/gifs)", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.lst_overlays = tk.Listbox(left, width=60, height=8)
        self.lst_overlays.pack(padx=6, pady=6)

        # Right: effects, presets, transcript, log & progress
        eff_frame = tk.LabelFrame(right, text="Effects & Presets", padx=8, pady=8)
        eff_frame.pack(fill="x", padx=8, pady=(0,8))
        self.chk_stutter = tk.IntVar(value=1 if self.adaptor.effects.get("stutter") else 0)
        tk.Checkbutton(eff_frame, text="Stutter", variable=self.chk_stutter, command=self.update_effects).grid(row=0, column=0, sticky="w")
        tk.Label(eff_frame, text="ms").grid(row=0, column=2, sticky="w")
        self.ent_stutter_ms = tk.Spinbox(eff_frame, from_=20, to=2000, width=6, command=self.update_effects)
        self.ent_stutter_ms.delete(0, "end"); self.ent_stutter_ms.insert(0, str(self.adaptor.effects.get("stutter_ms",120)))
        self.ent_stutter_ms.grid(row=0, column=1, sticky="w", padx=(6,12))
        self.chk_scramble = tk.IntVar(value=1 if self.adaptor.effects.get("scramble") else 0)
        tk.Checkbutton(eff_frame, text="Scramble", variable=self.chk_scramble, command=self.update_effects).grid(row=1, column=0, sticky="w")
        tk.Label(eff_frame, text="Segments").grid(row=1, column=2, sticky="w")
        self.ent_scramble_segments = tk.Spinbox(eff_frame, from_=2, to=64, width=6, command=self.update_effects)
        self.ent_scramble_segments.delete(0, "end"); self.ent_scramble_segments.insert(0, str(self.adaptor.effects.get("scramble_segments",8)))
        self.ent_scramble_segments.grid(row=1, column=1, sticky="w", padx=(6,12))
        self.chk_reverse = tk.IntVar(value=1 if self.adaptor.effects.get("reverse") else 0)
        tk.Checkbutton(eff_frame, text="Reverse", variable=self.chk_reverse, command=self.update_effects).grid(row=2, column=0, sticky="w")
        tk.Label(eff_frame, text="Pitch (semitones)").grid(row=3, column=0, sticky="w", pady=(8,0))
        self.sld_pitch = tk.Scale(eff_frame, from_=-12, to=12, orient="horizontal", length=260, command=self.update_pitch)
        self.sld_pitch.set(self.adaptor.effects.get("pitch_semitones", 0.0))
        self.sld_pitch.grid(row=4, column=0, columnspan=3, pady=(0,6))
        tk.Label(eff_frame, text="Preset").grid(row=5, column=0, sticky="w")
        self.cmb_preset = ttk.Combobox(eff_frame, state="readonly", values=list(self.presets.keys()))
        if self.presets:
            self.cmb_preset.current(0)
        self.cmb_preset.grid(row=5, column=1, columnspan=2, sticky="w")
        self.cmb_preset.bind("<<ComboboxSelected>>", self.apply_preset)

        trans_frame = tk.LabelFrame(right, text="Transcript / Poopify", padx=8, pady=8)
        trans_frame.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.txt_transcript = tk.Text(trans_frame, height=12)
        self.txt_transcript.pack(fill="both", expand=True)
        tk.Button(trans_frame, text="Poopify (shuffle)", command=self.poopify_transcript).pack(pady=(6,0))

        bottom = tk.LabelFrame(self, text="Export Progress & Log", padx=8, pady=8)
        bottom.pack(fill="both", padx=8, pady=(0,8))
        prog_frame = tk.Frame(bottom)
        prog_frame.pack(fill="x")
        self.progress = ttk.Progressbar(prog_frame, orient="horizontal", length=700, mode="determinate")
        self.progress.pack(side="left", padx=8, pady=4)
        self.lbl_progress = tk.Label(prog_frame, text="Idle")
        self.lbl_progress.pack(side="left", padx=8)
        self.txt_log = tk.Text(bottom, height=10)
        self.txt_log.pack(fill="both", expand=True, pady=(6,0))

    # --------------- UI helpers ---------------
    def log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        try:
            self.txt_log.insert("end", f"[{ts}] {text}\n")
            self.txt_log.see("end")
        except Exception:
            print(f"[{ts}] {text}")

    def move_item(self, listbox: tk.Listbox, direction: int):
        sel = listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        new = idx + direction
        if new < 0 or new >= listbox.size():
            return
        item = listbox.get(idx)
        listbox.delete(idx)
        listbox.insert(new, item)
        listbox.select_set(new)
        # update adaptor.source ordering if moved sources
        if listbox is self.lst_sources:
            self.adaptor.sources = [Path(x) for x in self.lst_sources.get(0, "end")]

    # --------------- sources / overlays ---------------
    def add_source(self):
        fn = filedialog.askopenfilename(title="Select source(s)", multiple=False,
                                        filetypes=[("Video/Audio", "*.mp4 *.mkv *.webm *.mov *.avi *.mp3 *.wav *.flac"), ("All", "*.*")])
        if not fn:
            return
        try:
            p = self.adaptor.add_source(fn)
            self.lst_sources.insert("end", str(p))
            self.log("Added source: " + str(p))
        except Exception as e:
            messagebox.showerror("Add source error", str(e))
            self.log("Error adding source: " + str(e))

    def remove_selected_source(self):
        sel = self.lst_sources.curselection()
        if not sel:
            return
        idx = sel[0]
        itm = self.lst_sources.get(idx)
        self.lst_sources.delete(idx)
        self.adaptor.sources = [s for s in self.adaptor.sources if str(s) != itm]
        self.log("Removed source: " + itm)

    def add_overlay(self):
        fn = filedialog.askopenfilename(title="Select overlay (image/gif/video)")
        if not fn:
            return
        try:
            if fn.lower().endswith(".gif") and hasattr(self.adaptor, "prepare_overlay_from_gif"):
                # quick convert
                conv = self.adaptor.prepare_overlay_from_gif(fn)
                self.adaptor.add_overlay(str(conv))
                self.lst_overlays.insert("end", f"{conv} (gif->mp4)")
                self.log("Added GIF overlay (converted)")
            else:
                ov = self.adaptor.add_overlay(fn)
                self.lst_overlays.insert("end", str(ov.get("path")))
                self.log("Added overlay: " + fn)
        except Exception as e:
            messagebox.showerror("Add overlay error", str(e))
            self.log("Error adding overlay: " + str(e))

    def remove_selected_overlay(self):
        sel = self.lst_overlays.curselection()
        if not sel:
            return
        idx = sel[0]
        itm = self.lst_overlays.get(idx)
        self.lst_overlays.delete(idx)
        self.adaptor.overlays = [o for o in self.adaptor.overlays if str(o.get("path")) != itm.split(" (")[0]]
        self.log("Removed overlay: " + itm)

    # --------------- effects & presets ---------------
    def update_effects(self):
        try:
            st_ms = int(self.ent_stutter_ms.get())
        except Exception:
            st_ms = 120
        try:
            scr_seg = int(self.ent_scramble_segments.get())
        except Exception:
            scr_seg = 8
        self.adaptor.set_effect("stutter", bool(self.chk_stutter.get()))
        self.adaptor.set_effect("stutter_ms", st_ms)
        self.adaptor.set_effect("stutter_repeats", int(self.adaptor.effects.get("stutter_repeats", 6)))
        self.adaptor.set_effect("scramble", bool(self.chk_scramble.get()))
        self.adaptor.set_effect("scramble_segments", scr_seg)
        self.adaptor.set_effect("reverse", bool(self.chk_reverse.get()))
        self.adaptor.set_effect("pitch_semitones", float(self.sld_pitch.get()))
        self.log("Effects updated")

    def update_pitch(self, val):
        self.adaptor.set_effect("pitch_semitones", float(val))
        self.log(f"Pitch set to {val}")

    def apply_preset(self, _evt=None):
        key = self.cmb_preset.get()
        preset = self.presets.get(key)
        if not preset:
            return
        self.adaptor.load_preset(preset)
        # update UI to show preset values
        self.chk_stutter.set(1 if preset.get("stutter") else 0)
        self.ent_stutter_ms.delete(0, "end"); self.ent_stutter_ms.insert(0, str(preset.get("stutter_ms", 120)))
        self.ent_scramble_segments.delete(0, "end"); self.ent_scramble_segments.insert(0, str(preset.get("scramble_segments", 8)))
        self.chk_scramble.set(1 if preset.get("scramble") else 0)
        self.chk_reverse.set(1 if preset.get("reverse") else 0)
        self.sld_pitch.set(preset.get("pitch_semitones", 0))
        self.log("Preset applied: " + key)

    # --------------- transcript & poopify ---------------
    def transcribe_selected(self):
        if not self.adaptor.sources:
            messagebox.showwarning("No source", "Add a source before transcribing.")
            return
        if stt_mod is None or not hasattr(stt_mod, "transcribe_file"):
            messagebox.showinfo("STT backend missing", "Install faster-whisper/whisper or speech_recognition to enable STT.")
            return
        src = str(self.adaptor.sources[0])
        def do_transcribe():
            self.log("Transcribing (may take a while)...")
            try:
                txt = stt_mod.transcribe_file(src)
                self.txt_transcript.delete("1.0", "end")
                self.txt_transcript.insert("1.0", txt)
                self.log("Transcription complete.")
            except Exception as e:
                self.log("Transcription error: " + str(e))
                messagebox.showerror("Transcription error", str(e))
        threading.Thread(target=do_transcribe, daemon=True).start()

    def poopify_transcript(self):
        txt = self.txt_transcript.get("1.0", "end").strip()
        if not txt:
            messagebox.showwarning("No transcript", "Transcribe or paste text first.")
            return
        import random
        words = txt.split()
        if len(words) <= 1:
            return
        swaps = max(1, int(len(words) * 0.35))
        for _ in range(swaps):
            i = random.randrange(len(words)); j = random.randrange(len(words))
            words[i], words[j] = words[j], words[i]
        pooped = " ".join(words)
        self.txt_transcript.delete("1.0", "end"); self.txt_transcript.insert("1.0", pooped)
        self.adaptor.preset_params["pooped_transcript"] = pooped
        self.log("Poopified transcript stored to project params.")

    # --------------- preview & export ---------------
    def preview(self):
        try:
            self.adaptor.preview()
            self.log("Preview launched (ffplay).")
        except Exception as e:
            self.log("Preview error: " + str(e))
            messagebox.showerror("Preview error", str(e))

    def export(self):
        if not self.adaptor.sources:
            messagebox.showwarning("No source", "Add a source before exporting.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4", "*.mp4")])
        if not out:
            return
        self.update_effects()
        def progress_cb(percent, tsec, message):
            try:
                if percent is not None:
                    self.progress['value'] = percent * 100.0
                    self.lbl_progress.config(text=f"{percent*100:.1f}% {message[:60]}")
                else:
                    self.lbl_progress.config(text=message[:60])
            except Exception:
                pass
        def on_done(rc, stderr):
            if rc == 0:
                self.log("Export finished: " + out)
                messagebox.showinfo("Export", "Export completed successfully.")
            else:
                self.log("Export failed:\n" + (stderr or ""))
                messagebox.showerror("Export failed", "See log for details.")
            time.sleep(0.5)
            self.progress['value'] = 0
            self.lbl_progress.config(text="Idle")
        def run():
            self.log("Starting export: " + out)
            rc, stderr = self.adaptor.export_with_progress(out, progress_callback=progress_cb)
            on_done(rc, stderr)
        threading.Thread(target=run, daemon=True).start()

    # --------------- concat helpers ---------------
    def concat_all_dialog(self):
        if not self.adaptor.sources:
            messagebox.showwarning("No sources", "Add sources to concat first.")
            return
        out = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4", "*.mp4")], title="Concat All -> Output file")
        if not out:
            return
        def run():
            self.log("Concatenating all sources -> " + out)
            proc = self.adaptor.concat_all(out, reencode=True, overwrite=True)
            if proc.returncode == 0:
                self.log("Concat all succeeded: " + out)
                messagebox.showinfo("Concat", "Concat completed.")
                # optionally add result to sources list
                self.lst_sources.insert("end", out)
                self.adaptor.add_source(out)
            else:
                self.log("Concat failed:\n" + (proc.stderr or proc.stdout or ""))
                messagebox.showerror("Concat failed", "See log.")
        threading.Thread(target=run, daemon=True).start()

    def concat_split_dialog(self):
        if not self.adaptor.sources:
            messagebox.showwarning("No sources", "Add sources to concat first.")
            return
        # small dialog to get per-file count and output directory
        dlg = tk.Toplevel(self)
        dlg.title("Concat Split Options")
        tk.Label(dlg, text="Files per output:").grid(row=0, column=0, padx=8, pady=8)
        spin = tk.Spinbox(dlg, from_=1, to=100, width=6); spin.delete(0, "end"); spin.insert(0, "1"); spin.grid(row=0, column=1, padx=8, pady=8)
        tk.Label(dlg, text="Base filename:").grid(row=1, column=0, padx=8, pady=8)
        ent_base = tk.Entry(dlg, width=30); ent_base.insert(0, "concat video"); ent_base.grid(row=1, column=1, padx=8, pady=8)
        def on_ok():
            per = int(spin.get())
            base = ent_base.get().strip() or "concat video"
            outdir = filedialog.askdirectory(title="Select output directory")
            if not outdir:
                dlg.destroy(); return
            dlg.destroy()
            def run_split():
                self.log(f"Starting concat split into '{outdir}' with {per} per file")
                results = self.adaptor.concat_split(outdir, base_name=base, per_file=per, reencode=True, overwrite=True)
                for r in results:
                    if r["returncode"] == 0:
                        self.log("Wrote: " + r["out"])
                    else:
                        self.log("Failed: " + r["out"] + "\n" + r.get("stderr",""))
                messagebox.showinfo("Concat split", "Concat split finished. See log.")
            threading.Thread(target=run_split, daemon=True).start()
        tk.Button(dlg, text="Start", command=on_ok).grid(row=2, column=0, columnspan=2, pady=10)

if __name__ == "__main__":
    app = FreePoopGUI()
    app.mainloop()