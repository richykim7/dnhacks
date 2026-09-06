import { useEffect, useLayoutEffect, useMemo, useRef, useCallback } from "react";
import { Canvas, useThree, useFrame } from "@react-three/fiber";
import * as T from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { layoutPoleLabels } from "./labels";
import type { SpindleBundle, SpindleRecipe, Vec3 } from "./types";
function PoleLabel({ id, selected, register, pick }: { id: string; selected: boolean; register: (sprite:T.Sprite|null)=>void; pick: ()=>void }) {
  const texture = useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 256;
    canvas.height = 80;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, 256, 80);
    ctx.font = "32px monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.strokeStyle = "#080c20";
    ctx.lineWidth = 5;
    ctx.strokeText(id, 128, 40);
    ctx.fillStyle = selected ? "#ffd296" : "#d8ebf1";
    ctx.fillText(id, 128, 40);
    return new T.CanvasTexture(canvas);
  }, [id, selected]);
  useEffect(() => () => texture.dispose(), [texture]);
  return (
    <sprite ref={register} frustumCulled={false} renderOrder={10} onClick={e=>{e.stopPropagation();pick();}}>
      <spriteMaterial map={texture} transparent depthTest={false} sizeAttenuation={false} />
    </sprite>
  );
}
function PoleLabels({poles, selected, pick}: {poles: {id:string;position:Vec3}[];selected:string|null;pick:(id:string)=>void}) {
  const {camera, size, scene} = useThree();
  const sprites = useRef(new Map<string,T.Sprite>());
  const lines = useMemo(()=>new T.BufferGeometry().setAttribute("position",new T.BufferAttribute(new Float32Array(poles.length*6),3)),[poles.length]);
  useEffect(()=>()=>lines.dispose(),[lines]);
  const update = useCallback(()=>{
    camera.updateMatrixWorld();
    const projected=poles.map(p=>{const v=new T.Vector3(...p.position).project(camera);return {id:p.id,x:(v.x+1)*size.width/2,y:(1-v.y)*size.height/2,z:v.z};});
    const labels=layoutPoleLabels(projected,size.width,size.height);
    const positions=lines.getAttribute("position") as T.BufferAttribute;
    const scale=40*2*Math.tan((camera as T.PerspectiveCamera).fov*Math.PI/360)/size.height;
    labels.forEach((label,i)=>{
      const p=poles.find(p=>p.id===label.id)!;
      const source=projected.find(p=>p.id===label.id)!;
      const target=new T.Vector3(label.x/size.width*2-1,1-label.y/size.height*2,source.z).unproject(camera);
      const sprite=sprites.current.get(p.id);
      if(sprite){sprite.position.copy(target);sprite.scale.set(scale*3.2,scale,1);sprite.updateMatrixWorld(true);}
      positions.setXYZ(i*2,...p.position);positions.setXYZ(i*2+1,target.x,target.y,target.z);
    });
    positions.needsUpdate=true;
  },[camera,size.width,size.height,poles,lines]);
  useFrame(update);
  useLayoutEffect(()=>{scene.userData.updateSpindleLabels=update;update();return()=>{if(scene.userData.updateSpindleLabels===update)delete scene.userData.updateSpindleLabels;};},[scene,update]);
  return <group>
    <lineSegments geometry={lines} frustumCulled={false} renderOrder={9}><lineBasicMaterial color="#91a6b3" transparent opacity={.6} depthTest={false} /></lineSegments>
    {poles.map(p=><PoleLabel key={p.id} id={p.id} selected={selected===p.id} pick={()=>pick(p.id)} register={sprite=>{if(sprite)sprites.current.set(p.id,sprite);else sprites.current.delete(p.id);}} />)}
  </group>;
}
export type RenderState = {
  camera: {
    position: Vec3;
    target: Vec3;
    fov: number;
    near: number;
    far: number;
    up: number[];
    quaternion: number[];
    projection: string;
  };
  viewport: { width: number; height: number; dpr: number };
  renderer: string;
  physical_to_scene: { units: string; scale: number; interpolation: string };
  physical_time_s: number;
  poles: unknown;
  cortical_motors: unknown;
  segments: number;
  frame_render_ms: number;
};
function Filaments({
  bundle,
  recipe,
}: {
  bundle: SpindleBundle;
  recipe: SpindleRecipe;
}) {
  const frame = bundle.runs[recipe.run].frames[recipe.frame];
  const geometry = useMemo(() => {
    const positions: number[] = [],
      colors: number[] = [];
    for (const f of frame.filaments) {
      const selected = !recipe.selected || recipe.selected === f.pole;
      for (let j = 1; j < f.points.length; j++) {
        positions.push(...f.points[j - 1], ...f.points[j]);
        for (const p of [f.points[j - 1], f.points[j]]) {
          const c = new T.Color(selected ? "#86c3cf" : "#365569");
          c.multiplyScalar(
            (recipe.treatment === "fine" ? 0.45 : 0.7) *
              (0.3 + (0.5 * (p[2] / bundle.radius[2] + 1)) / 2),
          );
          colors.push(c.r, c.g, c.b);
        }
      }
    }
    return new T.BufferGeometry()
      .setAttribute("position", new T.Float32BufferAttribute(positions, 3))
      .setAttribute("color", new T.Float32BufferAttribute(colors, 3));
  }, [frame, recipe.selected, recipe.treatment, bundle.radius]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial
        vertexColors
        transparent
        opacity={0.85}
        blending={T.AdditiveBlending}
        depthWrite={false}
      />
    </lineSegments>
  );
}
function MotorField({ frame }: { frame: import("./types").SpindleFrame }) {
  const geometry = useMemo(() => {
    const positions: number[] = [], colors: number[] = [];
    for (const motor of frame.cortical_motors ?? []) {
      positions.push(...motor.position);
      const color = new T.Color(motor.filament ? "#fff0b5" : "#d59642");
      colors.push(color.r, color.g, color.b);
    }
    return new T.BufferGeometry().setAttribute("position", new T.Float32BufferAttribute(positions, 3))
      .setAttribute("color", new T.Float32BufferAttribute(colors, 3));
  }, [frame]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <points geometry={geometry}><pointsMaterial vertexColors size={5} sizeAttenuation={false} transparent opacity={0.9} depthWrite={false} /></points>;
}
function Stage({
  bundle,
  recipe,
  pick,
  ready,
  onCamera,
}: {
  bundle: SpindleBundle;
  recipe: SpindleRecipe;
  pick: (id: string) => void;
  ready: (canvas: HTMLCanvasElement, state: RenderState) => void;
  onCamera: (p: Vec3, t: Vec3) => void;
}) {
  const { gl, scene, camera, invalidate, size } = useThree();
  const orbit = useRef<OrbitControls>(null);
  const frame = bundle.runs[recipe.run].frames[recipe.frame];
  useLayoutEffect(() => {
    const c = new OrbitControls(camera, gl.domElement);
    c.enableDamping = false;
    c.minDistance = 8;
    c.maxDistance = 100;
    c.addEventListener("change", () => invalidate());
    c.addEventListener("end", () =>
      onCamera(camera.position.toArray() as Vec3, c.target.toArray() as Vec3),
    );
    orbit.current = c;
    return () => c.dispose();
  }, [gl, camera, invalidate, onCamera]);
  useLayoutEffect(() => {
    const selected = frame.poles.find((p) => p.id === recipe.selected);
    const target =
      recipe.camera?.target ||
      (recipe.shot === "detail" && selected
        ? selected.position
        : ([0, 0, 0] as Vec3));
    const distance =
      recipe.shot === "detail"
        ? 17
        : Math.max(...bundle.radius) *
          (size.width < 600 ? 3.7 : 3.4) *
          Math.max(1, size.height / size.width);
    const offset = recipe.shot === "front" ? [0, 0, 1] : [0.48, 0.3, 0.83];
    camera.position.fromArray(
      recipe.camera?.position ||
        (target.map((x, i) => x + distance * offset[i]) as Vec3),
    );
    const lens = camera as T.PerspectiveCamera;
    lens.fov = recipe.camera?.fov ?? 40;
    lens.near = recipe.camera?.near ?? 0.1;
    lens.far = recipe.camera?.far ?? 300;
    lens.updateProjectionMatrix();
    camera.lookAt(...target);
    orbit.current?.target.fromArray(target);
    orbit.current?.update();
    invalidate();
  }, [
    recipe.shot,
    recipe.camera,
    recipe.selected,
    bundle.radius,
    camera,
    invalidate,
    size.width,
    size.height,
  ]);
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await gl.compileAsync(scene, camera);
      if (cancelled) return;
      scene.userData.updateSpindleLabels?.();
      const started = performance.now();
      gl.render(scene, camera);
      gl.getContext().finish();
      if (!cancelled) {
        const c = camera as T.PerspectiveCamera;
        ready(gl.domElement, {
          camera: {
            position: c.position.toArray() as Vec3,
            target: (orbit.current?.target.toArray() || [0, 0, 0]) as Vec3,
            fov: c.fov,
            near: c.near,
            far: c.far,
            up: c.up.toArray(),
            quaternion: c.quaternion.toArray(),
            projection: c.type,
          },
          viewport: {
            width: gl.domElement.width,
            height: gl.domElement.height,
            dpr: gl.getPixelRatio(),
          },
          renderer: `Three.js ${T.REVISION} / WebGL2`,
          physical_to_scene: { units: "um", scale: 1, interpolation: "none" },
          physical_time_s: frame.time,
          poles: frame.poles,
          cortical_motors: frame.cortical_motors ?? null,
          segments: frame.filaments.reduce(
            (n, f) => n + f.points.length - 1,
            0,
          ),
          frame_render_ms: performance.now() - started,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [recipe, gl, scene, camera, ready, size]);
  const trails = useMemo(() => {
    const v: number[] = [];
    if (recipe.trails)
      for (const p of frame.poles) {
        const history = bundle.runs[recipe.run].frames.slice(
          Math.max(0, recipe.frame - 20),
          recipe.frame + 1,
        );
        for (let i = 1; i < history.length; i++) {
          const a = history[i - 1].poles.find((x) => x.id === p.id),
            b = history[i].poles.find((x) => x.id === p.id);
          if (a && b) v.push(...a.position, ...b.position);
        }
      }
    return new T.BufferGeometry().setAttribute(
      "position",
      new T.Float32BufferAttribute(v, 3),
    );
  }, [bundle, frame, recipe]);
  useEffect(() => () => trails.dispose(), [trails]);
  return (
    <>
      <color attach="background" args={["#080c20"]} />
      <ambientLight intensity={0.8} />
      <directionalLight position={[8, 20, 25]} intensity={3} color="#dceaff" />
      <pointLight position={[-10, 0, 8]} intensity={90} color="#54cbd0" />
      <mesh scale={bundle.radius}>
        <sphereGeometry args={[1, 64, 40]} />
        <meshPhysicalMaterial
          color="#9fbcca"
          side={T.BackSide}
          transparent
          opacity={0.065}
          roughness={0.28}
          metalness={0.6}
          depthWrite={false}
        />
      </mesh>
      {[0, 1, 2].map((i) => (
        <mesh
          key={i}
          scale={[bundle.radius[0], bundle.radius[1], bundle.radius[2]]}
          rotation={
            i === 0
              ? [0, 0, 0]
              : i === 1
                ? [Math.PI / 2, 0, 0]
                : [0, Math.PI / 2, 0]
          }
        >
          <torusGeometry args={[1, 0.0025, 6, 160]} />
          <meshBasicMaterial
            color={i === 0 ? "#adc3e2" : "#527681"}
            transparent
            opacity={i === 0 ? 0.4 : 0.12}
          />
        </mesh>
      ))}
      <Filaments bundle={bundle} recipe={recipe} />
      <MotorField frame={frame} />
      <PoleLabels poles={frame.poles} selected={recipe.selected} pick={pick} />
      <lineSegments geometry={trails}>
        <lineBasicMaterial color="#e7b878" transparent opacity={0.6} />
      </lineSegments>
      {frame.poles.map((p) => (
        <group key={p.id} position={p.position}>
          <mesh
            onClick={(e) => {
              e.stopPropagation();
              pick(p.id);
            }}
          >
            <sphereGeometry args={[0.32, 24, 18]} />
            <meshStandardMaterial
              color={p.id === recipe.selected ? "#ffc680" : "#f1eee6"}
              emissive={p.id === recipe.selected ? "#b26b22" : "#426d7e"}
              emissiveIntensity={0.5}
              roughness={0.23}
              metalness={0.25}
            />
          </mesh>
          <mesh>
            <sphereGeometry args={[0.46, 24, 18]} />
            <meshBasicMaterial
              color="#c8e9ff"
              transparent
              opacity={0.04}
              depthWrite={false}
            />
          </mesh>
        </group>
      ))}
    </>
  );
}
export default function SpindleScene(props: Parameters<typeof Stage>[0]) {
  return (
    <Canvas
      frameloop="demand"
      dpr={1}
      camera={{ position: [18, 12, 38], fov: 40, near: 0.1, far: 300 }}
      gl={{ antialias: true, preserveDrawingBuffer: true }}
    >
      <Stage {...props} />
    </Canvas>
  );
}
