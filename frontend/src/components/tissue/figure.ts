import { conditionIndices, type Tissue, type View } from "./types";
/** Export canvas pixels with condition labels, units and the exact recipe beside the PNG. */
export function saveFigure(
  host: HTMLElement,
  data: Tissue,
  view: View,
  owner: string,
) {
  const canvases = Array.from(host.querySelectorAll("canvas"));
  if (!canvases.length) return;
  const width = 1600,
    height = 1000,
    out = document.createElement("canvas");
  out.width = width;
  out.height = height;
  const ctx = out.getContext("2d")!;
  ctx.fillStyle = "#090d20";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#c0c9e4";
  ctx.font = "28px sans-serif";
  ctx.fillText("Living tissue · conditional simulation", 40, 45);
  ctx.font = "16px sans-serif";
  ctx.fillText(owner.slice(0, 130), 40, 76);
  const indices = conditionIndices(view);
  canvases.forEach((canvas, i) => {
    const x = 40 + (i * 1520) / canvases.length,
      w = 1520 / canvases.length;
    const scale = Math.min(w / canvas.width, 760 / canvas.height);
    ctx.drawImage(
      canvas,
      x + (w - canvas.width * scale) / 2,
      135,
      canvas.width * scale,
      canvas.height * scale,
    );
    ctx.fillStyle = "#c0c9e4";
    ctx.fillText(data.conditions[indices[i]].label, x, 110);
    const bar =
      (50 / ((2 * Math.tan((20 * Math.PI) / 180) * 490) / view.zoom)) *
      canvas.height *
      scale;
    ctx.fillRect(x + 15, 860, bar, 2);
    ctx.fillText("50 µm · focal plane", x + 15, 886);
  });
  ctx.fillText(
    `Tumor: pearl · CAF: amber (illustrative shape) · Dead: violet · Alanine: cyan fixed 0–${view.fieldMaximum} mM`,
    40,
    927,
  );
  ctx.fillText(
    `${data.conditions[view.condition].frames[view.frame].time} min · section z=${view.section} µm · opacity ${view.opacity} · ${view.preset} · ${data.category}`,
    40,
    958,
  );
  const download = (href: string, name: string) => {
    const a = document.createElement("a");
    a.href = href;
    a.download = name;
    a.click();
  };
  download(out.toDataURL("image/png"), "living-tissue.png");
  const url = URL.createObjectURL(
    new Blob(
      [JSON.stringify({ owner, view, provenance: data.provenance }, null, 2)],
      { type: "application/json" },
    ),
  );
  download(url, "living-tissue.recipe.json");
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
