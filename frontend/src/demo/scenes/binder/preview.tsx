import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import BinderDemo from './BinderDemo';

function Preview() {
  const query = new URLSearchParams(location.search);
  const [time, setTime] = useState(Number(query.get('time') ?? 0));
  const [playing, setPlaying] = useState(false);
  const reduced = query.get('reducedMotion') === '1';
  const phase = time < 5 ? 'Separate partners' : time < 10.3 ? 'Approach and align' : time < 11.15 ? 'Seat in cleft' : time < 15 ? 'Bound complex · orbit' : 'Bound complex · hold';
  useEffect(() => {
    if (!playing) return;
    const start = performance.now() - time * 1000;
    let frame: number;
    const tick = (now: number) => {
      const t = Math.min(18, (now - start) / 1000);
      setTime(t);
      if (t < 18) frame = requestAnimationFrame(tick); else setPlaying(false);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // The preview owns the clock; capture the playback origin only on play/pause.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);
  useEffect(() => {
    const set = (event: Event) => { setPlaying(false); setTime((event as CustomEvent<number>).detail); };
    window.addEventListener('binder-time', set);
    return () => window.removeEventListener('binder-time', set);
  }, []);
  return <main style={{ height: '100%', position: 'relative', display: 'flex', alignItems: 'stretch' }}>
    <section style={{ width: '64%', height: '100%' }}><BinderDemo time={time} reducedMotion={reduced} /></section>
    <aside style={{ width: '36%', padding: '0 5% 0 2%', alignSelf: 'center' }}>
      <div style={{ color: '#67e8f9', fontSize: 12, letterSpacing: '.16em', marginBottom: 22 }}>ILLUSTRATIVE GEOMETRY</div>
      <h1 style={{ fontWeight: 450, fontSize: 'clamp(22px,2.7vw,48px)', letterSpacing: '-.035em', margin: '0 0 28px' }}>Binder interaction</h1>
      <div style={{ color: '#e7f9fb', fontSize: 20, marginBottom: 32 }}>{phase}</div>
      <p style={{ color: '#a9c0cc', fontSize: 16, lineHeight: 1.8 }}>The smaller binder turns to align with the open cleft, seats between its contact sites, and moves with the protein as one complex.</p>
      <div style={{ color: '#a9c6d0', fontSize: 13, marginTop: 34 }}><span style={{ color: '#67e8f9' }}>●</span> Protein &nbsp;&nbsp; <span style={{ color: '#fb8c82' }}>●</span> Binder</div>
      <p style={{ color: '#839ba9', fontSize: 12, lineHeight: 1.7, marginTop: 32 }}>Choreographed illustration. No measured structure, docking prediction, affinity score or experimental result.</p>
    </aside>
    <footer style={{ position: 'absolute', left: '5%', right: '5%', bottom: '5%', display: 'flex', alignItems: 'center', gap: 20 }}>
      <span style={{ flex: 1, color: '#8da9b9', fontSize: 12 }}>BINDER / V2</span>
      {!query.has('capture') && <><button onClick={() => { if (time >= 18) setTime(0); setPlaying(!playing); }}>{playing ? 'Pause' : 'Play'}</button><button onClick={() => { setPlaying(false); setTime(0); }}>Reset</button><input aria-label="Scene time" type="range" min="0" max="18" step=".01" value={time} onChange={e => { setPlaying(false); setTime(Number(e.target.value)); }} /></>}
      <span style={{ color: '#a9c6d0', fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>{time.toFixed(1).padStart(4, '0')} / 18 s</span>
    </footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<Preview />);
