"""Assembles the self-contained explainer page (fonts embedded) -> out/PAL_explainer.html"""
import base64, os
H = os.path.dirname(os.path.abspath(__file__)); F = os.path.join(H, "node_modules/@fontsource")
def font(fam, path, wt):
    b = base64.b64encode(open(os.path.join(F, path), "rb").read()).decode()
    return f"@font-face{{font-family:'{fam}';font-weight:{wt};font-style:normal;src:url(data:font/woff2;base64,{b}) format('woff2')}}"
fonts = "\n".join([font("Inter", f"inter/files/inter-latin-{w}-normal.woff2", w) for w in (400, 500, 600, 700, 800)] +
                  [font("Source Serif 4", f"source-serif-4/files/source-serif-4-latin-{w}-normal.woff2", w) for w in (400, 600, 700)])
js = "\n".join(open(os.path.join(H, "src", f)).read() for f in ("data.js", "engine.js", "scenes1.js", "scenes2.js", "scenes3.js", "player.js"))
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prove the Empty Lane</title>
<style>{fonts}
:root{{--bg:#0B1117;--fg:#E8EEF2}}
@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{--bg:#0B1117;--fg:#E8EEF2}}}}
:root[data-theme="dark"]{{--bg:#0B1117;--fg:#E8EEF2}}
html,body{{margin:0;padding:0;background:var(--bg);color:var(--fg);font-family:Inter,'DejaVu Sans',sans-serif;overflow:hidden}}
#page{{position:relative;overflow:hidden;background:#0B1117}}
#stage{{position:absolute;width:1280px;height:720px;overflow:hidden;transform-origin:0 0}}
#fade{{position:absolute;inset:0;background:#000;pointer-events:none}}
#sqtop,#sqbot{{position:absolute;left:0;right:0;text-align:center;padding:0 40px;box-sizing:border-box}}
#ctrl{{position:fixed;left:0;right:0;bottom:0;display:flex;gap:10px;align-items:center;padding:10px 16px;background:rgba(11,17,23,.85);font:500 14px Inter,sans-serif;color:#E8EEF2}}
#ctrl button,#ctrl select{{background:#18232E;color:#E8EEF2;border:1px solid #263442;border-radius:8px;padding:6px 12px;font:600 14px Inter,sans-serif}}
#ctrl input{{flex:1}}
</style></head><body>
<div id="page"><div id="sqtop"></div><div id="stage"></div><div id="sqbot"></div><div id="fade"></div></div>
<div id="ctrl"><button id="pp">Pause</button><select id="cut"><option value="full">Full cut</option><option value="social">Social cut</option></select><input id="seek" type="range" min="0" max="1000" value="0"><span id="tm">0.0 s</span></div>
<script>{js}</script></body></html>"""
os.makedirs(os.path.join(H, "out"), exist_ok=True)
open(os.path.join(H, "out", "PAL_explainer.html"), "w").write(html)
print("ok", len(html) // 1024, "kB")
