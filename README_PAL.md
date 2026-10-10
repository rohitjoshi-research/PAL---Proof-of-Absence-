# Explainer video (source)

Deterministic HTML animation (`src/`, one `render(t)` and `window.__seek(t)`), rendered frame by frame with Playwright,
with an original procedural soundtrack. Rendered MP4s are not kept in the repository (size); rebuild them as below.

```
cd video
npm install                                   # fonts (Inter, Source Serif 4), embedded into the page by build.py
pip install playwright numpy pillow && python3 -m playwright install chromium
python3 build.py                              # -> out/PAL_explainer.html (self-contained; ?cut=full|social, ?mode=wide|square)
python3 render.py meta full && python3 render.py meta social          # durations, subtitles (out/*.srt)
./render_all.sh                               # frames at 30 fps: full 16:9, social 1:1, social 16:9
python3 sound.py full && python3 sound.py social                      # out/*.wav
# encode, e.g. full 16:9:
ffmpeg -framerate 30 -i out/frames_full_wide/f%05d.jpg -i out/full.wav -c:v libx264 -profile:v high -crf 17 \
       -pix_fmt yuv420p -c:a aac -b:a 192k -shortest -movflags +faststart out/PAL_explainer_full_16x9.mp4
```

Content rules: every number is from the paper's simulation; headlines are paraphrased from verified news and official
sources (`src/data.js`, listed on the sources card); no logos or brand marks; personal-views and AI-use notes on the end card.
`PAL_explainer_full.srt`, `PAL_explainer_social.srt` and `voiceover_60s.md` are the subtitles and the voice-over script.
