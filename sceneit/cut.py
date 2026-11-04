import functools
import shutil
import subprocess
from pathlib import Path

from .media import probe

# HDR → SDR 톤매핑. 결과는 항상 8비트 yuv420p + bt709 (브라우저에서 재생되는 형식).
HDR_TO_SDR = "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv"
SDR_TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]


@functools.cache
def has_zscale():
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return " zscale " in out


def target_size(info, layout):
    if layout == "cover":
        return 1080, 1920
    h = round(1080 * info["height"] / info["width"] / 2) * 2
    return 1080, min(h, 1920)


def clamp(cuts, durations):
    fixed = []
    for c in cuts:
        src = int(c.get("src", 0))
        dur = durations[src]
        t0, t1 = float(c["t0"]), float(c["t1"])
        if t1 > dur:
            length = t1 - t0
            t1 = dur
            t0 = max(0.0, dur - length)
        if t1 - t0 >= 0.2:
            fixed.append({**c, "src": src, "t0": round(t0, 2), "t1": round(t1, 2)})
    return fixed


def render_cut(videos, cuts, out, layout):
    infos = [probe(v) for v in videos]
    w, h = target_size(infos[0], layout)
    if layout == "cover":
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,setsar=1"
    else:
        vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1"
    out = Path(out)
    tmp = out.parent / "_segments"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    lines = []
    for i, c in enumerate(cuts):
        src = videos[c["src"]]
        length = c["t1"] - c["t0"]
        seg = tmp / f"{i:03d}.mp4"
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(c["t0"]), "-t", str(length), "-i", str(src)]
        if not infos[c["src"]]["audio"]:
            cmd += ["-f", "lavfi", "-t", str(length), "-i", "anullsrc=r=48000:cl=stereo"]
        seg_vf = vf + ("," + HDR_TO_SDR if infos[c["src"]].get("hdr") and has_zscale() else "") + ",format=yuv420p"
        cmd += ["-vf", seg_vf, "-map", "0:v:0", "-map", "0:a:0" if infos[c["src"]]["audio"] else "1:a:0"]
        cmd += ["-c:v", "libx264", "-crf", "16", "-preset", "medium", *SDR_TAGS, "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", str(seg)]
        subprocess.run(cmd, check=True)
        lines.append(f"file '{seg.name}'")
    (tmp / "list.txt").write_text("\n".join(lines) + "\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-c", "copy", str(out.resolve())], check=True, cwd=tmp)
    shutil.rmtree(tmp)
    return {"width": w, "height": h, "duration": probe(out)["duration"]}
