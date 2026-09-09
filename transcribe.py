#!/usr/bin/env python
"""Transcribe ONE video to a timestamped .srt subtitle file using Whisper.

Deliberately one video per run -- there is no "do everything" mode.

    python transcribe.py --list     show all videos and which are done
    python transcribe.py 7          transcribe video #7 from that list
    python transcribe.py "some video.mp4"
"""

import os
import site
import sys
import sysconfig


# CUDA DLLs ship inside the nvidia-* pip packages, and Windows will not find them
# on its own. Must happen before faster_whisper is imported or CTranslate2 fails
# with "Library cublas64_12.dll is not found".
def _register_cuda_dlls():
    if not hasattr(os, "add_dll_directory"):
        return
    roots = list(site.getsitepackages())
    purelib = sysconfig.get_paths().get("purelib")
    if purelib and purelib not in roots:
        roots.append(purelib)
    for root in roots:
        for sub in ("cublas", "cudnn", "cuda_nvrtc"):
            path = os.path.join(root, "nvidia", sub, "bin")
            if os.path.isdir(path):
                try:
                    os.add_dll_directory(path)
                except OSError:
                    pass


_register_cuda_dlls()

import argparse
import re
import time
from pathlib import Path

VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv"}


def lower_priority():
    """Drop to below-normal priority so the desktop stays responsive.

    Whisper does heavy CPU work alongside the GPU (video decoding, VAD,
    tokenizing). At normal priority that starves DWM, the Windows compositor,
    and the screen freezes for 10-20 seconds at a time.
    """
    try:
        import ctypes
        below_normal = 0x00004000
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        return bool(ctypes.windll.kernel32.SetPriorityClass(handle, below_normal))
    except Exception:
        return False


def format_timestamp(seconds):
    """Seconds -> SRT's HH:MM:SS,mmm. The comma is required; a period breaks players."""
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def format_duration(seconds):
    """Seconds -> a short human string like '2h 34m 05s'."""
    seconds = int(round(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def find_videos(root):
    """Every video under root, sorted so numbering is stable between runs."""
    videos = [
        p for p in Path(root).rglob("*")
        if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES
    ]
    return sorted(videos, key=lambda p: str(p).lower())


def srt_path_for(video):
    return video.with_suffix(".srt")


def md_path_for(video):
    return video.with_suffix(".md")


def parse_srt(srt_path):
    """Read an .srt back into (start_seconds, text) pairs."""
    pattern = re.compile(r"(\d\d):(\d\d):(\d\d),(\d\d\d)\s*-->")
    cues = []
    raw = Path(srt_path).read_text(encoding="utf-8")
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [ln for ln in block.strip().splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        match = pattern.match(lines[1])
        if not match:
            continue
        h, m, s, ms = (int(g) for g in match.groups())
        cues.append((h * 3600 + m * 60 + s + ms / 1000, " ".join(lines[2:]).strip()))
    return cues


def write_condensed(cues, out_path, title, window=60):
    """Merge 5-second cues into ~1-minute paragraphs, one timestamp each.

    Roughly 40% smaller than the .srt and far easier to read, while keeping
    timestamps precise enough to jump to a demo in the video.
    """
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(f"# {title}\n\n")
        fh.write("Auto-transcribed from the class recording. Timestamps match the\n")
        fh.write("original video -- use them to jump to a demo.\n\n---\n\n")

        block_start = None
        words = []
        for start, text in cues:
            if block_start is None:
                block_start = start
            words.append(text)
            if start - block_start >= window:
                fh.write(f"**[{format_timestamp(block_start)[:8]}]** "
                         f"{' '.join(words)}\n\n")
                block_start, words = None, []
        if words:
            fh.write(f"**[{format_timestamp(block_start)[:8]}]** {' '.join(words)}\n\n")


def print_list(videos, root):
    if not videos:
        print(f"No videos found under {root}")
        return
    done = 0
    width = len(str(len(videos)))
    for i, video in enumerate(videos, 1):
        finished = srt_path_for(video).exists()
        done += finished
        status = "done   " if finished else "pending"
        try:
            label = video.relative_to(root)
        except ValueError:
            label = video
        print(f"[{i:>{width}}] {status}  {label}")
    print(f"\n{done} of {len(videos)} transcribed, {len(videos) - done} pending.")


def resolve_target(target, videos, root):
    """Accept either a list number or a path. Returns a Path or exits."""
    if target.isdigit():
        index = int(target)
        if not 1 <= index <= len(videos):
            sys.exit(f"No video #{index}. There are {len(videos)}. Use --list to see them.")
        return videos[index - 1]

    candidate = Path(target)
    if not candidate.is_absolute():
        candidate = Path(root) / target
    if candidate.is_file():
        return candidate

    # Fall back to a case-insensitive name match so partial names work.
    needle = target.lower()
    matches = [v for v in videos if needle in v.name.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"'{target}' matches {len(matches)} videos:")
        for m in matches[:10]:
            print(f"  {m.name}")
        sys.exit("Be more specific, or use the number from --list.")
    sys.exit(f"Video not found: {target}\nUse --list to see available videos.")


def load_model(args):
    """Load Whisper, falling back to CPU if CUDA is unavailable."""
    from faster_whisper import WhisperModel

    if args.device != "cpu":
        try:
            model = WhisperModel(args.model, device="cuda",
                                 compute_type=args.compute_type,
                                 cpu_threads=args.cpu_threads)
            print(f"Model: {args.model}   device=cuda   compute_type={args.compute_type}"
                  f"   cpu_threads={args.cpu_threads}")
            return model
        except Exception as exc:
            if args.device == "cuda":
                raise
            print("=" * 70)
            print("WARNING: could not use the GPU, falling back to CPU.")
            print(f"Reason: {exc}")
            print("CPU works but is roughly 5-10x slower. Ctrl-C now if that is not what")
            print("you want -- a 2.5 hour video will take several hours on CPU.")
            print("=" * 70)

    model = WhisperModel(args.model, device="cpu", compute_type="int8",
                         cpu_threads=args.cpu_threads)
    print(f"Model: {args.model}   device=cpu   compute_type=int8"
          f"   cpu_threads={args.cpu_threads}")
    return model


def transcribe(video, args):
    out_path = srt_path_for(video)
    if out_path.exists() and not args.overwrite:
        sys.exit(
            f"{out_path.name} already exists.\n"
            "Pass --overwrite to redo it, or pick a different video."
        )

    model = load_model(args)

    print(f"\nTranscribing: {video.name}")
    started = time.monotonic()
    segments, info = model.transcribe(
        str(video),
        language=args.language,
        beam_size=args.beam_size,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    total = info.duration or 0
    speech = getattr(info, "duration_after_vad", None) or total
    print(f"Audio length: {format_duration(total)}"
          f"   speech after silence removal: {format_duration(speech)}")
    print("-" * 70)

    # Write to .tmp and rename at the end, so Ctrl-C never leaves a partial .srt
    # that would look finished on the next --list.
    tmp_path = out_path.with_suffix(".srt.tmp")
    count = 0
    lines = []
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            for segment in segments:
                count += 1
                text = segment.text.strip()
                fh.write(f"{count}\n")
                fh.write(f"{format_timestamp(segment.start)} --> "
                         f"{format_timestamp(segment.end)}\n")
                fh.write(f"{text}\n\n")
                fh.flush()
                lines.append(text)

                pct = (segment.end / total * 100) if total else 0
                elapsed = time.monotonic() - started
                sys.stdout.write(
                    f"\r  {pct:5.1f}%  at {format_timestamp(segment.start)[:8]}"
                    f"  |  {count} lines  |  {format_duration(elapsed)} elapsed   "
                )
                sys.stdout.flush()
    except KeyboardInterrupt:
        tmp_path.unlink(missing_ok=True)
        sys.exit("\n\nStopped. No .srt was written -- run it again to start over.")
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    os.replace(tmp_path, out_path)
    elapsed = time.monotonic() - started

    md_path = md_path_for(video)
    write_condensed(parse_srt(out_path), md_path, video.stem, window=args.window)

    print("\n" + "-" * 70)
    print(f"Done. {count} subtitle lines.")
    if elapsed > 0:
        print(f"Took {format_duration(elapsed)} for {format_duration(total)} of video"
              f"  ({total / elapsed:.1f}x realtime)")
    print(f"Saved: {out_path.name}   (subtitles for VLC)")
    print(f"Saved: {md_path.name}   (condensed, upload this one)")


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe one video to a timestamped .srt file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("target", nargs="?",
                        help="video number (from --list) or filename")
    parser.add_argument("--list", action="store_true",
                        help="show all videos and which already have subtitles")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent),
                        help="folder to search for videos (default: this script's folder)")
    parser.add_argument("--model", default="medium",
                        help="tiny, base, small, medium, large-v3 (default: medium)")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"],
                        help="auto tries the GPU and falls back to CPU (default: auto)")
    parser.add_argument("--compute-type", default="int8_float16",
                        help="GPU quantization (default: int8_float16, fits 4GB VRAM)")
    parser.add_argument("--language", default="en",
                        help="spoken language (default: en)")
    parser.add_argument("--beam-size", type=int, default=5,
                        help="1 is ~2x faster, 5 is more accurate (default: 5)")
    parser.add_argument("--cpu-threads", type=int, default=6,
                        help="CPU threads to use (default: 6, leaves cores free "
                             "so the screen does not freeze)")
    parser.add_argument("--window", type=int, default=60,
                        help="seconds of speech per timestamp in the .md (default: 60)")
    parser.add_argument("--condense", action="store_true",
                        help="rebuild .md files from existing .srt files, no transcribing")
    parser.add_argument("--overwrite", action="store_true",
                        help="redo a video that already has an .srt")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    videos = find_videos(root)

    if args.condense:
        made = 0
        for video in videos:
            srt = srt_path_for(video)
            if srt.exists():
                write_condensed(parse_srt(srt), md_path_for(video), video.stem,
                                window=args.window)
                print(f"Condensed: {md_path_for(video).name}")
                made += 1
        print(f"\n{made} .md file(s) written." if made
              else "\nNo .srt files found to condense.")
        return

    if args.list or not args.target:
        print_list(videos, root)
        if not args.target:
            print("\nRun one with:  python transcribe.py <number>")
        return

    transcribe(resolve_target(args.target, videos, root), args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    lower_priority()
    main()
