import { Canvas, useThree, useFrame } from "@react-three/fiber";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { Cell, Frame, Tissue, View } from "./types";
import { aggregateCells, boundedVolume } from "./aggregation";

function Cells({
  cells,
  view,
  onSelect,
  light,
}: {
  cells: Cell[];
  view: View;
  onSelect: (id: number) => void;
  light: boolean;
}) {
  const mesh = useRef<THREE.InstancedMesh>(null!);
  const membrane = useMemo(() => {
    const m = new THREE.MeshPhysicalMaterial({
      side: THREE.DoubleSide,
      roughness: 0.52,
      metalness: 0.08,
      clearcoat: cells.length > 2000 ? 0 : 0.4,
      clearcoatRoughness: 0.5,
      clippingPlanes: [
        new THREE.Plane(new THREE.Vector3(0, 0, -1), view.section),
      ],
    });
    m.onBeforeCompile = (shader) => {
      shader.fragmentShader = shader.fragmentShader.replace(
        "#include <normal_fragment_maps>",
        "#include <normal_fragment_maps>\n normal=normalize(normal+0.065*vec3(sin(vViewPosition.y*2.3)*cos(vViewPosition.z*1.7),sin(vViewPosition.z*2.1)*cos(vViewPosition.x*1.9),sin(vViewPosition.x*2.7)*cos(vViewPosition.y*1.5))); ",
      );
    };
    return m;
  }, [view.section, cells.length > 2000]);
  useEffect(() => () => membrane.dispose(), [membrane]);
  const visible = useMemo(
    () => cells.filter((c) => c.position[2] - c.radius <= view.section),
    [cells, view.section],
  );
  useLayoutEffect(() => {
    const o = new THREE.Object3D(),
      color = new THREE.Color();
    visible.forEach((c, i) => {
      o.position.set(...c.position);
      o.scale.set(
        c.radius * (c.type === "CAF" ? 1.8 : 1),
        c.radius * (c.type === "CAF" ? 0.48 : 1),
        c.radius * (c.type === "CAF" ? 0.6 : 1),
      );
      o.rotation.set(c.id * 0.73, c.id * 0.31, c.id * 1.17);
      o.updateMatrix();
      mesh.current.setMatrixAt(i, o.matrix);
      color.set(
        c.id === view.selection
          ? "#72f5df"
          : c.state === "dead"
            ? light
              ? "#8c849a"
              : "#443953"
            : c.type === "CAF"
              ? "#db984e"
              : light
                ? "#8196b2"
                : "#c0c9e4",
      );
      mesh.current.setColorAt(i, color);
    });
    mesh.current.instanceMatrix.needsUpdate = true;
    mesh.current.computeBoundingSphere();
    if (mesh.current.instanceColor)
      mesh.current.instanceColor.needsUpdate = true;
  }, [visible, view.selection, light]);
  return (
    <>
      <instancedMesh
        ref={mesh}
        args={[undefined, undefined, visible.length]}
        onClick={(e) => {
          e.stopPropagation();
          if (e.instanceId !== undefined) onSelect(visible[e.instanceId].id);
        }}
      >
        <sphereGeometry args={cells.length > 2000 ? [1, 12, 8] : [1, 20, 14]} />
        <primitive object={membrane} attach="material" />
      </instancedMesh>
      <Caps
        cells={visible}
        section={view.section}
        light={light}
        onSelect={onSelect}
      />
    </>
  );
}
function Caps({
  cells,
  section,
  light,
  onSelect,
}: {
  cells: Cell[];
  section: number;
  light: boolean;
  onSelect: (id: number) => void;
}) {
  const cut = cells.filter(
    (c) => c.type === "tumor" && Math.abs(section - c.position[2]) < c.radius,
  );
  const mesh = useRef<THREE.InstancedMesh>(null!);
  useLayoutEffect(() => {
    const o = new THREE.Object3D();
    cut.forEach((c, i) => {
      const r = Math.sqrt(c.radius * c.radius - (section - c.position[2]) ** 2);
      o.position.set(c.position[0], c.position[1], section + 0.02);
      o.scale.set(r, r, 1);
      o.updateMatrix();
      mesh.current.setMatrixAt(i, o.matrix);
      mesh.current.setColorAt(
        i,
        new THREE.Color(
          c.state === "dead" ? "#55465e" : light ? "#728caa" : "#9eaac4",
        ),
      );
    });
    mesh.current.instanceMatrix.needsUpdate = true;
    mesh.current.computeBoundingSphere();
    if (mesh.current.instanceColor)
      mesh.current.instanceColor.needsUpdate = true;
  }, [cells, section, light]);
  return (
    <instancedMesh
      ref={mesh}
      args={[undefined, undefined, cut.length]}
      onClick={(e) => {
        e.stopPropagation();
        if (e.instanceId !== undefined) onSelect(cut[e.instanceId].id);
      }}
    >
      <circleGeometry args={[1, 32]} />
      <meshStandardMaterial roughness={0.8} side={THREE.DoubleSide} />
    </instancedMesh>
  );
}
function Field({
  frame,
  data,
  opacity,
  section,
  maximum,
  steps,
}: {
  frame: Frame;
  data: Tissue;
  opacity: number;
  section: number;
  maximum: number;
  steps: number;
}) {
  const texture = useMemo(() => {
    const t = new THREE.Data3DTexture(
      new Float32Array(frame.field.values),
      ...frame.field.dimensions,
    );
    t.format = THREE.RedFormat;
    t.type = THREE.FloatType;
    t.minFilter = THREE.LinearFilter;
    t.magFilter = THREE.LinearFilter;
    t.unpackAlignment = 1;
    t.needsUpdate = true;
    return t;
  }, [frame]);
  useEffect(() => () => texture.dispose(), [texture]);
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        premultipliedAlpha: true,
        depthWrite: false,
        side: THREE.BackSide,
        uniforms: {
          volume: { value: texture },
          alpha: { value: opacity },
          maximum: { value: maximum },
          clip: { value: section },
          low: {
            value: new THREE.Vector3(
              ...(data.domain.bounds.slice(0, 3) as [number, number, number]),
            ),
          },
          high: {
            value: new THREE.Vector3(
              ...(data.domain.bounds.slice(3) as [number, number, number]),
            ),
          },
        },
        vertexShader: `varying vec3 world; void main(){world=(modelMatrix*vec4(position,1.)).xyz; gl_Position=projectionMatrix*viewMatrix*vec4(world,1.);}`,
        fragmentShader: `precision highp sampler3D; uniform sampler3D volume; uniform float alpha,maximum,clip;uniform vec3 low,high; varying vec3 world;
void main(){vec3 ray=normalize(world-cameraPosition);vec3 inv=1./ray;vec3 t0=(low-cameraPosition)*inv,t1=(high-cameraPosition)*inv;vec3 a=min(t0,t1),b=max(t0,t1);float start=max(max(a.x,a.y),a.z),end=min(min(b.x,b.y),b.z);vec4 acc=vec4(0.);float stepSize=(end-max(start,0.))/${steps}.;for(int i=0;i<${steps};i++){vec3 p=cameraPosition+ray*(max(start,0.)+(float(i)+.5)*stepSize);if(p.z>clip)continue;float v=clamp(texture(volume,(p-low)/(high-low)).r/maximum,0.,1.);float k=v*alpha*.018*(48./${steps}.);acc.rgb+=(1.-acc.a)*k*vec3(.12,.83,.86);acc.a+=(1.-acc.a)*k;}gl_FragColor=acc;}`,
      }),
    [texture, opacity, section, data, maximum, steps],
  );
  useEffect(() => () => material.dispose(), [material]);
  const b = data.domain.bounds;
  return (
    <mesh
      material={material}
      position={[(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2]}
    >
      <boxGeometry args={[b[3] - b[0], b[4] - b[1], b[5] - b[2]]} />
    </mesh>
  );
}
function Camera({
  view,
  ready,
  target,
}: {
  view: View;
  ready: (height: number) => void;
  target: [number, number, number];
}) {
  const { camera, invalidate, gl, scene, size } = useThree();
  const pending = useRef(true);
  useLayoutEffect(() => {
    const r = 490 / view.zoom;
    camera.position.set(
      target[0] + r * Math.sin(view.azimuth) * Math.cos(view.elevation),
      target[1] + r * Math.sin(view.elevation),
      target[2] + r * Math.cos(view.azimuth) * Math.cos(view.elevation),
    );
    camera.lookAt(...target);
    camera.updateProjectionMatrix();
    pending.current = true;
    invalidate();
  }, [camera, view, invalidate, size.height, size.width, ...target]);
  useFrame(() => {
    gl.render(scene, camera);
    if (pending.current) {
      pending.current = false;
      ready(size.height);
    }
  }, 1);
  return null;
}
export default function TissueScene({
  data,
  frame,
  view,
  onSelect,
  onChange,
  ready,
  light,
}: {
  data: Tissue;
  frame: Frame;
  view: View;
  onSelect: (id: number) => void;
  onChange: (v: Partial<View>) => void;
  ready: (height: number) => void;
  light: boolean;
}) {
  const drag = useRef<[number, number] | null>(null);
  const [lost, setLost] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const [mobile, setMobile] = useState(matchMedia("(max-width:650px)").matches);
  useEffect(() => {
    const m = matchMedia("(max-width:650px)");
    const update = () => setMobile(m.matches);
    m.addEventListener("change", update);
    return () => m.removeEventListener("change", update);
  }, []);
  const displayCells = useMemo(
    () =>
      mobile && view.selection === null
        ? aggregateCells(frame.cells)
        : frame.cells,
    [mobile, frame.cells, view.selection],
  );
  const displayFrame = useMemo(
    () => (mobile ? { ...frame, field: boundedVolume(frame.field) } : frame),
    [mobile, frame],
  );
  const selected = frame.cells.find((c) => c.id === view.selection);
  return (
    <div
      className="tissue-canvas"
      data-source-cells={frame.cells.length}
      data-rendered-glyphs={displayCells.length}
      data-volume-steps={frame.cells.length > 2000 ? 24 : 48}
      data-volume-dimensions={displayFrame.field.dimensions.join("x")}
      tabIndex={0}
      role="group"
      aria-label="Tissue camera: arrow keys orbit, plus and minus zoom"
      onKeyDown={(e) => {
        const p: Partial<View> =
          e.key === "ArrowLeft"
            ? { azimuth: view.azimuth - 0.1 }
            : e.key === "ArrowRight"
              ? { azimuth: view.azimuth + 0.1 }
              : e.key === "ArrowUp"
                ? { elevation: Math.min(1.1, view.elevation + 0.1) }
                : e.key === "ArrowDown"
                  ? { elevation: Math.max(-1.1, view.elevation - 0.1) }
                  : e.key === "+"
                    ? { zoom: Math.min(2.8, view.zoom + 0.1) }
                    : e.key === "-"
                      ? { zoom: Math.max(0.6, view.zoom - 0.1) }
                      : {};
        if (Object.keys(p).length) {
          e.preventDefault();
          onChange(p);
        }
      }}
      onPointerDown={(e) => {
        drag.current = [e.clientX, e.clientY];
      }}
      onPointerUp={() => (drag.current = null)}
      onPointerLeave={() => (drag.current = null)}
      onPointerMove={(e) => {
        if (!drag.current || !e.buttons) return;
        const [x, y] = drag.current;
        drag.current = [e.clientX, e.clientY];
        onChange({
          azimuth: view.azimuth + (e.clientX - x) * 0.006,
          elevation: Math.max(
            -1.1,
            Math.min(1.1, view.elevation + (e.clientY - y) * 0.004),
          ),
        });
      }}
      onWheel={(e) =>
        onChange({
          zoom: Math.max(0.6, Math.min(2.8, view.zoom - e.deltaY * 0.001)),
        })
      }
    >
      {displayCells.length < frame.cells.length && (
        <p className="tissue-aggregation">
          {frame.cells.length.toLocaleString()} cells in{" "}
          {displayCells.length.toLocaleString()} type/state groups. Glyph volume
          sums occupied cell volume. Select a group to restore individual IDs.
        </p>
      )}
      {lost && (
        <div role="alert" className="tissue-context-error">
          Graphics context was lost.{" "}
          <button
            onClick={() => {
              setLost(false);
              setEpoch((e) => e + 1);
            }}
          >
            Restore tissue scene
          </button>
        </div>
      )}
      {!lost && (
        <Canvas
          key={epoch}
          onCreated={({ gl, get }) => {
            (gl.domElement as any).tissueCounters = () => ({
              frames: gl.info.render.frame,
              camera: get().camera.position.toArray(),
            });
            gl.domElement.addEventListener(
              "webglcontextlost",
              (event) => {
                event.preventDefault();
                setLost(true);
                onChange({});
              },
              { once: true },
            );
            (gl.domElement as any).tissueBenchmark = async (count = 20) => {
              const samples: number[] = [];
              const context = gl.getContext();
              for (let i = 0; i < count + 3; i++) {
                await new Promise<void>((resolve) =>
                  requestAnimationFrame(() => resolve()),
                );
                const start = performance.now();
                const state = get();
                gl.render(state.scene, state.camera);
                context.finish();
                if (i >= 3) samples.push(performance.now() - start);
              }
              samples.sort((a, b) => a - b);
              const extension = context.getExtension(
                "WEBGL_debug_renderer_info",
              );
              return {
                frames: samples.length,
                p95_ms: samples[Math.ceil(samples.length * 0.95) - 1],
                draw_calls: gl.info.render.calls,
                triangles: gl.info.render.triangles,
                textures: gl.info.memory.textures,
                renderer: extension
                  ? context.getParameter(extension.UNMASKED_RENDERER_WEBGL)
                  : context.getParameter(context.RENDERER),
                canvas: [gl.domElement.width, gl.domElement.height],
                measurement:
                  "render plus GPU finish; static exact frame; three warmup renders",
              };
            };
          }}
          frameloop="demand"
          dpr={[1, 1.5]}
          camera={{ fov: 40, near: 1, far: 2000 }}
          gl={{
            preserveDrawingBuffer: true,
            antialias: true,
            localClippingEnabled: true,
          }}
        >
          <color attach="background" args={[light ? "#e5e9f1" : "#090d20"]} />
          <ambientLight intensity={light ? 1.4 : 0.55} />
          <directionalLight
            position={[140, 230, 200]}
            intensity={3.2}
            color="#e1eaff"
          />
          <directionalLight
            position={[-180, 20, -80]}
            intensity={4}
            color="#669ad7"
          />
          <pointLight
            position={[130, -60, 70]}
            intensity={9000}
            color="#eeab70"
          />
          <Cells
            cells={displayCells}
            view={view}
            onSelect={onSelect}
            light={light}
          />
          {view.opacity > 0 && (
            <Field
              frame={displayFrame}
              data={data}
              opacity={view.opacity}
              section={view.section}
              maximum={view.fieldMaximum}
              steps={frame.cells.length > 2000 ? 24 : 48}
            />
          )}
          {selected && (
            <mesh position={selected.position}>
              <sphereGeometry args={[35, 36, 24]} />
              <meshBasicMaterial
                color="#61dcca"
                wireframe
                transparent
                opacity={0.16}
              />
            </mesh>
          )}
          <Camera
            view={view}
            ready={ready}
            target={
              view.preset === "Neighborhood" && selected
                ? selected.position
                : [0, 0, 0]
            }
          />
        </Canvas>
      )}
    </div>
  );
}
