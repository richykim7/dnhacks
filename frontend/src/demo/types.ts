/** Local curated animation only; never a scientific result. */
export interface DemoSceneProps {
  time: number;
  reducedMotion?: boolean;
  interactive?: boolean;
}
export const DEMO_DURATION = 18;
export type DemoSceneId = "binder" | "tissue" | "spindle";
