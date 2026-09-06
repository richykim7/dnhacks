import {describe,it,expect} from "vitest";
import {layoutPoleLabels} from "./labels";
describe("clustered centrosome labels",()=>{
  it("keeps eight coincident projected poles readable without moving their source",()=>{
    const poles=Array.from({length:8},(_,i)=>({id:`C${i+1}`,x:180,y:190}));
    const labels=layoutPoleLabels(poles,390,410);
    expect(labels).toEqual(layoutPoleLabels([...poles].reverse(),390,410));
    for(const [i,p] of labels.entries()){
      expect(Math.abs(p.x-180)>32 || Math.abs(p.y-190)>26).toBe(true);
      expect(p.x).toBeGreaterThanOrEqual(22);expect(p.x).toBeLessThanOrEqual(368);
      expect(p.y).toBeGreaterThanOrEqual(22);expect(p.y).toBeLessThanOrEqual(388);
      for(const q of labels.slice(0,i))expect(Math.abs(p.x-q.x)>=42 || Math.abs(p.y-q.y)>=25).toBe(true);
    }
    expect(poles.every(p=>p.x===180&&p.y===190)).toBe(true);
  });
});
