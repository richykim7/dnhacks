import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { Canvas, useThree, type ThreeEvent } from '@react-three/fiber';
import * as T from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { center, distance, type Atom, type Geometry, type Recipe, type Vec3 } from '@/lib/inhibitor';

function Instances({atoms, color, scale, pick, opacity=1, clip}: {atoms: Atom[]; color:string; scale:number; pick:(id:string)=>void; opacity?:number; clip:T.Plane[]}) {
  const ref=useRef<T.InstancedMesh>(null);
  useLayoutEffect(()=>{const obj=new T.Object3D(); atoms.forEach((a,i)=>{obj.position.fromArray(a.position); obj.scale.setScalar(scale*(a.element==='H'?.6:1)); obj.updateMatrix(); ref.current!.setMatrixAt(i,obj.matrix); const c=a.element==='N'?'#759ee6':a.element==='O'?'#ef908b':a.element==='S'?'#ecd282':color;ref.current!.setColorAt(i,new T.Color(c));}); if(ref.current){ref.current.instanceMatrix.needsUpdate=true; ref.current.computeBoundingSphere();}},[atoms,scale,color]);
  return <instancedMesh ref={ref} args={[undefined,undefined,atoms.length]} onClick={(e:ThreeEvent<MouseEvent>)=>{e.stopPropagation(); if(e.instanceId!==undefined)pick(atoms[e.instanceId].id);}}>
    <sphereGeometry args={[1,16,12]}/><meshStandardMaterial color="white" roughness={.32} metalness={.16} transparent={opacity<1} opacity={opacity} depthWrite={opacity===1} clippingPlanes={clip}/>
  </instancedMesh>;
}
function Bonds({g,indices,color}:{g:Geometry;indices:Set<number>;color:string}){
  const lines=useMemo(()=>{const p:number[]=[]; g.bonds.forEach(([a,b])=>{if(indices.has(a)&&indices.has(b))p.push(...g.atoms[a].position,...g.atoms[b].position);}); return new T.BufferGeometry().setAttribute('position',new T.Float32BufferAttribute(p,3));},[g,indices]);
  useEffect(()=>()=>lines.dispose(),[lines]);
  return <lineSegments geometry={lines}><lineBasicMaterial color={color}/></lineSegments>;
}
function Trace({g,path,clip}:{g:Geometry;path:number[];clip:T.Plane[]}){
 const geometry=useMemo(()=>new T.TubeGeometry(new T.CatmullRomCurve3(path.map(i=>new T.Vector3(...g.atoms[i].position))),path.length*5,.36,7,false),[g,path]);
 useEffect(()=>()=>geometry.dispose(),[geometry]);
 return <mesh geometry={geometry}><meshStandardMaterial color="#d9e4e0" roughness={.38} metalness={.18} clippingPlanes={clip}/></mesh>;
}
function Scene({g,recipe,pick,ack,onCamera}:{g:Geometry;recipe:Recipe;pick:(id:string)=>void;ack:(revision:number,canvas:HTMLCanvasElement)=>void;onCamera:(position:Vec3,target:Vec3)=>void}){
 const {gl,scene,camera,invalidate,size}=useThree(); const orbit=useRef<OrbitControls>(null);
 const atomSet=useMemo(()=>g.atoms.filter(a=>a.model===recipe.model),[g,recipe.model]);
 const ligand=useMemo(()=>atomSet.filter(a=>a.residue_id===recipe.ligand),[atomSet,recipe.ligand]);
 const focus=useMemo(()=>center(ligand.length?ligand:atomSet),[ligand,atomSet]);
 const context=useMemo(()=>atomSet.filter(a=>a.kind==='polymer' && ligand.some(b=>distance(a,b)<6)),[atomSet,ligand]);
 const ligandIndices=useMemo(()=>new Set(g.atoms.flatMap((a,i)=>a.residue_id===recipe.ligand?[i]:[])),[g,recipe.ligand]);
 const clip=useMemo(()=>recipe.clip?[new T.Plane(new T.Vector3(0,0,-1),focus[2]+3)]:[],[recipe.clip,focus]);
 useEffect(()=>{const controls=new OrbitControls(camera,gl.domElement);orbit.current=controls;controls.enableDamping=false;controls.addEventListener('change',()=>invalidate());const end=()=>onCamera(camera.position.toArray() as Vec3,controls.target.toArray() as Vec3);controls.addEventListener('end',end);return()=>controls.dispose();},[camera,gl,invalidate,onCamera]);
 useLayoutEffect(()=>{
   const target=recipe.camera?.target || (recipe.shot==='arrival'?center(atomSet):focus);
   const radius=Math.max(10,...atomSet.map(a=>Math.hypot(...a.position.map((v,i)=>v-target[i]))));
   const dist=recipe.shot==='arrival'?radius*2.8:25;
   const offset=recipe.shot==='oblique'?[.85,.38,.9]:[.2,.22,1.3];
   camera.position.fromArray(recipe.camera?.position || target.map((v,i)=>v+offset[i]*dist) as Vec3);
   camera.up.set(0,1,0);camera.lookAt(...target);orbit.current?.target.fromArray(target);orbit.current?.update();camera.updateProjectionMatrix();invalidate();
 },[recipe.camera,recipe.shot,recipe.ligand,recipe.model,camera,atomSet,focus,invalidate]);
 useEffect(()=>{let cancelled=false; void (async()=>{await document.fonts.ready;await gl.compileAsync(scene,camera);if(cancelled)return;gl.render(scene,camera);gl.getContext().finish();if(!cancelled)ack(recipe.revision,gl.domElement);})();return()=>{cancelled=true;};},[recipe,gl,scene,camera,ack,size]);
 return <>
  <color attach="background" args={['#070f20']}/><ambientLight intensity={.7}/><directionalLight position={[20,45,70]} intensity={2.6} color="#e2efff"/><directionalLight position={[-40,5,-20]} intensity={2} color="#54ccd8"/><pointLight position={[focus[0],focus[1]+8,focus[2]+12]} intensity={120} color="#ffcd87"/>
  {g.backbones.filter(p=>g.atoms[p[0]].model===recipe.model).map((p,i)=><Trace key={i} g={g} path={p} clip={clip}/>)}
  {recipe.style==='luminous' && <Instances atoms={context} color="#77b7b6" scale={1.25} opacity={.13} pick={pick} clip={clip}/>}
  {recipe.style==='matte' && <Instances atoms={context} color="#a4c4c6" scale={.48} pick={pick} clip={clip}/>}
  <Bonds g={g} indices={ligandIndices} color="#ffc77c"/>
  <Instances atoms={ligand} color="#ffbe67" scale={.48} pick={pick} clip={[]}/>
  <Instances atoms={g.atoms.filter(a=>recipe.selected.includes(a.id))} color="#b8f2f3" scale={.65} pick={pick} clip={[]}/>
 </>;
}
export default function InhibitorScene(props:Parameters<typeof Scene>[0]){
 return <Canvas frameloop="demand" dpr={[1,1.5]} camera={{fov:38,near:.1,far:10000}} gl={{antialias:true,preserveDrawingBuffer:true,localClippingEnabled:true}} onCreated={({gl})=>{gl.domElement.setAttribute('aria-label','Interactive inhibitor geometry');gl.domElement.addEventListener('webglcontextlost',e=>e.preventDefault());}}><Scene {...props}/></Canvas>;
}
