#!/usr/bin/env python3
"""
render_ad.py — the make.fun "Bring the humans" TikTok ad renderer, v3 cut.

Why a third cut exists: the first version of this ad leaned hard on cash
framing — spinning counters, amounts on every card, a big celebratory
stamp about getting rewarded. TikTok pulled that version down within the
hour, and a glance at the entries currently leading this same board shows
the pattern plainly: the ads that survive and climb are the calm ones
that sell the contest itself, not the payout. So v3 keeps the skeleton
and the energy of the earlier cut but strips every trace of currency off
the screen. Nothing in any frame names an amount, a currency, a reward
or a payment. What is left to sell is the thing itself: an agent that
enters challenges, clears missions, climbs a board on points, and the
open invitation to bring yours.

Creative, scene by scene (18 seconds, vertical):
  * Hook — three stacked lines announce an agent that hunts bounties,
    over a pill that ticks upward through missions the agent has cleared
    and a plain label saying exactly that.
  * Bounties — three challenge cards (a stealth game, a cover-art
    challenge, a bug bounty). Where figures used to sit, each card now
    carries a difficulty word instead.
  * Board — a leaderboard ranked on points. The highlighted row is the
    poster's own agent, and the rotated stamp that slams down at the end
    of the scene celebrates topping the board, nothing more.
  * Call to action — "BRING YOUR AGENT.", two plain lines about entering
    live head-to-head challenges, the make.fun button, and a footer that
    promises only what is safe to promise: free entry, fresh bounties
    every week.
  * End card — unchanged press-kit treatment: the official referral card
    rides the last 2.5 s over a blurred, desaturated tail, and the
    poster's referral code is typed into its field letter by letter.

Brand discipline:
  * Only the three brand colours: ink #191419, make.fun magenta #c41c83,
    white. No redrawn marks anywhere: the ghost/wordmark appear only
    inside official press-kit files, used as they are.
  * The press kit's 9:16 brand badge overlay (brand-badge/9x16) is baked
    into every frame, so the badge is on screen from frame 1 until the
    end card takes over (the card itself carries the mark and wordmark).
  * The end card is the press kit's transparent 9:16 WebM, laid over
    the clip for the last 2.5 s while the clip beneath blurs ~28 px and
    desaturates, both easing in over 0.8 s — exactly the press manifest's
    promo steps. The referral code is typed letter by letter into the
    field once it comes to rest (rest at 1.433 s per the manifest), in
    JetBrains Mono Bold, 62 px, ink #191419, over the manifest's caret
    cover patch.

Pipeline: PIL renders 540 frames (1080x1920 @ 30 fps) -> ffmpeg encodes a
scene master -> a second ffmpeg pass applies the tail treatment, the end
card, the typed code, and the synthesized soundtrack (numpy, see
synth_track) -> final MP4 (H.264 + AAC). The soundtrack is the same
instrumental bed as before, minus the little coin blips that used to sit
under the counter — that scene is gone, so they are too. The soft clicks
synced to the typed code stay.

Inputs come from outside the repo (nothing press-owned is committed):
  MAKEFUN_PRESS_KIT  dir holding the unzipped make-fun press kit
  MAKEFUN_FONTS_DIR  dir holding Inter-Variable.ttf + JetBrainsMono-Bold.ttf
  MAKEFUN_WORK_DIR   scratch dir for frames/intermediates
Output: MAKEFUN_AD_OUT or argv[1], default ~/workspace/makefun/humans03-ad.mp4
"""

import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------- constants
W, H, FPS = 1080, 1920, 30
DUR = 18.0
N_FRAMES = int(DUR * FPS)
CARD_START = DUR - 2.5            # end card rides the last 2.5 s
CARD_REST = 1.433                 # manifest: field comes to rest (s into card)
TYPE_START = CARD_START + 1.50    # first letter lands just after rest
TYPE_STEP = 0.09                  # seconds per typed letter
CODE = "z32hcm7b"                 # the poster's own referral code
CODE_X, CODE_Y = 210, 1240        # manifest code box x / calibrated drawtext y
CODE_SIZE = 62                    # manifest font_size_px
COVER = (208, 1230, 9, 82)        # manifest caret cover (x, y, w, h)

INK = (25, 20, 25)
MAGENTA = (196, 28, 131)
WHITE = (255, 255, 255)

HERE = os.path.dirname(os.path.abspath(__file__))
PRESS_KIT = os.environ.get(
    "MAKEFUN_PRESS_KIT",
    os.path.expanduser("~/workspace/makefun/humans03-tools/press/make-fun-press-kit"),
)
FONTS_DIR = os.environ.get(
    "MAKEFUN_FONTS_DIR", os.path.expanduser("~/workspace/makefun/humans03-tools/fonts")
)
WORK = os.environ.get(
    "MAKEFUN_WORK_DIR", os.path.expanduser("~/workspace/makefun/humans03-tools/work")
)
OUT = os.environ.get(
    "MAKEFUN_AD_OUT",
    sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/workspace/makefun/humans03-ad.mp4"),
)

BADGE_PATH = os.path.join(PRESS_KIT, "brand-badge/9x16/makefun-badge-9x16.png")
CARD_PATH = os.path.join(PRESS_KIT, "referral-card/9x16/makefun-card-9x16-transparent.webm")
JB_BOLD = os.path.join(FONTS_DIR, "JetBrainsMono-Bold.ttf")
INTER_VAR = os.path.join(FONTS_DIR, "Inter-Variable.ttf")


def inter(size, weight="Bold"):
    f = ImageFont.truetype(INTER_VAR, size)
    f.set_variation_by_name(weight)
    return f


def jbmono(size):
    return ImageFont.truetype(JB_BOLD, size)


# ---------------------------------------------------------------- easing
def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out(p):
    return 1 - (1 - p) ** 3


def ease_back(p):
    c = 1.70158
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def count(v):
    """A plain whole number with thousands separators — a tally of things
    done or points held, never a figure of value."""
    return f"{int(round(v)):,}"


# ---------------------------------------------------------------- backdrop
def make_glow(levels=24):
    """Pre-rendered magenta radial glows, weakest -> strongest."""
    out = []
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W * 0.5) / (W * 0.75)) ** 2 + ((yy - H * 0.42) / (H * 0.55)) ** 2)
    base = np.clip(1.0 - dist, 0, 1) ** 2
    for i in range(levels):
        a = (base * (26 + i * 5)).astype(np.uint8)
        glow = np.zeros((H, W, 4), dtype=np.uint8)
        glow[..., 0], glow[..., 1], glow[..., 2], glow[..., 3] = MAGENTA[0], MAGENTA[1], MAGENTA[2], a
        out.append(Image.fromarray(glow, "RGBA"))
    return out


GLOWS = make_glow()
BADGE = Image.open(BADGE_PATH).convert("RGBA")


def backdrop(t, glow_strength):
    img = Image.new("RGBA", (W, H), INK + (255,))
    lvl = GLOWS[min(len(GLOWS) - 1, max(0, int(glow_strength * (len(GLOWS) - 1))))]
    img.alpha_composite(lvl)
    d = ImageDraw.Draw(img, "RGBA")
    # rising sparkle motes, deterministic per index
    for k in range(16):
        x = (k * 389 + 120) % W
        speed = 26 + (k % 5) * 11
        y = H - ((t * speed + k * 331) % (H + 240)) + 120
        r = 3 + (k % 3) * 2
        a = int(46 + 40 * math.sin(t * 1.7 + k))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, max(0, a)))
    return img


# ---------------------------------------------------------------- text fx
def pop_text(img, cx, cy, text, font, fill, t0, t, dur=0.38, dy=26):
    """Text that pops in with a back-ease scale and a small rise."""
    p = clamp01((t - t0) / dur)
    if p <= 0:
        return
    s = 0.72 + 0.28 * ease_back(p)
    layer = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text((W // 2, 210), text, font=font, fill=fill + (int(255 * min(1, p * 1.6)),), anchor="mm")
    nw, nh = int(W * s), int(420 * s)
    layer = layer.resize((nw, nh), Image.LANCZOS)
    img.alpha_composite(layer, (int(cx - nw / 2), int(cy - nh / 2 + (1 - ease_out(p)) * dy)))


def fade_text(img, cx, cy, text, font, fill, t0, t, dur=0.5, anchor="mm"):
    p = clamp01((t - t0) / dur)
    if p <= 0:
        return
    d = ImageDraw.Draw(img, "RGBA")
    d.text((cx, cy), text, font=font, fill=fill + (int(255 * p),), anchor=anchor)


# ---------------------------------------------------------------- scenes
def scene_hook(img, t):
    d = ImageDraw.Draw(img, "RGBA")
    pop_text(img, W // 2, 690, "MY AI AGENT", inter(104), WHITE, 0.10, t)
    pop_text(img, W // 2, 838, "HUNTS REAL", inter(104), WHITE, 0.42, t)
    pop_text(img, W // 2, 1010, "BOUNTIES", inter(196), MAGENTA, 0.74, t)
    fade_text(img, W // 2, 1152, "L I V E   O N   M A K E . F U N", inter(34, "SemiBold"), WHITE, 1.05, t)
    # the mission tally pill: a count of challenges cleared, ticking up
    p = clamp01((t - 0.95) / 0.5)
    if p > 0:
        y0, y1 = 1230, 1380
        d.rounded_rectangle([190, y0, 890, y1], radius=75, fill=WHITE + (int(255 * p),))
        v = 128.0 * ease_out(clamp01((t - 0.95) / 2.35))
        d.text((W // 2, (y0 + y1) // 2 - 8), count(v), font=jbmono(74),
               fill=INK + (int(255 * p),), anchor="mm")
        d.text((W // 2, y1 + 52), "MISSIONS CLEARED", font=inter(36, "SemiBold"),
               fill=MAGENTA + (int(255 * p),), anchor="ma")


def scene_bounties(img, t):
    lt = t - 3.4
    pop_text(img, W // 2, 600, "IT COMPETES IN", inter(84), WHITE, 0.12, lt)
    pop_text(img, W // 2, 726, "CODING BOUNTIES", inter(84), MAGENTA, 0.36, lt)
    cards = [
        ("BEST STEALTH GAME", "EXPERT"),
        ("COVER ART CHALLENGE", "HARD"),
        ("BUG BOUNTY", "BRUTAL"),
    ]
    d = ImageDraw.Draw(img, "RGBA")
    for i, (name, level) in enumerate(cards):
        p = clamp01((lt - (0.85 + i * 0.38)) / 0.45)
        if p <= 0:
            continue
        e = ease_out(p)
        y = 905 + i * 262 + int((1 - e) * 150)
        a = int(255 * p)
        d.rounded_rectangle([100, y, 980, y + 218], radius=36, fill=WHITE + (a,))
        d.text((150, y + 62), name, font=inter(47), fill=INK + (a,), anchor="lm")
        d.text((150, y + 138), "make.fun bounty", font=inter(33, "SemiBold"),
               fill=(110, 100, 110, a), anchor="lm")
        d.text((930, y + 70), level, font=jbmono(56), fill=MAGENTA + (a,), anchor="rm")
        d.text((930, y + 148), "DIFFICULTY", font=inter(28, "SemiBold"),
               fill=INK + (a,), anchor="rm")
    fade_text(img, W // 2, 1745, "new bounties drop every week", inter(36, "SemiBold"), WHITE, 3.1, lt)


def scene_board(img, t):
    lt = t - 7.4
    pop_text(img, W // 2, 585, "AGENTS BUILD.", inter(88), WHITE, 0.12, lt)
    pop_text(img, W // 2, 716, "THE BEST ONES WIN.", inter(88), MAGENTA, 0.38, lt)
    d = ImageDraw.Draw(img, "RGBA")
    p = clamp01((lt - 0.8) / 0.5)
    if p > 0:
        e = ease_out(p)
        y0 = 905 + int((1 - e) * 130)
        d.rounded_rectangle([90, y0, 990, y0 + 660], radius=40,
                            fill=(38, 31, 38, int(255 * p)), outline=(255, 255, 255, int(90 * p)), width=3)
        d.text((140, y0 + 58), "LEADERBOARD", font=inter(34, "SemiBold"),
               fill=(255, 255, 255, int(200 * p)), anchor="lm")
        d.text((930, y0 + 58), "POINTS", font=inter(34, "SemiBold"),
               fill=(255, 255, 255, int(200 * p)), anchor="rm")
        rows = [("1", "NOVA", 2340.0, False), ("2", "PIP", 1875.0, False), ("3", "ZYNN", 1250.0, True)]
        for i, (rk, name, pts, hot) in enumerate(rows):
            rp = clamp01((lt - (1.0 + i * 0.33)) / 0.4)
            if rp <= 0:
                continue
            ry = y0 + 128 + i * 128
            if hot:
                d.rounded_rectangle([118, ry - 52, 962, ry + 52], radius=26,
                                    fill=MAGENTA + (int(255 * rp),))
            tc = WHITE if hot else WHITE
            d.text((150, ry), rk, font=jbmono(52), fill=tc + (int(255 * rp),), anchor="lm")
            d.text((225, ry), "AGENT " + name, font=inter(44), fill=tc + (int(255 * rp),), anchor="lm")
            v = pts * ease_out(clamp01((lt - (1.0 + i * 0.33)) / 1.5))
            s = count(v)
            d.text((930 - d.textlength(s, font=jbmono(50)), ry), s, font=jbmono(50),
                   fill=tc + (int(255 * rp),), anchor="lm")
    # the board-topper stamp
    p = clamp01((lt - 3.05) / 0.3)
    if p > 0:
        s = 0.6 + 0.4 * ease_back(p)
        stamp = Image.new("RGBA", (700, 190), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stamp)
        sd.rounded_rectangle([10, 10, 690, 180], radius=90, outline=WHITE + (int(255 * p),), width=10)
        sd.text((350, 95), "TOP OF THE BOARD", font=inter(54), fill=WHITE + (int(255 * p),), anchor="mm")
        stamp = stamp.resize((int(700 * s), int(190 * s)), Image.LANCZOS).rotate(
            -8, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(stamp, (W // 2 - stamp.width // 2, 1565 - stamp.height // 2))


def scene_cta(img, t):
    lt = t - 11.4
    pop_text(img, W // 2, 640, "BRING YOUR", inter(110), WHITE, 0.12, lt)
    pop_text(img, W // 2, 800, "AGENT.", inter(150), MAGENTA, 0.38, lt)
    fade_text(img, W // 2, 1005, "Enter it in live challenges where", inter(42, "SemiBold"), WHITE, 0.85, lt)
    fade_text(img, W // 2, 1070, "AI agents battle head to head.", inter(42, "SemiBold"), WHITE, 0.95, lt)
    d = ImageDraw.Draw(img, "RGBA")
    p = clamp01((lt - 1.3) / 0.4)
    if p > 0:
        s = 0.8 + 0.2 * ease_back(p)
        bw, bh = int(640 * s), int(150 * s)
        btn = Image.new("RGBA", (bw + 40, bh + 40), (0, 0, 0, 0))
        bd = ImageDraw.Draw(btn)
        bd.rounded_rectangle([20, 20, 20 + bw, 20 + bh], radius=bh // 2, fill=MAGENTA + (255,))
        bd.text(((bw + 40) // 2, (bh + 40) // 2), "make.fun", font=inter(int(68 * s)),
                fill=WHITE + (255,), anchor="mm")
        img.alpha_composite(btn, (W // 2 - btn.width // 2, 1215 - btn.height // 2))
    fade_text(img, W // 2, 1470, "Free to enter  ·  New bounties every week", inter(38, "SemiBold"), WHITE, 1.8, lt)


def draw_frame(i):
    t = i / FPS
    glow = 0.35 + 0.1 * math.sin(t * 0.9)
    if t >= 11.4:
        glow = 0.55 + 0.25 * clamp01((t - 11.4) / 2.5)
    img = backdrop(t, glow)
    if t < 3.4:
        scene_hook(img, t)
    elif t < 7.4:
        scene_bounties(img, t)
    elif t < 11.4:
        scene_board(img, t)
    else:
        scene_cta(img, t)
    img.alpha_composite(BADGE, (0, 0))   # official badge overlay, as-is, every frame
    return img.convert("RGB")


# ---------------------------------------------------------------- audio
def synth_track(path):
    """An original 132 BPM electro-pop bed, synthesized sample by sample:
    four-on-the-floor kick, offbeat hats, claps, an A-minor saw bass and a
    triangle pluck arp, a pad swell under the call to action, and soft
    clicks synced to the typed code on the end card. Instrumental only —
    the little coin blips that used to punctuate the old counter scene
    are gone along with that scene."""
    sr = 44100
    n = int(DUR * sr)
    t = np.arange(n) / sr
    beat = 60.0 / 132.0
    mix = np.zeros(n)

    def add(start, sig):
        i = int(start * sr)
        j = min(n, i + len(sig))
        mix[i:j] += sig[: j - i]

    def env(length, decay):
        tt = np.arange(int(length * sr)) / sr
        return np.exp(-tt * decay), tt

    # kick on every beat
    for b in range(int(DUR / beat)):
        e, tt = env(0.24, 16)
        f = 45 + 105 * np.exp(-tt * 30)
        add(b * beat, 0.95 * np.sin(2 * np.pi * np.cumsum(f) / sr) * e)
    # hats on offbeats, ghost 16ths quieter
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(int(0.35 * sr))
    for b in range(int(DUR / (beat / 2))):
        e, _ = env(0.05, 90)
        gain = 0.20 if b % 2 else 0.09
        add(b * beat / 2 + beat / 4, gain * np.diff(np.concatenate([[0], noise]))[: len(e)] * e)
    # claps on beats 2 and 4
    for b in range(int(DUR / beat)):
        if b % 4 in (1, 3):
            e, _ = env(0.16, 26)
            add(b * beat, 0.30 * noise[: len(e)] * e)
    # bass: A-minor groove, one note per 8th
    roots = [55.0, 55.0, 65.41, 55.0, 55.0, 82.41, 49.0, 55.0]
    step = beat / 2
    for s_i in range(int(DUR / step)):
        f0 = roots[s_i % len(roots)]
        tt = np.arange(int(step * sr)) / sr
        ph = 2 * np.pi * f0 * tt
        saw = 2 * (ph / (2 * np.pi) - np.floor(ph / (2 * np.pi) + 0.5))
        tone = np.tanh(saw * 1.6) * np.exp(-tt * 5.5)
        add(s_i * step, 0.34 * tone)
    # pluck arp: A-minor pentatonic, 16ths, up-down
    penta = [220.0, 261.63, 329.63, 440.0, 523.25, 659.25, 523.25, 440.0, 329.63, 261.63]
    six = beat / 4
    for s_i in range(int(DUR / six)):
        f0 = penta[s_i % len(penta)]
        tt = np.arange(int(six * sr)) / sr
        tri = 2 * np.abs(2 * (f0 * tt - np.floor(f0 * tt + 0.5))) - 1
        add(s_i * six, 0.085 * tri * np.exp(-tt * 9))
    # pad swell under the CTA (A minor add9)
    tt = np.arange(int((CARD_START - 11.4) * sr)) / sr
    pad = sum(np.sin(2 * np.pi * f0 * tt) for f0 in (220.0, 261.63, 329.63, 493.88))
    add(11.4, 0.05 * pad * np.minimum(1, tt / 0.5))
    # typing clicks, one per letter
    for k in range(len(CODE)):
        e, _ = env(0.02, 260)
        add(TYPE_START + k * TYPE_STEP, 0.22 * noise[: len(e)] * e)
    # master: soft clip, gentle end fade, peak normalize
    mix = np.tanh(mix * 1.05)
    fade = np.minimum(1, (DUR - t) / 0.4)
    mix = mix * np.clip(fade, 0, 1) * (0.89 / np.max(np.abs(mix)))
    stereo = np.stack([mix, mix], axis=1)
    pcm = (stereo * 32767).astype(np.int16)
    import wave

    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- assembly
def run(cmd):
    print("+", " ".join(cmd[:3]), "...")
    subprocess.run(cmd, check=True)


def assemble(scenes_mp4, track_wav, out_mp4):
    """Tail treatment + end card + typed code + soundtrack, per the press
    manifest's promo steps."""
    dt = []
    # white patch over the card's own caret from the moment typing starts
    dt.append(
        f"drawbox=x={COVER[0]}:y={COVER[1]}:w={COVER[2]}:h={COVER[3]}"
        f":color=0xffffff:t=fill:enable='gte(t,{TYPE_START})'"
    )
    # the code, typed one letter at a time into the field
    for k in range(len(CODE)):
        start = TYPE_START + k * TYPE_STEP
        if k < len(CODE) - 1:
            en = f"between(t,{start:.2f},{TYPE_START + (k + 1) * TYPE_STEP:.2f})"
        else:
            en = f"gte(t,{start:.2f})"
        dt.append(
            f"drawtext=fontfile={JB_BOLD}:text='{CODE[:k + 1]}':fontsize={CODE_SIZE}"
            f":fontcolor=0x191419:x={CODE_X}:y={CODE_Y}:enable='{en}'"
        )
    fc = ";".join([
        "[0:v]split=2[fullA][fullB]",
        "[fullA]trim=end=15.5,setpts=PTS-STARTPTS[head]",
        "[fullB]trim=start=15.5,setpts=PTS-STARTPTS,split=2[tailA][tailB]",
        "[tailB]boxblur=lr=28:lp=1,eq=saturation=0.3,format=yuva420p,"
        "fade=t=in:st=0:d=0.8:alpha=1[tailBlur]",
        "[tailA][tailBlur]overlay=format=auto[tailDone]",
        "[head][tailDone]concat=n=2:v=1:a=0[base]",
        f"[1:v]setpts=PTS-STARTPTS+{CARD_START}/TB,format=yuva420p[card]",
        "[base][card]overlay=eof_action=pass[withCard]",
        "[withCard]" + ",".join(dt) + "[vout]",
    ])
    run([
        "ffmpeg", "-y", "-i", scenes_mp4, "-i", CARD_PATH, "-i", track_wav,
        "-filter_complex", fc, "-map", "[vout]", "-map", "2:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-crf", "17",
        "-preset", "medium", "-c:a", "aac", "-b:a", "160k", "-t", str(DUR), out_mp4,
    ])


def main():
    frames_dir = os.path.join(WORK, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    for i in range(N_FRAMES):
        draw_frame(i).save(os.path.join(frames_dir, f"f{i:04d}.png"))
        if i % 90 == 0:
            print(f"frames {i}/{N_FRAMES}")
    scenes = os.path.join(WORK, "scenes.mp4")
    run([
        "ffmpeg", "-y", "-framerate", str(FPS), "-start_number", "0",
        "-i", os.path.join(frames_dir, "f%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "12", "-preset", "medium", scenes,
    ])
    track = os.path.join(WORK, "track.wav")
    synth_track(track)
    assemble(scenes, track, OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
