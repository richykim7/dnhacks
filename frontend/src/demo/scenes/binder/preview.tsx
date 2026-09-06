import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import BinderDemo from './BinderDemo';

function Preview() {
  const query = new URLSearchParams(location.search);
  const [time, setTime] = useState(Number(query.get('time') ?? 0));
  const [playing, setPlaying] = useState(false);
  const reduced = query.get('reducedMotion') === '1';
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
    // Capture playback origin only when the play state changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);
  useEffect(() => {
    const set = (event: Event) => { setPlaying(false); setTime((event as CustomEvent<number>).detail); };
    window.addEventListener('binder-time', set);
    return () => window.removeEventListener('binder-time', set);
  }, []);
  return <main style={{ height: '100%', position: 'relative' }}>
    <BinderDemo time={time} reducedMotion={reduced} />
    <header style={{ position: 'absolute', top: '7%', left: '6%', pointerEvents: 'none' }}>
      <div style={{ color: '#67e8f9', fontSize: 12, letterSpacing: '.25em', marginBottom: 22 }}>MOLECULAR ENCOUNTERS / 01</div>
      <h1 style={{ fontWeight: 400, fontSize: 'clamp(28px,3vw,58px)', letterSpacing: '-.045em', margin: 0 }}>A meeting at the surface.</h1>
      <p style={{ color: '#9bb2bf', fontSize: 16, lineHeight: 1.7 }}>A protein in motion. A partner finds its place.</p>
    </header>
    <div style={{ position: 'absolute', left: '6%', bottom: '11%', color: '#a9c6d0', fontSize: 13, letterSpacing: '.12em' }}>
      <span style={{ color: '#67e8f9' }}>●</span> PROTEIN &nbsp;&nbsp;&nbsp; <span style={{ color: '#fb8c82' }}>●</span> BINDER
    </div>
    <footer style={{ position: 'absolute', left: '6%', right: '6%', bottom: '5%', display: 'flex', alignItems: 'center', gap: 20 }}>
      <span style={{ color: '#8fa4b1', fontSize: 12, flex: 1 }}>ILLUSTRATIVE CHOREOGRAPHY · NO EXPERIMENTAL RESULT</span>
      {!query.has('capture') && <><button onClick={() => { if (time >= 18) setTime(0); setPlaying(!playing); }}>{playing ? 'Pause' : 'Play'}</button><button onClick={() => { setPlaying(false); setTime(0); }}>Reset</button><input aria-label="Scene time" type="range" min="0" max="18" step=".01" value={time} onChange={e => { setPlaying(false); setTime(Number(e.target.value)); }} /></>}
      <span style={{ color: '#a9c6d0', fontSize: 12, fontVariantNumeric: 'tabular-nums' }}>{time.toFixed(1).padStart(4, '0')} / 18 s</span>
    </footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<Preview />);
