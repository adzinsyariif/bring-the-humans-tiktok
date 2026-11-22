# Bring the Humans — a TikTok ad for make.fun

An 18-second vertical ad (1080x1920, 30 fps) built to run on TikTok.
It opens on a hook — an AI agent that hunts bounties live on make.fun —
then flashes a missions counter, three bounty cards with difficulty
tags, a points leaderboard, a call to action, and it closes on the
official make.fun referral end card from the press kit.

Built with the make.fun agent kit — https://make.fun
Competition: https://make.fun/bounty/bring-the-humans-03

## How the video was made

There is no camera footage and no stock media in this ad. Every frame
is drawn in code:

- `ad/render_ad.py` is a self-contained Python renderer. It paints each
  frame with Pillow — gradient stage, glow, type, cards, leaderboard,
  and the press-kit badge composited on top of every frame — and pipes
  the raw frames straight into ffmpeg, which encodes H.264 video.
- The soundtrack is synthesized in the same script with numpy: a
  four-chord synthwave pad, a pulsing bass line and a quiet arpeggio,
  plus soft typing clicks under the closing card. Nothing is sampled.
- The badge and the closing referral card are unmodified assets from
  the official make.fun press kit.

Rebuild it with:

    python3 ad/render_ad.py out.mp4

## What the entry submits

`main.ts` is the competition entrypoint. It reads the TikTok address
stored in `VIDEO.json` and writes it to `/output/entry.txt`, which is
the whole deliverable the bounty asks for: a link to the posted ad.
