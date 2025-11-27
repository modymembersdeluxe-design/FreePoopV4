# ytpffmpeg_adaptor.py - FreePoop V4 Deluxe Ultra adaptor (updated)
# - Keeps robust stutter/scramble/pitch/filter_complex builders
# - Adds concat_all and concat_split helpers (concat demuxer approach)
# - Exports with progress parsing (time=...) via export_with_progress
# - Maintains compatibility: set_effect, load_preset, add_source/add_overlay, prepare_overlay_from_gif
from __future__ import annotations
import subprocess
import tempfile
import uuid
import random
from typing import List, Dict, Optional, Tuple, Callable, Any
from pathlib import Path

try:
    import yt_dlp
except Exception:
    yt_dlp = None

try:
    from plugin_manager import PluginManager
except Exception:
    PluginManager = None


def _safe_run(cmd: List[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, cwd=cwd)


def ffprobe_duration(path: Path, ffprobe_bin: str = "ffprobe") -> float:
    cmd = [ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    p = _safe_run(cmd)
    if p.returncode != 0:
        raise RuntimeError("ffprobe failed: " + (p.stderr or p.stdout))
    try:
        return float(p.stdout.strip())
    except Exception as e:
        raise RuntimeError("Failed parsing duration: " + str(e))


def _parse_ffmpeg_time(timestr: str) -> float:
    parts = timestr.strip().split(':')
    if len(parts) != 3:
        try:
            return float(timestr)
        except Exception:
            return 0.0
    h = float(parts[0]); m = float(parts[1]); s = float(parts[2])
    return h * 3600 + m * 60 + s


class YTPFFmpegAdaptor:
    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffplay_bin: str = "ffplay", ffprobe_bin: str = "ffprobe", temp_dir: Optional[str] = None):
        self.ffmpeg = ffmpeg_bin
        self.ffplay = ffplay_bin
        self.ffprobe = ffprobe_bin
        self.temp_dir = Path(temp_dir or tempfile.mkdtemp(prefix="freepoop_v4_"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.sources: List[Path] = []
        self.overlays: List[Dict] = []
        self.effects: Dict[str, Any] = {
            "stutter": False, "stutter_ms": 120, "stutter_repeats": 6,
            "scramble": False, "scramble_segments": 8, "reverse": False,
            "pitch_semitones": 0.0
        }
        self.preset_params: Dict[str, Any] = {}
        self.plugin_manager = PluginManager(self) if PluginManager else None
        self._seed = random.getrandbits(32)

    # ------------- compatibility API -------------
    def set_effect(self, name: str, value: Any):
        self.effects[name] = value

    def load_preset(self, preset: Dict[str, Any]):
        if not isinstance(preset, dict):
            return
        self.preset_params.update(preset)
        for k, v in preset.items():
            self.effects[k] = v

    # ------------- sources / overlays -------------
    def add_source(self, path_or_url: str) -> Path:
        if not path_or_url:
            raise ValueError("No path provided")
        if isinstance(path_or_url, str) and (path_or_url.startswith("http://") or path_or_url.startswith("https://")):
            if yt_dlp is None:
                raise RuntimeError("yt-dlp not installed")
            opts = {"outtmpl": str(self.temp_dir / "%(id)s.%(ext)s"), "quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(path_or_url, download=True)
                f = ydl.prepare_filename(info)
                p = Path(f)
                if not p.exists():
                    for ext in ("mp4", "mkv", "webm", "avi"):
                        c = p.with_suffix("." + ext)
                        if c.exists():
                            p = c; break
                if not p.exists():
                    raise RuntimeError("Downloaded file not found")
                self.sources.append(p)
                return p
        else:
            p = Path(path_or_url)
            if not p.exists():
                raise FileNotFoundError("Source not found: " + path_or_url)
            self.sources.append(p)
            return p

    def add_overlay(self, file_path: str, x: str = "(main_w-overlay_w)/2", y: str = "(main_h-overlay_h)/2", start: float = 0.0, duration: Optional[float] = None) -> Dict:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError("Overlay not found: " + file_path)
        ov = {"path": p, "x": x, "y": y, "start": float(start), "duration": duration}
        self.overlays.append(ov)
        return ov

    def prepare_overlay_from_gif(self, gif_path: str, fps: int = 15) -> Path:
        gif = Path(gif_path)
        if not gif.exists():
            raise FileNotFoundError("GIF not found: " + gif_path)
        out = self.temp_dir / (gif.stem + f"_{uuid.uuid4().hex[:8]}.mp4")
        cmd = [self.ffmpeg, "-y", "-i", str(gif), "-r", str(fps), "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(out)]
        p = _safe_run(cmd)
        if p.returncode != 0:
            raise RuntimeError("GIF conversion failed: " + (p.stderr or p.stdout))
        return out

    # ------------- concat helpers -------------
    def _write_concat_list(self, paths: List[Path], listfile: Path):
        # ffmpeg concat demuxer expects lines: file 'path'
        with listfile.open("w", encoding="utf-8") as fh:
            for p in paths:
                # Write absolute path and escape single quotes
                safe = str(p).replace("'", "'\"'\"'")
                fh.write(f"file '{safe}'\n")

    def concat_all(self, output_path: str, reencode: bool = True, overwrite: bool = True) -> subprocess.CompletedProcess:
        if not self.sources:
            raise RuntimeError("No sources to concat")
        listfile = self.temp_dir / (f"concat_{uuid.uuid4().hex[:8]}.txt")
        self._write_concat_list(self.sources, listfile)
        cmd = [self.ffmpeg]
        if overwrite: cmd += ["-y"]
        cmd += ["-f", "concat", "-safe", "0", "-i", str(listfile)]
        if reencode:
            cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", str(output_path)]
        else:
            cmd += ["-c", "copy", str(output_path)]
        p = _safe_run(cmd)
        try:
            listfile.unlink()
        except Exception:
            pass
        return p

    def concat_split(self, output_dir: str, base_name: str = "concat video", per_file: int = 1, reencode: bool = True, overwrite: bool = True) -> List[Dict[str, Any]]:
        if not self.sources:
            raise RuntimeError("No sources to concat")
        outdir = Path(output_dir)
        outdir.mkdir(parents=True, exist_ok=True)
        results = []
        total = len(self.sources)
        i = 0
        part = 1
        while i < total:
            chunk = self.sources[i:i+per_file]
            out_name = f"{base_name} ({part}).mp4"
            out_path = outdir / out_name
            listfile = self.temp_dir / (f"concat_{uuid.uuid4().hex[:8]}.txt")
            self._write_concat_list(chunk, listfile)
            cmd = [self.ffmpeg]
            if overwrite: cmd += ["-y"]
            cmd += ["-f", "concat", "-safe", "0", "-i", str(listfile)]
            if reencode:
                cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", str(out_path)]
            else:
                cmd += ["-c", "copy", str(out_path)]
            p = _safe_run(cmd)
            stderr_text = p.stderr or p.stdout
            results.append({"out": str(out_path), "returncode": p.returncode, "stderr": stderr_text})
            try:
                listfile.unlink()
            except Exception:
                pass
            i += per_file
            part += 1
        return results

    # ------------- robust ffmpeg filter builders (stutter/scramble/pitch) -------------
    def _build_stutter(self, in_v_label: str, in_a_label: str, st_ms: int, repeats: int, source: Path) -> Tuple[str, str, str]:
        D = ffprobe_duration(source, self.ffprobe)
        st_dur = max(0.02, min(st_ms / 1000.0, D))
        default_start = min(1.0, max(0.0, D * 0.1))
        st_start = default_start if (default_start + st_dur <= D) else max(0.0, D - st_dur - 0.01)
        parts = []; vlabels = []; alabels = []
        idx = 0
        def vlab(n): return f"vseg{n}"
        def alab(n): return f"aseg{n}"
        if st_start > 0.001:
            parts.append(f"[{in_v_label}]trim=start=0:duration={st_start},setpts=PTS-STARTPTS[{vlab(idx)}]")
            parts.append(f"[{in_a_label}]atrim=start=0:duration={st_start},asetpts=PTS-STARTPTS[{alab(idx)}]")
            vlabels.append(f"[{vlab(idx)}]"); alabels.append(f"[{alab(idx)}]"); idx += 1
        for _ in range(max(1, repeats)):
            parts.append(f"[{in_v_label}]trim=start={st_start}:duration={st_dur},setpts=PTS-STARTPTS[{vlab(idx)}]")
            parts.append(f"[{in_a_label}]atrim=start={st_start}:duration={st_dur},asetpts=PTS-STARTPTS[{alab(idx)}]")
            vlabels.append(f"[{vlab(idx)}]"); alabels.append(f"[{alab(idx)}]"); idx += 1
        post_start = st_start + st_dur
        if post_start + 0.001 < D:
            parts.append(f"[{in_v_label}]trim=start={post_start}:duration={D-post_start},setpts=PTS-STARTPTS[{vlab(idx)}]")
            parts.append(f"[{in_a_label}]atrim=start={post_start}:duration={D-post_start},asetpts=PTS-STARTPTS[{alab(idx)}]")
            vlabels.append(f"[{vlab(idx)}]"); alabels.append(f"[{alab(idx)}]"); idx += 1
        inter = []
        for i in range(len(vlabels)):
            inter.append(vlabels[i]); inter.append(alabels[i])
        concat = "".join(inter) + f"concat=n={len(vlabels)}:v=1:a=1[st_v][st_a]"
        parts.append(concat)
        return ";".join(parts), "st_v", "st_a"

    def _build_scramble(self, in_v_label: str, in_a_label: str, segments: int, source: Path) -> Tuple[str, str, str]:
        D = ffprobe_duration(source, self.ffprobe)
        segments = max(1, segments)
        seg_dur = max(0.01, D / segments)
        parts = []; vlabels = []; alabels = []
        for i in range(segments):
            start = i * seg_dur
            dur = max(0.01, D - start) if i == segments - 1 else seg_dur
            parts.append(f"[{in_v_label}]trim=start={start}:duration={dur},setpts=PTS-STARTPTS[v_{i}]")
            parts.append(f"[{in_a_label}]atrim=start={start}:duration={dur},asetpts=PTS-STARTPTS[a_{i}]")
            vlabels.append(f"[v_{i}]"); alabels.append(f"[a_{i}]")
        order = list(range(segments))
        rnd = random.Random(self._seed); rnd.shuffle(order)
        inter = []
        for i in order:
            inter.append(vlabels[i]); inter.append(alabels[i])
        concat = "".join(inter) + f"concat=n={segments}:v=1:a=1[scr_v][scr_a]"
        parts.append(concat)
        return ";".join(parts), "scr_v", "scr_a"

    def _build_pitch(self, in_label: str, out_label: str, semitones: float, sr: int = 44100) -> str:
        if abs(semitones) < 1e-6:
            return f"[{in_label}]anull[{out_label}]"
        rate_factor = 2 ** (semitones / 12.0)
        tempo = 1.0 / rate_factor
        atempo_chain = []
        rem = tempo
        while rem < 0.5 or rem > 2.0:
            if rem < 0.5:
                atempo_chain.append(0.5); rem /= 0.5
            else:
                atempo_chain.append(2.0); rem /= 2.0
        atempo_chain.append(rem)
        atempo_str = ",".join([f"atempo={v:.8f}" for v in atempo_chain if abs(v - 1.0) > 1e-9])
        filt = f"[{in_label}]asetrate={int(sr * rate_factor)},aresample={sr}"
        if atempo_str:
            filt += f",{atempo_str}"
        filt += f"[{out_label}]"
        return filt

    def _assemble_filter_complex(self) -> Tuple[str, str, str]:
        if not self.sources:
            raise RuntimeError("No sources")
        parts = []
        cur_v, cur_a = "0:v", "0:a"
        main_src = self.sources[0]
        if self.effects.get("reverse"):
            parts.append(f"[{cur_v}]reverse[v_rev]"); parts.append(f"[{cur_a}]areverse[a_rev]")
            cur_v, cur_a = "v_rev", "a_rev"
        if self.effects.get("stutter"):
            frag, outv, outa = self._build_stutter(cur_v, cur_a, int(self.effects.get("stutter_ms", 120)), int(self.effects.get("stutter_repeats", 6)), main_src)
            parts.append(frag); cur_v, cur_a = outv, outa
        if self.effects.get("scramble"):
            frag, outv, outa = self._build_scramble(cur_v, cur_a, int(self.effects.get("scramble_segments", 8)), main_src)
            parts.append(frag); cur_v, cur_a = outv, outa
        if abs(float(self.effects.get("pitch_semitones", 0.0))) > 1e-6:
            pfrag = self._build_pitch(cur_a, f"{cur_a}_p", float(self.effects.get("pitch_semitones", 0.0)))
            parts.append(pfrag); cur_a = f"{cur_a}_p"
        overlay_chain = f"[{cur_v}]"
        for idx, ov in enumerate(self.overlays, start=1):
            ov_label = f"[{idx}:v]"; out_label = f"ov{idx}"
            x = ov.get("x", "(main_w-overlay_w)/2"); y = ov.get("y", "(main_h-overlay_h)/2")
            enable = ""
            if ov.get("start", 0) and ov.get("start") > 0:
                end = ov.get("start") + (ov.get("duration") or 99999)
                enable = f":enable='between(t,{ov['start']},{end})'"
            parts.append(f"{overlay_chain}{ov_label}overlay=x={x}:y={y}{enable}[{out_label}]")
            overlay_chain = f"[{out_label}]"
        final_v = overlay_chain.strip("[]") if overlay_chain.startswith("[") else overlay_chain
        final_a = cur_a
        fc = ";".join(parts) if parts else ""
        return fc, final_v, final_a

    # ------------- command generation & export -------------
    def generate_command(self, outpath: str, overwrite: bool = True, crf: int = 18, preset: str = "medium") -> List[str]:
        if not self.sources:
            raise RuntimeError("No sources")
        cmd = [self.ffmpeg]
        if overwrite:
            cmd += ["-y"]
        cmd += ["-i", str(self.sources[0])]
        for ov in self.overlays:
            cmd += ["-i", str(ov["path"])]
        fc, vlbl, albl = self._assemble_filter_complex()
        if fc:
            cmd += ["-filter_complex", fc, "-map", f"[{vlbl}]", "-map", f"[{albl}]"]
        else:
            cmd += ["-map", "0:v", "-map", "0:a?"]
        pooped = self.preset_params.get("pooped_transcript")
        if pooped:
            srt = self._write_srt(pooped)
            if srt:
                # best-effort subtitles via -vf; may need more advanced handling for filter_complex chains
                cmd += ["-vf", f"subtitles={str(srt)}"]
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-c:a", "aac", "-b:a", "192k", str(outpath)]
        if self.plugin_manager:
            try:
                self.plugin_manager.run_hook_all("on_before_export", self, cmd)
            except Exception:
                pass
        return cmd

    def _write_srt(self, text: str) -> Optional[Path]:
        lines = [ln.strip() for ln in text.replace("\r", "").split("\n") if ln.strip()]
        if not lines:
            return None
        sents = []
        for ln in lines:
            for s in ln.split("."):
                s = s.strip()
                if s:
                    sents.append(s)
        if not sents:
            sents = lines
        srt = self.temp_dir / (f"poop_{uuid.uuid4().hex[:8]}.srt")
        per = 3.0
        with srt.open("w", encoding="utf-8") as fh:
            for i, s in enumerate(sents, start=1):
                start = (i - 1) * per
                end = start + per
                def fmt(t):
                    h = int(t // 3600); m = int((t % 3600) // 60); ssec = int(t % 60); ms = int((t - int(t)) * 1000)
                    return f"{h:02d}:{m:02d}:{ssec:02d},{ms:03d}"
                fh.write(f"{i}\n{fmt(start)} --> {fmt(end)}\n{s}\n\n")
        return srt

    def export_with_progress(self, outpath: str, progress_callback: Optional[Callable[[Optional[float], Optional[float], str], None]] = None, overwrite: bool = True, crf: int = 18, preset: str = "medium") -> Tuple[int, str]:
        if not self.sources:
            raise RuntimeError("No sources")
        try:
            duration = ffprobe_duration(self.sources[0], self.ffprobe)
        except Exception:
            duration = None
        cmd = self.generate_command(outpath, overwrite=overwrite, crf=crf, preset=preset)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)
        stderr_acc = []
        try:
            while True:
                line = proc.stderr.readline()
                if not line and proc.poll() is not None:
                    break
                if not line:
                    continue
                stderr_acc.append(line)
                if "time=" in line:
                    try:
                        idx = line.find("time=")
                        tail = line[idx + 5:].strip()
                        token = tail.split()[0]
                        tsec = _parse_ffmpeg_time(token)
                        percent = None
                        if duration and duration > 0:
                            percent = min(1.0, max(0.0, tsec / duration))
                        if progress_callback:
                            progress_callback(percent, tsec, line.strip())
                    except Exception:
                        if progress_callback:
                            progress_callback(None, None, line.strip())
                else:
                    if progress_callback:
                        progress_callback(None, None, line.strip())
            rc = proc.wait()
            return rc, "".join(stderr_acc)
        except Exception as e:
            proc.kill()
            return -1, str(e)

    def export(self, outpath: str, **kwargs):
        rc, stderr = self.export_with_progress(outpath, progress_callback=None, **kwargs)
        class R: pass
        r = R(); r.returncode = rc; r.stderr = stderr
        return r

    def preview(self):
        if not self.sources:
            raise RuntimeError("No sources to preview")
        subprocess.Popen([self.ffplay, "-autoexit", "-nodisp", str(self.sources[0])])

    def cleanup(self):
        for p in list(self.temp_dir.iterdir()):
            try:
                p.unlink()
            except Exception:
                pass
        try:
            self.temp_dir.rmdir()
        except Exception:
            pass