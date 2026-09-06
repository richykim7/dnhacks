#!/usr/bin/env python3
"""Bundle the pitch with its adjacent video so the fallback link is portable."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
FILES=['DNHacks_2026_DN_Research.pptx','DNHacks_2026_DN_Research.pdf','binder-reveal.mp4']
INSTRUCTIONS='''DNHacks presentation — ten slides / about 6 minutes 15 seconds

Extract this entire folder before opening the PowerPoint.
Slide 4: embedded video is configured to start in PowerPoint Slide Show mode.
The green OPEN VIDEO button opens the adjacent binder-reveal.mp4.
The PDF and document previews show a still image; play the MP4 separately there.

Every PowerPoint slide has a tentative script and technical/source/editing Notes.
Slides 3 and 7 contain actual website UI with sample data; replace with your run.
Slides 7 and 8 are the editable discovery reveal and immediately following evidence
boundary. The candidate, matching paper, cutoff and access audit still need filling.
Keep the paper fade and the following frozen-evidence slide adjacent.
Save manual edits separately from regenerated copies.

Fonts: IBM Plex Sans and IBM Plex Mono (not embedded).
'''

if __name__=='__main__':
    with ZipFile(OUT/'DNHacks_Presentation_Bundle.zip','w',compression=ZIP_DEFLATED) as z:
        for name in FILES:
            z.write(OUT/name,name)
        z.write(ROOT/'speaker-notes.md','speaker-notes.md')
        z.writestr('READ-ME.txt',INSTRUCTIONS)
    print(OUT/'DNHacks_Presentation_Bundle.zip')
