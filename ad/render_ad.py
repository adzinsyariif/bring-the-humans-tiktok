#!/usr/bin/env python3
"""Render the bring-the-humans-03 TikTok ad, frame by frame.

One file does the whole job: it paints 540 still frames with Pillow,
synthesizes the soundtrack with numpy, and hands both to ffmpeg for an
18 second vertical H.264 + AAC master at 1080x1920, 30 fps.

Story order: hook, missions counter, three bounty cards, a points
leaderboard with a stamp, a call to action, and the press-kit referral
card held full-screen to close. The press-kit badge rides on top of
every single frame.

Usage: python3 ad/render_ad.py [output.mp4]
"""

import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- setup

W, H = 1080, 1920
FPS = 30
SECONDS = 18.0
FRAME_COUNT = int(FPS * SECONDS)

HERE = Path(__file__).resolve()
TOOLS = HERE.parents[2] / "humans03-tools"
PRESS = TOOLS / "press" / "make-fun-press-kit"
BADGE_FILE = PRESS / "brand-badge" / "makefun-badge.png"
ENDCARD_FILE = PRESS / "referral-card" / "9x16" / "makefun-card-9x16.png"
INTER_FILE = TOOLS / "fonts" / "Inter-Variable.ttf"
MONO_FILE = TOOLS / "fonts" / "JetBrainsMono-Bold.ttf"

INK = (22, 16, 28)
PAPER = (250, 247, 252)
MAGENTA = (196, 28, 131)
MAGENTA_SOFT = (232, 121, 190)
VIOLET = (96, 62, 168)
CARD_FACE = (38, 29, 52)
CARD_EDGE = (84, 66, 112)
MUTED = (178, 166, 198)
GOLD = (255, 205, 92)


def load_font(path, size, weight=None):
    """Load a font, asking variable fonts for a heavy cut when offered.

    Inter ships two variation axes (optical size, then weight) and the
    setter wants a value for every axis, so pass the largest optical
    size alongside the weight — a lone weight is refused and the font
    quietly stays at its regular 400 cut.
    """
    font = ImageFont.truetype(str(path), size)
    if weight is not None:
        try:
            font.set_variation_by_axes([32, weight])
        except Exception:
            pass
    return font


F_HOOK = load_font(INTER_FILE, 130, 860)
F_HOOK_ACCENT = load_font(INTER_FILE, 148, 900)
F_SUB = load_font(INTER_FILE, 46, 700)
F_LABEL = load_font(INTER_FILE, 44, 700)
F_COUNT = load_font(MONO_FILE, 300)
F_CARD_TITLE = load_font(INTER_FILE, 62, 800)
F_CHIP = load_font(INTER_FILE, 38, 800)
F_HEAD = load_font(INTER_FILE, 42, 800)
F_ROW = load_font(INTER_FILE, 58, 750)
F_ROW_NUM = load_font(MONO_FILE, 58)
F_STAMP = load_font(INTER_FILE, 54, 900)
F_CTA = load_font(INTER_FILE, 122, 880)
F_BODY = load_font(INTER_FILE, 50, 600)
F_FINE = load_font(INTER_FILE, 44, 650)

# ------------------------------------------------------------- easing

def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def ease_out(x):
    x = clamp01(x)
    return 1.0 - (1.0 - x) ** 3


def ease_back(x):
    x = clamp01(x)
    c = 1.70158
    return 1.0 + (c + 1.0) * (x - 1.0) ** 3 + c * (x - 1.0) ** 2


def window(t, start, dur):
    """Progress of an entrance that begins at `start`, lasts `dur`."""
    return clamp01((t - start) / dur)


def blend(a, b, k):
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(3))


# -------------------------------------------------------------- stage

def build_stage():
    """A static vertical gradient with a soft vignette, painted once."""
    top = np.array([30, 20, 44], dtype=np.float32)
    bottom = np.array([12, 8, 20], dtype=np.float32)
    ramp = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None, None]
    plane = top[None, None, :] * (1.0 - ramp) + bottom[None, None, :] * ramp
    plane = np.repeat(plane, W, axis=1)
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
    shade = (1.0 - 0.35 * np.clip(dist - 0.35, 0.0, 1.0) ** 2)[..., None]
    img = Image.fromarray((plane * shade).astype(np.uint8), "RGB")
    return img


def build_glow(colour, radius):
    """A radial glow sprite used as drifting stage light."""
    size = radius * 2
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2) / radius
    alpha = (np.clip(1.0 - d, 0.0, 1.0) ** 2 * 120).astype(np.uint8)
    sprite = np.zeros((size, size, 4), dtype=np.uint8)
    sprite[..., 0], sprite[..., 1], sprite[..., 2] = colour
    sprite[..., 3] = alpha
    return Image.fromarray(sprite, "RGBA")


STAGE = build_stage()
GLOW_A = build_glow(MAGENTA, 430)
GLOW_B = build_glow(VIOLET, 520)

BADGE_SRC = Image.open(BADGE_FILE).convert("RGBA")
BADGE = BADGE_SRC.resize((492, 191), Image.LANCZOS)
BADGE_POS = ((W - 492) // 2, 58)

ENDCARD = Image.open(ENDCARD_FILE).convert("RGB").resize((W, H), Image.LANCZOS)


def fresh_frame(t):
    """Stage plus two slow-drifting glows, ready for a scene to draw on."""
    img = STAGE.copy()
    ax = int(W * 0.22 + 90 * math.sin(t * 0.35))
    ay = int(H * 0.20 + 70 * math.cos(t * 0.27))
    img.paste(GLOW_A, (ax - 430, ay - 430), GLOW_A)
    bx = int(W * 0.78 + 110 * math.cos(t * 0.22))
    by = int(H * 0.74 + 80 * math.sin(t * 0.31))
    img.paste(GLOW_B, (bx - 520, by - 520), GLOW_B)
    return img


def stamp_badge(img):
    img.paste(BADGE, BADGE_POS, BADGE)


# --------------------------------------------------------- text utils

def text_w(draw, s, font):
    box = draw.textbbox((0, 0), s, font=font)
    return box[2] - box[0]


def centred(draw, cx, y, s, font, fill, stroke=0, stroke_fill=None):
    box = draw.textbbox((0, 0), s, font=font)
    x = cx - (box[2] - box[0]) / 2 - box[0]
    draw.text((x, y - box[1]), s, font=font, fill=fill,
              stroke_width=stroke, stroke_fill=stroke_fill or fill)
    return box[3] - box[1]


def wrap(draw, s, font, max_w):
    words, lines, cur = s.split(), [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_w(draw, trial, font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fade_layer(base, painter, alpha):
    """Run `painter` on a transparent layer and lay it over `base`.

    Returns the composited frame; `alpha` scales the whole layer so a
    scene can fade in or out as one piece.
    """
    if alpha <= 0.0:
        return base
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    painter(ImageDraw.Draw(layer))
    if alpha < 1.0:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


# -------------------------------------------------------------- scenes
#
# Timeline (seconds): hook 0.0 | counter 3.6 | cards 6.8 | board 10.8
#                     cta 14.4 | end card 16.2 | close 18.0

def rgba(colour, alpha):
    return (colour[0], colour[1], colour[2], int(255 * clamp01(alpha)))


def scene_alpha(t, start, end):
    """Fade in over 0.25 s, fade out over the last 0.2 s of a scene."""
    return min(window(t, start, 0.25), 1.0 - window(t, end - 0.2, 0.2))


def draw_hook(draw, t):
    lines = [
        ("MY AI AGENT", F_HOOK, PAPER, 0.15, 520),
        ("HUNTS REAL", F_HOOK, PAPER, 0.55, 706),
        ("BOUNTIES", F_HOOK_ACCENT, MAGENTA_SOFT, 0.95, 906),
    ]
    for s, font, colour, start, y in lines:
        p = ease_out(window(t, start, 0.45))
        centred(draw, W // 2, y + int((1 - p) * 70), s, font, rgba(colour, p))
    p = ease_out(window(t, 1.55, 0.4))
    if p > 0:
        label = "LIVE ON MAKE.FUN"
        w = text_w(draw, label, F_SUB) + 92
        x0, y0 = (W - w) // 2, 1176 + int((1 - p) * 40)
        draw.rounded_rectangle([x0, y0, x0 + w, y0 + 84], 42,
                               outline=rgba(MAGENTA_SOFT, p), width=3)
        draw.ellipse([x0 + 34, y0 + 33, x0 + 52, y0 + 51],
                     fill=rgba(GOLD, p))
        draw.text((x0 + 68, y0 + 16), label, font=F_SUB,
                  fill=rgba(PAPER, p))


def draw_counter(draw, t):
    centred(draw, W // 2, 596, "MISSIONS CLEARED", F_LABEL, rgba(MUTED, 1.0))
    draw.rounded_rectangle([130, 692, W - 130, 1032], 170,
                           fill=rgba(CARD_FACE, 1.0),
                           outline=rgba(MAGENTA, 1.0), width=6)
    value = int(round(128 * ease_out(window(t, 3.95, 2.05))))
    centred(draw, W // 2, 726, str(value), F_COUNT, rgba(PAPER, 1.0))
    p = ease_out(window(t, 4.3, 0.5))
    draw.line([330, 1128, W - 330, 1128], fill=rgba(MAGENTA_SOFT, p), width=5)


CARDS = [
    ("BEST STEALTH GAME", "DIFFICULTY: EXPERT"),
    ("COVER ART CHALLENGE", "DIFFICULTY: HARD"),
    ("BUG BOUNTY", "DIFFICULTY: BRUTAL"),
]


def draw_cards(draw, t):
    top, card_h, gap = 452, 252, 46
    for i, (title, tag) in enumerate(CARDS):
        p = ease_out(window(t, 6.95 + i * 0.28, 0.5))
        if p <= 0:
            continue
        shift = int((1 - p) * 110)
        y0 = top + i * (card_h + gap)
        x0, x1 = 84 + shift, 996 + shift
        draw.rounded_rectangle([x0, y0, x1, y0 + card_h], 36,
                               fill=rgba(CARD_FACE, p),
                               outline=rgba(CARD_EDGE, p), width=2)
        draw.rounded_rectangle([x0 + 26, y0 + 30, x0 + 40, y0 + card_h - 30],
                               7, fill=rgba(MAGENTA, p))
        draw.text((x0 + 72, y0 + 44), title, font=F_CARD_TITLE,
                  fill=rgba(PAPER, p))
        chip_w = text_w(draw, tag, F_CHIP) + 48
        cy = y0 + 148
        draw.rounded_rectangle([x0 + 72, cy, x0 + 72 + chip_w, cy + 62], 31,
                               outline=rgba(GOLD, p), width=3)
        draw.text((x0 + 96, cy + 9), tag, font=F_CHIP, fill=rgba(GOLD, p))


ROWS = [
    ("AGENT NOVA", "2,340", False),
    ("PIP", "1,875", False),
    ("ZYNN", "1,250", True),
]


def draw_board(draw, t):
    draw.rounded_rectangle([84, 420, 996, 1336], 40,
                           fill=rgba((30, 23, 44), 1.0),
                           outline=rgba(CARD_EDGE, 1.0), width=2)
    draw.text((140, 492), "AGENT", font=F_HEAD, fill=rgba(MUTED, 1.0))
    pw = text_w(draw, "POINTS", F_HEAD)
    draw.text((940 - pw, 492), "POINTS", font=F_HEAD, fill=rgba(MUTED, 1.0))
    draw.line([140, 584, 940, 584], fill=rgba(CARD_EDGE, 1.0), width=2)
    for i, (name, score, hot) in enumerate(ROWS):
        p = ease_out(window(t, 11.05 + i * 0.22, 0.4))
        if p <= 0:
            continue
        ry = 636 + i * 196
        if hot:
            draw.rounded_rectangle([116, ry - 20, 964, ry + 138], 26,
                                   fill=rgba(MAGENTA, p))
        draw.text((140, ry + 22), name, font=F_ROW,
                  fill=rgba(PAPER, p))
        sw = text_w(draw, score, F_ROW_NUM)
        draw.text((940 - sw, ry + 22), score, font=F_ROW_NUM,
                  fill=rgba(PAPER if hot else MUTED, p))


def stamp_tile():
    tile = Image.new("RGBA", (700, 210), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.rounded_rectangle([10, 10, 690, 200], 28,
                        outline=MAGENTA_SOFT + (255,), width=8)
    centred(d, 350, 62, "TOP OF THE BOARD", F_STAMP, MAGENTA_SOFT + (255,))
    return tile.rotate(-12, expand=True, resample=Image.BICUBIC)


STAMP = stamp_tile()


def paste_stamp(img, t):
    p = window(t, 12.55, 0.35)
    if p <= 0:
        return img
    scale = 1.55 - 0.55 * ease_back(p)
    tile = STAMP.resize((int(STAMP.width * scale), int(STAMP.height * scale)),
                        Image.BICUBIC)
    if p < 1.0:
        tile.putalpha(tile.getchannel("A").point(lambda v: int(v * p)))
    cx, cy = 660, 1308
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(tile, (cx - tile.width // 2, cy - tile.height // 2), tile)
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def draw_cta(draw, t):
    p1 = ease_out(window(t, 14.55, 0.45))
    centred(draw, W // 2, 520 + int((1 - p1) * 60), "BRING YOUR",
            F_CTA, rgba(PAPER, p1))
    centred(draw, W // 2, 690 + int((1 - p1) * 60), "AGENT.",
            F_CTA, rgba(MAGENTA_SOFT, p1))
    p2 = ease_out(window(t, 15.0, 0.45))
    if p2 > 0:
        lines = wrap(draw, "Enter it in live challenges where AI agents "
                           "battle head to head.", F_BODY, 850)
        y = 990
        for line in lines:
            centred(draw, W // 2, y, line, F_BODY, rgba(PAPER, p2))
            y += 70
    p3 = ease_out(window(t, 15.35, 0.45))
    if p3 > 0:
        centred(draw, W // 2, 1300, "Free to enter · New bounties every week",
                F_FINE, rgba(GOLD, p3))


SCENES = [
    (0.0, 3.6, draw_hook),
    (3.6, 6.8, draw_counter),
    (6.8, 10.8, draw_cards),
    (10.8, 14.4, draw_board),
    (14.4, 16.2, draw_cta),
]


def compose(t):
    """Build the frame for time `t`, badge included, end card last."""
    if t >= 16.2:
        k = ease_out(window(t, 16.2, 0.3))
        img = Image.blend(fresh_frame(t), ENDCARD, k) if k < 1.0 \
            else ENDCARD.copy()
        stamp_badge(img)
        return img
    img = fresh_frame(t)
    for start, end, painter in SCENES:
        if start <= t < end:
            img = fade_layer(img, lambda d: painter(d, t),
                             scene_alpha(t, start, end))
            if painter is draw_board:
                img = paste_stamp(img, t)
            break
    stamp_badge(img)
    return img


# -------------------------------------------------------------- audio
#
# A small synthwave loop written from oscillators: four chords of pad,
# a pulsing root bass, a quiet arpeggio, and soft key clicks while the
# closing card is on screen. Everything is generated, nothing sampled.

SR = 44100
CHORD_SPAN = SECONDS / 4.0
PROGRESSION = [
    (33, [57, 60, 64, 69]),   # A minor
    (29, [53, 57, 60, 65]),   # F major
    (36, [55, 60, 64, 67]),   # C major
    (31, [55, 59, 62, 67]),   # G major
]


def freq(midi):
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def saw(phase):
    return 2.0 * (phase - np.floor(phase + 0.5))


def pad_chord(midi_notes, seconds):
    n = int(SR * seconds)
    tt = np.arange(n) / SR
    out = np.zeros(n)
    for note in midi_notes:
        f = freq(note)
        out += saw(f * 1.003 * tt) + saw(f * 0.997 * tt)
        out += 0.4 * np.sin(2 * np.pi * f * tt)
    kernel = np.ones(48) / 48.0
    out = np.convolve(out, kernel, mode="same")
    env = np.ones(n)
    atk = int(SR * 0.5)
    rel = int(SR * 0.6)
    env[:atk] = np.linspace(0.0, 1.0, atk) ** 2
    env[-rel:] = np.linspace(1.0, 0.0, rel) ** 2
    return out * env * 0.05


def bass_line(root_midi, seconds):
    n = int(SR * seconds)
    out = np.zeros(n)
    step = 0.75
    pulse = int(SR * 0.5)
    tt = np.arange(pulse) / SR
    f = freq(root_midi)
    wave = (np.sin(2 * np.pi * f * tt)
            + 0.35 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt * 5.0)
    pos = 0.0
    while pos < seconds - 0.1:
        i = int(pos * SR)
        out[i:i + pulse] += wave[:max(0, min(pulse, n - i))]
        pos += step
    return out * 0.30


def arpeggio(midi_notes, seconds):
    n = int(SR * seconds)
    out = np.zeros(n)
    step = CHORD_SPAN / 16.0
    plen = int(SR * 0.22)
    tt = np.arange(plen) / SR
    order = [0, 1, 2, 3, 2, 1]
    for k in range(16):
        note = midi_notes[order[k % len(order)]] + 12
        tri = 2.0 * np.abs(saw(freq(note) * tt)) - 1.0
        pluck = tri * np.exp(-tt * 14.0)
        i = int(k * step * SR)
        out[i:i + plen] += pluck[:max(0, min(plen, n - i))]
    return out * 0.055


def key_clicks(total):
    """Short filtered noise taps, clustered in the end-card segment."""
    out = np.zeros(total)
    rng = np.random.default_rng(20261122)
    burst = int(SR * 0.016)
    tt = np.arange(burst) / SR
    pos = 16.12
    while pos < 17.4:
        click = rng.standard_normal(burst) * np.exp(-tt * 260.0)
        click += 0.5 * np.sin(2 * np.pi * 1900 * tt) * np.exp(-tt * 300.0)
        i = int(pos * SR)
        out[i:i + burst] += click[:max(0, min(burst, total - i))] * 0.5
        pos += float(rng.uniform(0.07, 0.17))
    return out


def build_track():
    n = int(SR * SECONDS)
    mix = np.zeros(n)
    span = int(SR * CHORD_SPAN)
    for idx, (root, notes) in enumerate(PROGRESSION):
        seg = slice(idx * span, (idx + 1) * span)
        mix[seg] += pad_chord(notes, CHORD_SPAN)
        mix[seg] += bass_line(root, CHORD_SPAN)
        mix[seg] += arpeggio(notes, CHORD_SPAN)
    mix += key_clicks(n)
    mix = np.tanh(mix * 1.15)
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.88
    fade_in = int(SR * 0.04)
    fade_out = int(SR * 0.5)
    mix[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
    mix[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)
    return (mix * 32767).astype(np.int16)


def write_wav(path, samples):
    import wave
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(samples.tobytes())


# --------------------------------------------------------------- main

def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        HERE.parents[2] / "humans03-reauth-out.mp4"
    wav_path = out.with_suffix(".wav")
    write_wav(wav_path, build_track())

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:",
        "-i", str(wav_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for i in range(FRAME_COUNT):
        frame = compose(i / FPS)
        proc.stdin.write(frame.tobytes())
        if i % 90 == 0:
            print(f"frame {i}/{FRAME_COUNT}", flush=True)
    proc.stdin.close()
    rc = proc.wait()
    wav_path.unlink(missing_ok=True)
    if rc != 0:
        raise SystemExit(f"ffmpeg exited with {rc}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
