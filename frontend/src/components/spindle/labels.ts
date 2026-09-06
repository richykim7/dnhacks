export type ScreenPoint = { id: string; x: number; y: number };
export function layoutPoleLabels(poles: ScreenPoint[], width: number, height: number) {
  const placed: ScreenPoint[] = [];
  const inside = (x: number, y: number) => x >= 22 && x <= width - 22 && y >= 22 && y <= height - 22;
  for (const [rank, p] of [...poles].sort((a,b) => a.id.localeCompare(b.id)).entries()) {
    let best: ScreenPoint | undefined;
    for (const radius of [42, 64, 88, 116, 148]) {
      for (let attempt = 0; attempt < 16; attempt++) {
        const angle = -Math.PI * .75 + rank * Math.PI * 2 / poles.length + attempt * Math.PI / 8;
        const x = p.x + radius * Math.cos(angle), y = p.y + radius * Math.sin(angle);
        if (inside(x,y) && !placed.some(q => Math.abs(q.x-x) < 42 && Math.abs(q.y-y) < 25)
          && !poles.some(q => Math.abs(q.x-x) < 32 && Math.abs(q.y-y) < 26)) {
          best = {id:p.id,x,y}; break;
        }
      }
      if (best) break;
    }
    // Bounded fallback for crowded/offscreen scenes: keep identity discoverable.
    placed.push(best ?? {id:p.id,x:rank % 2 ? width - 25 : 25,y:32 + Math.floor(rank/2)*25});
  }
  return placed;
}
