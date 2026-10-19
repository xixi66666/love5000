import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';

// 可复现的本地渲染示例，作为介绍 Remotion 本身的真实输出素材。
export const RenderDemo: React.FC = () => {
  const frame = useCurrentFrame();
  const part = Math.floor(frame / 150) % 3;
  const beat = frame % 150;
  const progress = interpolate(beat, [0, 130], [0, 1], {extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{backgroundColor: '#111b23', color: '#f5f0e8', fontFamily: 'Arial, sans-serif', padding: 50}}>
    <div style={{fontSize: 20, color: '#a6b5c1', letterSpacing: 4}}>LOCAL RENDER / REMOTION</div>
    <div style={{fontSize: 63, fontWeight: 900, letterSpacing: -2, marginTop: 20}}>
      {['DATA → MOTION', 'ONE TEMPLATE.', 'A NEW VIDEO.'][part]}
    </div>
    <div style={{display: 'flex', gap: 25, marginTop: 45, height: 420}}>
      <div style={{background: '#1e303e', flex: 1, padding: 30, border: '1px solid #365063'}}>
        <div style={{fontSize: 20, color: '#a6b5c1'}}>INPUT.JSON</div>
        <pre style={{fontSize: 27, lineHeight: 1.9, color: '#d6e5ed'}}>{`{\n  "title": "${['Build', 'Create', 'Ship'][part]}",\n  "value": ${[72, 94, 100][part]},\n  "color": "coral"\n}`}</pre>
      </div>
      <div style={{background: '#f5f0e8', color: '#111b23', flex: 1, padding: 30, overflow: 'hidden', position: 'relative'}}>
        <div style={{fontSize: 20, fontWeight: 700}}>OUTPUT / 30 FPS</div>
        <div style={{marginTop: 35, fontSize: 72, fontWeight: 900,
          transform: `translateY(${(1 - Math.min(1, beat / 20)) * 70}px)`}}>{['Build', 'Create', 'Ship'][part]}</div>
        <div style={{fontSize: 110, fontWeight: 900, color: '#ff6038'}}>{Math.round([72, 94, 100][part] * progress)}<span style={{fontSize: 36}}>%</span></div>
        <div style={{height: 18, background: '#dfd9cf', marginTop: 15}}><div style={{height: '100%', width: `${progress * 100}%`, background: '#ff6038'}} /></div>
      </div>
    </div>
  </AbsoluteFill>;
};
