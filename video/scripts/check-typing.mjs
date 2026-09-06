// Verify one-letter cadence and exact timing against the previous capture.
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { PNG } from "pngjs";
const folder = process.env.CAPTURE_OUTPUT || path.resolve("public/capture");
const before = JSON.parse(
  await readFile(path.join(folder, "manifest-before-typing.json"), "utf8"),
);
const after = JSON.parse(
  await readFile(path.join(folder, "manifest.json"), "utf8"),
);
const checks = [];
const fail = (m) => {
  throw new Error(m);
};
if (JSON.stringify(before.cursor) !== JSON.stringify(after.cursor))
  fail("Cursor paths changed");
const unchanged = (d) =>
  d.captures
    .filter((s) => !s.note.includes("Typing") && s.note !== "Completed field")
    .sort((a, b) => a.t - b.t);
if (JSON.stringify(unchanged(before)) !== JSON.stringify(unchanged(after)))
  fail("Non-typing snapshots changed");
for (const [start, duration] of [
  [7, 3],
  [11, 9],
  [27, 5],
  [71, 9],
]) {
  const shots = after.captures
    .filter((s) => s.typingStart === start)
    .sort((a, b) => a.t - b.t);
  if (!shots.length) fail("No updated typing snapshots at " + start);
  const last = shots.at(-1),
    letters = Array.from(last.typedText);
  if (
    shots[0].t !== start ||
    last.t !== start + duration ||
    shots.length !== letters.length + 1
  )
    fail("Timing/count changed at " + start);
  if (
    !before.captures.some((s) => s.t === start && s.note.includes("Typing")) ||
    !before.captures.some(
      (s) => s.t === start + duration && s.note === "Completed field",
    )
  )
    fail("Original timing does not match");
  for (let i = 0; i < shots.length; i++)
    if (
      shots[i].typedLength !== i ||
      shots[i].typedText !== letters.slice(0, i).join("")
    )
      fail("Character skipped at " + start);
  let previous = 0;
  for (let frame = start * 30; frame <= (start + duration) * 30; frame++) {
    const visible = shots.filter((s) => s.t <= frame / 30).at(-1).typedLength;
    if (visible - previous > 1)
      fail("More than one letter appears in a video frame at " + frame);
    previous = visible;
  }
  // Verify surrounding pixels for every replacement, not merely a sample.
  const base = PNG.sync.read(
    await readFile(path.join(folder, shots[0].baseFile)),
  );
  for (const shot of shots) {
    const image = PNG.sync.read(await readFile(path.join(folder, shot.file))),
      r = shot.fieldClip;
    for (let y = 0; y < base.height; y++) {
      const row = y * base.width * 4;
      const parts =
        y < r.y || y >= r.y + r.height
          ? [[0, base.width * 4]]
          : [
              [0, r.x * 4],
              [(r.x + r.width) * 4, base.width * 4],
            ];
      for (const [a, b] of parts)
        if (
          !image.data
            .subarray(row + a, row + b)
            .equals(base.data.subarray(row + a, row + b))
        )
          fail("Pixels outside input changed: " + shot.file);
    }
  }
  checks.push({
    start,
    end: start + duration,
    duration,
    characters: letters.length,
    snapshots: shots.length,
    maximumLettersPerVideoFrame: 1,
    surroundingPixelsUnchanged: true,
  });
}
await writeFile(
  path.join(folder, "typing-validation.json"),
  JSON.stringify(
    { checks, cursorUnchanged: true, otherSnapshotsUnchanged: true },
    null,
    2,
  ),
);
console.log(JSON.stringify(checks));
