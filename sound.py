"""Original procedural soundtrack (no licensed material): soft pad chords, light pulse, faster ticks during the
headlines, a whoosh at every chapter cut, fade in/out.  python3 sound.py CUT -> out/<cut>.wav"""
import json, os, sys, wave
import numpy as np

H = os.path.dirname(os.path.abspath(__file__)); SR = 48000
cut = sys.argv[1]
meta = json.load(open(os.path.join(H, "out", f"{cut}_cuts.json")))
T = meta["duration"]; n = int(T * SR) + SR // 2
t = np.arange(n) / SR
rng = np.random.default_rng(7)
mix = np.zeros((2, n))

def note(f): return 440.0 * 2 ** ((f - 69) / 12)
# pad: Am - F - C - G, 4 s per chord, three voices + detuned octave, slow attack
prog = [[57, 60, 64], [53, 57, 60], [48, 55, 60], [55, 59, 62]]
seg = 4.0
pad = np.zeros(n)
for k in range(int(T / seg) + 2):
    a, b = int(k * seg * SR), min(n, int((k + 1) * seg * SR + 0.8 * SR))
    if a >= n: break
    tt = t[a:b] - k * seg
    env = np.clip(tt / 1.2, 0, 1) * np.clip((seg + 0.8 - tt) / 1.0, 0, 1)
    for m in prog[k % 4]:
        f = note(m)
        pad[a:b] += env * (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.003 * tt) + 0.25 * np.sin(2 * np.pi * 2 * f * tt)) / 3
pad *= 0.11 * (0.85 + 0.15 * np.sin(2 * np.pi * 0.1 * t))
# light pulse at 88 bpm
pulse = np.zeros(n); bpm = 88; beat = 60 / bpm
for bt in np.arange(0, T, beat):
    a = int(bt * SR); L = int(0.25 * SR)
    if a + L > n: break
    tt = np.arange(L) / SR
    pulse[a:a + L] += np.sin(2 * np.pi * (55 + 40 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 14)
pulse *= 0.10
# ticks: faster (16ths) during the headlines scene, sparse elsewhere
ticks = np.zeros(n)
news = [s for s in meta["scenes"] if s[0] == "news"]
n0, n1 = (news[0][1], news[0][1] + news[0][2]) if news else (0, 0)
for bt in np.arange(0, T, beat / 4):
    inside = n0 <= bt < n1
    if not inside and int(round(bt / (beat / 4))) % 4: continue
    a = int(bt * SR); L = int(0.03 * SR)
    if a + L > n: break
    tt = np.arange(L) / SR
    ticks[a:a + L] += rng.normal(0, 1, L) * np.exp(-tt * 260) * (0.5 if inside else 0.25)
ticks = np.convolve(ticks, [1, -0.9], mode="same") * 0.12
# whoosh at every chapter cut (band-limited noise sweep)
wh = np.zeros(n)
for k, t0, d in meta["scenes"][1:]:
    a = int(max(0, t0 - 0.25) * SR); L = int(0.7 * SR)
    if a + L > n: continue
    tt = np.arange(L) / SR
    noise = rng.normal(0, 1, L)
    sweep = np.cumsum(noise) ; sweep -= np.convolve(sweep, np.ones(400) / 400, mode="same")
    env = np.sin(np.pi * np.clip(tt / 0.7, 0, 1)) ** 2
    wh[a:a + L] += sweep / (np.abs(sweep).max() + 1e-9) * env
wh *= 0.16
x = pad + pulse + ticks + wh
fade = np.clip(t / 1.5, 0, 1) * np.clip((T - t) / 2.0, 0, 1)
x *= fade
mix[0] = x + 0.004 * np.sin(2 * np.pi * 0.07 * t) * pad
mix[1] = np.roll(x, 90)
mix /= np.abs(mix).max() / 0.8
pcm = (mix.T * 32767).astype("<i2")
with wave.open(os.path.join(H, "out", f"{cut}.wav"), "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("wrote", cut, round(T, 1), "s")
