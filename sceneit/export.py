import hashlib
import json
import re
import shutil
from pathlib import Path


def project_id(name):
    # Remotion id는 영문·숫자·-만 된다. 한글 이름끼리 같은 id가 되지 않게 이름 해시를 붙인다.
    pid = re.sub(r"[^A-Za-z0-9-]+", "-", name).strip("-")
    if not name.isascii():
        pid = f"{pid or 'p'}-{hashlib.sha1(name.encode()).hexdigest()[:6]}"
    return pid or "project"


def sub_line(i, s):
    text = s["text"]
    label = f"{i + 1} " + re.sub(r"\[\[|\]\]", "", text).replace("\n", " ")[:16]
    f = round(float(s["t0"]) * 30)
    d = max(1, round((float(s["t1"]) - float(s["t0"])) * 30))
    attrs = [
        f"name={json.dumps(label, ensure_ascii=False)}",
        f"from={{{f}}}",
        f"durationInFrames={{{d}}}",
        f"text={{{json.dumps(text, ensure_ascii=False)}}}",
        f'font="{s.get("font", "jua")}"',
        f'enter="{s.get("enter", "fadeInUp")}"',
        f'emph="{s.get("emph", "none")}"',
        f'exit="{s.get("exit", "none")}"',
        f"speed={{{float(s.get('speed', 1))}}}",
        f"y={{{float(s.get('y', 0.8))}}}",
        f"size={{{float(s.get('size', 1))}}}",
        f'fill="{s.get("fill", "#ffffff")}"',
        f'stroke="{s.get("stroke", "#1b1b1b")}"',
        f'hi="{s.get("hi", "#ffd23f")}"',
        f'box="{s.get("box") if s.get("box") in BOXES else "none"}"',
    ]
    return "    <Sub " + " ".join(attrs) + " />"


BOXES = ("none", "black", "yellow", "white")  # studio/src/SubClip.tsx 의 BOX_KEYS 와 같아야 한다


def write_project(studio, pid, video, subs, layout, aspect, duration, frame="blur"):
    studio = Path(studio)
    media = studio / "public" / "media"
    media.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(video, media / f"{pid}.mp4")
    frames = max(1, round(duration * 30))
    body = "\n".join(sub_line(i, s) for i, s in enumerate(subs))
    tsx = f'''import React from "react";
import {{ AbsoluteFill }} from "remotion";
import {{ Frame }} from "../Frame";
import {{ Sub }} from "../SubClip";

export const meta = {{ id: "{pid}", frames: {frames} }};

export const Component: React.FC = () => (
  <AbsoluteFill>
    <Frame src="media/{pid}.mp4" layout="{layout}" aspect={{{aspect:.4f}}} bg="{"black" if frame == "black" else "blur"}" />
{body}
  </AbsoluteFill>
);
'''
    (studio / "src" / "projects" / f"{pid}.tsx").write_text(tsx, encoding="utf-8")
