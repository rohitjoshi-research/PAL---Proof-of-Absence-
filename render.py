"""Frame renderer for the explainer page (deterministic __seek, no screen recording).
  python3 render.py sheet  CUT MODE TIMES...      -> out/sheet_<cut>_<mode>.png (contact sheet of the given times)
  python3 render.py frames CUT MODE START END     -> out/frames_<cut>_<mode>/f%05d.jpg for frame indices [START, END)
  python3 render.py meta   CUT                    -> prints duration; writes out/<cut>.srt and out/<cut>_cuts.json
"""
import json, os, sys
from playwright.sync_api import sync_playwright

H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(H, "out"); FPS = 30
URL = "file://" + os.path.join(OUT, "PAL_explainer.html")


def page_for(p, cut, mode, scale=None):
    b = p.chromium.launch()
    if mode == "square":
        pg = b.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=scale or 1)
    else:
        pg = b.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=scale or 1.5)
    pg.goto(f"{URL}?render&cut={cut}&mode={mode}")
    pg.wait_for_function("document.fonts.status === 'loaded'")
    return b, pg


def srt_time(t):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


if __name__ == "__main__":
    what, cut, mode = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "wide")
    with sync_playwright() as p:
        if what == "sheet":
            from PIL import Image
            times = [float(x) for x in sys.argv[4:]]
            b, pg = page_for(p, cut, mode, scale=1)
            ims = []
            for t in times:
                pg.evaluate(f"__seek({t})"); path = os.path.join(OUT, "_tmp.png"); pg.screenshot(path=path); ims.append(Image.open(path).copy())
            w, h = ims[0].size; cols = 3; rows = (len(ims) + cols - 1) // cols
            sheet = Image.new("RGB", (w * cols // 2, h * rows // 2), "white")
            for i, im in enumerate(ims):
                sheet.paste(im.resize((w // 2, h // 2)), ((i % cols) * w // 2, (i // cols) * h // 2))
            sheet.save(os.path.join(OUT, f"sheet_{cut}_{mode}.png")); b.close()
        elif what == "frames":
            a, z = int(sys.argv[4]), int(sys.argv[5])
            d = os.path.join(OUT, f"frames_{cut}_{mode}"); os.makedirs(d, exist_ok=True)
            b, pg = page_for(p, cut, mode)
            for i in range(a, z):
                pg.evaluate(f"__seek({i / FPS})")
                pg.screenshot(path=os.path.join(d, f"f{i:05d}.jpg"), type="jpeg", quality=93)
            b.close()
        elif what == "meta":
            b, pg = page_for(p, cut, "wide", scale=1)
            T = pg.evaluate("__duration()"); print("duration", T)
            caps, prev, start = [], None, 0.0
            n = int(T * 10) + 1
            for i in range(n + 1):
                t = min(i / 10, T); c = pg.evaluate(f"__caption({t})") if i < n else None
                if c != prev:
                    if prev: caps.append((start, t, prev))
                    prev, start = c, t
            with open(os.path.join(OUT, f"{cut}.srt"), "w") as f:
                for k, (a_, z_, c) in enumerate(caps, 1):
                    c = c.replace("&amp;", "&")
                    f.write(f"{k}\n{srt_time(a_)} --> {srt_time(z_)}\n{c}\n\n")
            chips = pg.evaluate("(() => { const tl = timeline(CUT); return tl.map(e => [e.k, e.t0, e.dur]); })()")
            json.dump({"duration": T, "scenes": chips}, open(os.path.join(OUT, f"{cut}_cuts.json"), "w"), indent=1)
            b.close()
