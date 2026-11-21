#!/usr/bin/env python3
"""用两条视频、可选的分段表与 SRT，生成能离线打开的网页对照项目。"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid
from fractions import Fraction
from html import escape


def probe(path, program):
    data = subprocess.check_output([
        program, "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=avg_frame_rate,duration,start_time", "-of", "json", str(path)
    ])
    streams = json.loads(data)["streams"]
    if not streams or streams[0].get("duration", "N/A") == "N/A":
        raise ValueError(f"无法读取视频时长，请先转成带视频时间戳的 MP4：{path}")
    video = streams[0]
    if abs(float(video.get("start_time", 0))) > .002:
        raise ValueError(f"请先将素材的起始时间码归零：{path}")
    duration, fps = float(video["duration"]), float(Fraction(video["avg_frame_rate"]))
    if not math.isfinite(duration) or duration < .04 or not 1 <= fps <= 240:
        raise ValueError(f"视频时长或帧率超出对照台支持的范围：{path}")
    return duration, fps


def read_srt(path, duration):
    time_format = r"(\d+):([0-5]\d):([0-5]\d)[,.](\d{3})"

    def stamp(value):
        match = re.fullmatch(time_format, value.strip())
        if not match:
            raise ValueError(f"SRT 时间码无效：{value}")
        hours, minutes, seconds, ms = map(int, match.groups())
        return ((hours * 60 + minutes) * 60 + seconds) * 1000 + ms

    rows = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        if len(lines) < 2 or "-->" not in lines[0]:
            raise ValueError(f"SRT 字幕缺少时间码或文字：{block[:80]}")
        start, end = map(stamp, lines[0].split("-->"))
        if not 0 <= start < end <= round(duration * 1000) + 1:
            raise ValueError(f"SRT 字幕超出成片时间轴：{lines[0]}")
        rows.append([start, end, "\n".join(lines[1:])])
    return rows


def make_segments(path, ref_end, cut_end, fps, ref_id):
    if path:
        entries = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        if abs(ref_end - cut_end) > .5 / fps:
            raise ValueError("两版时长不同，请用 --segments 指定每段对应区间。")
        end = round(min(ref_end, cut_end), 3)
        entries = [dict(title="全片", a0=0, a1=end, b0=0, b1=end)]
    if not isinstance(entries, list) or not entries:
        raise ValueError("分段表需要至少一行。")
    segments = []
    previous = 0
    for i, item in enumerate(entries, 1):
        a0, a1, b0, b1 = [float(item[key]) for key in ("a0", "a1", "b0", "b1")]
        if not (0 <= a0 < a1 <= ref_end + .001 and previous <= b0 < b1 <= cut_end + .001
                and min(a1-a0, b1-b0) >= .04 - .000001):
            raise ValueError(f"第 {i} 段超出时间轴、重叠或短于 0.04 秒。")
        segments.append(dict(id=f"s{i}", title=item["title"], reference=ref_id,
                             a0=a0, a1=a1, b0=b0, b1=b1, cuts=item.get("cuts", [])))
        previous = b1
    return segments


def build(args):
    bundled = Path("/Applications/kdenlive.app/Contents/MacOS/ffprobe")
    program = args.ffprobe or shutil.which("ffprobe") or (str(bundled) if bundled.is_file() else None)
    if not program:
        raise ValueError("找不到 ffprobe，可用 --ffprobe 指定可执行文件。")
    ref_end, _ = probe(args.reference, program)
    cut_end, fps = probe(args.cut, program)
    token = uuid.uuid4().hex
    reference = dict(id=f"ref-{token}", title=args.reference_title, kind="path",
                     value="./视频/参考原片" + args.reference.suffix.lower())
    cut = dict(id=f"cut-{token}", title=args.cut_title, kind="path",
               value="./视频/成片" + args.cut.suffix.lower())
    segments = make_segments(args.segments, ref_end, cut_end, fps, reference["id"])
    if args.captions:
        cut["cues"] = read_srt(args.captions, cut_end)
    starter = dict(schema=1, title=args.title, storageKey=f"cut-review.{token}", preloaded=True,
                   fps=fps, activeId=segments[0]["id"], versionId=cut["id"], audio=args.audio,
                   speed=1, sync="native", references=[reference], versions=[cut], segments=segments)
    template = Path(__file__).resolve().parents[1] / "assets/cut-compare-studio.html"
    html = template.read_text(encoding="utf-8")
    seed = json.dumps(starter, ensure_ascii=False).replace("<", "\\u003c")
    marker = "/* STARTER_DATA */ null"
    if html.count(marker) != 1:
        raise ValueError("对照台模板缺少项目数据入口。")
    html = html.replace(marker, seed)
    html = html.replace("<title>剪辑对照台</title>", f"<title>{escape(args.title)}</title>")
    target = args.output.resolve()
    if target.exists():
        raise ValueError(f"目录已存在，请选择新的输出目录：{target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        stage = Path(tmp) / "review"
        (stage / "视频").mkdir(parents=True)
        for src, asset in [(args.reference, reference), (args.cut, cut)]:
            dst = stage / asset["value"]
            shutil.copyfile(src, dst)
        (stage / "左右对照.html").write_text(html, encoding="utf-8")
        os.rename(stage, target)
    print(target / "左右对照.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="左栏参考视频")
    parser.add_argument("cut", type=Path, help="右栏成片")
    parser.add_argument("output", type=Path, help="新建的项目目录")
    parser.add_argument("--title", default="参考原片与复刻版")
    parser.add_argument("--reference-title", default="参考原片")
    parser.add_argument("--cut-title", default="复刻版")
    parser.add_argument("--audio", choices=("left", "right", "none"), default="left")
    parser.add_argument("--captions", type=Path, help="以成片时间码计的 UTF-8 SRT")
    parser.add_argument("--segments", type=Path, help="分段映射 JSON")
    parser.add_argument("--ffprobe", help="ffprobe 可执行文件路径")
    try:
        build(parser.parse_args())
    except (OSError, KeyError, ValueError, ZeroDivisionError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"{exc}\n")
