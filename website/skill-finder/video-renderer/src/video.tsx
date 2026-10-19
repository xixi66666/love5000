import React, {createContext, useContext} from 'react';
import {
  AbsoluteFill, Audio, Img, Loop, OffthreadVideo, Sequence, interpolate,
  spring, useCurrentFrame, useVideoConfig, staticFile,
} from 'remotion';
import type {DailyProps, Scene} from './types';
import defaults from './template-defaults.json';

const Theme = createContext(defaults);
const easing = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const assetUrl = (src: string) => /^(https?:\/\/|blob:|data:|\/)/.test(src) ? src : staticFile(src);

const Caption: React.FC<{scene: Scene}> = ({scene}) => {
  const theme = useContext(Theme);
  const {background: paper, foreground: ink} = theme;
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const cue = scene.captions.find((item) => item.start <= time && item.end > time);
  if (!cue) return null;
  // 以真实词/句边界换页，不用动画伪造逐字时间戳。
  return <div style={{position: 'absolute', bottom: theme.captionBottom, left: 74, right: theme.safeRight,
    textAlign: 'center', fontSize: theme.captionSize, lineHeight: 1.35, fontWeight: 800,
    color: paper, textShadow: '0 3px 8px #000', wordBreak: 'break-word'}}>
    <span style={{backgroundColor: ink, padding: '9px 18px', boxDecorationBreak: 'clone'}}>{cue.text}</span>
  </div>;
};

const ProjectScene: React.FC<{scene: Scene; day: string; number: number; total: number}> = ({scene, day, number, total}) => {
  const theme = useContext(Theme);
  const {accent: orange, background: paper, foreground: ink} = theme;
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 22, stiffness: 130}});
  const phase = Math.min(2, Math.floor(frame / Math.max(fps * 3, scene.durationInFrames / 3)));
  const heading = scene.heading.includes('/') ? scene.heading.split('/').slice(1).join('/') : scene.heading;
  const owner = scene.heading.includes('/') ? scene.heading.split('/')[0] : theme.brand;
  const growth = Math.round((scene.growth ?? 0) * interpolate(frame, [8, 45], [0, 1], easing));
  const lift = interpolate(enter, [0, 1], [75 * theme.motion, 0]);
  const progress = Math.min(1, frame / scene.durationInFrames);
  return <AbsoluteFill style={{backgroundColor: paper, color: ink, fontFamily: 'DailyCJK, "Microsoft YaHei", "Noto Sans CJK SC", sans-serif', overflow: 'hidden'}}>
    <AbsoluteFill style={{backgroundImage: 'radial-gradient(#10161818 1px, transparent 1px)', backgroundSize: '22px 22px', opacity: 0.6}} />
    <div style={{position: 'absolute', top: -160, right: -240, width: 900, height: 900,
      border: '1px solid #10161826', borderRadius: '50%', transform: `rotate(${frame / 12 * theme.motion}deg)`}} />
    <div style={{position: 'absolute', left: 72, right: theme.safeRight, top: 150, display: 'flex', justifyContent: 'space-between',
      borderBottom: `3px solid ${ink}`, paddingBottom: 24, fontSize: 25, fontWeight: 800, letterSpacing: 3}}>
      <span>{theme.brand}<span style={{color: orange}}> / DAILY</span></span><span>{day}</span>
    </div>
    <div style={{position: 'absolute', top: 248, left: 70, right: theme.safeRight, transform: `translateY(${lift}px)`, opacity: enter}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 22}}>
        <span style={{background: orange, color: '#fff', padding: '9px 17px', fontSize: 34, fontWeight: 900}}>{scene.label}</span>
        <span style={{fontSize: 25, letterSpacing: 2, fontWeight: 700, color: '#626b6e'}}>{owner}</span>
      </div>
      <div style={{fontSize: heading.length > 28 ? theme.headlineSize * 0.775 : theme.headlineSize, lineHeight: 1.12, fontWeight: 900,
        marginTop: 26, letterSpacing: -3, overflowWrap: 'anywhere'}}>
        {heading.split('，').map((line, i) => <div key={i}>{line}</div>)}
      </div>
    </div>
    <div style={{position: 'absolute', top: theme.mediaTop, left: 72, right: theme.safeRight, height: 625,
      background: ink, overflow: 'hidden', boxShadow: '18px 18px 0 #10161818',
      transform: `translateY(${lift / 2}px)`}}>
      <div style={{height: 53, borderBottom: '1px solid #ffffff22', color: '#bcc4c6', display: 'flex',
        alignItems: 'center', padding: '0 24px', fontSize: 21, gap: 9}}>
        {[orange, '#d9bf63', '#9ac5a1'].map(c => <i key={c} style={{width: 11, height: 11, borderRadius: '50%', background: c}} />)}
        <span style={{marginLeft: 15}}>{scene.asset ? '项目素材 / SOURCE' : '项目资料 / BRIEF'}</span>
      </div>
      {scene.asset ? <div style={{height: 572, overflow: 'hidden', position: 'relative'}}>
        {scene.asset.kind === 'video'
          ? <Loop durationInFrames={scene.asset.durationInFrames ?? scene.durationInFrames}>
              <OffthreadVideo src={assetUrl(scene.asset.src)} muted style={{width: '100%', height: '100%', objectFit: 'contain'}} />
            </Loop>
          : <Img src={assetUrl(scene.asset.src)} style={{width: '100%', height: '100%', objectFit: 'contain',
            transform: `scale(${interpolate(frame, [0, scene.durationInFrames], [1, 1.09], easing)})`}} />}
        <div style={{position: 'absolute', bottom: 15, left: 20, right: 20, color: '#fff', fontSize: 19,
          background: '#101618cc', padding: 8, overflowWrap: 'anywhere'}}>{scene.asset.source}</div>
      </div> : scene.heading.includes('/') ? <div style={{padding: '48px 40px', color: paper}}>
        <div style={{fontSize: 22, color: '#b9c2c5', letterSpacing: 4}}>{['WHAT IT DOES', 'WHY IT MATTERS', 'TRY IT YOURSELF'][phase]}</div>
        <div style={{fontSize: 48, fontWeight: 800, lineHeight: 1.35, marginTop: 27}}>{scene.summary.slice(0, 100)}</div>
        <div style={{position: 'absolute', bottom: 25, fontSize: 21, color: '#c1cbce'}}>资料解读 · 未提供实机演示</div>
      </div> : <div style={{padding: '35px 40px', color: paper}}>
        <div style={{fontSize: 22, color: '#b9c2c5', letterSpacing: 4}}>FROM SIGNAL TO ACTION</div>
        {['看用途', '看效果', '看限制'].map((item, index) => <div key={item}
          style={{fontSize: 62, fontWeight: 900, marginTop: 24, display: 'flex', gap: 24,
            transform: `translateX(${phase === index ? 14 : 0}px)`, color: phase === index ? orange : paper}}>
          <span style={{fontSize: 26, alignSelf: 'center', opacity: 0.55}}>0{index + 1}</span>{item}
        </div>)}
        <div style={{marginTop: 22, fontSize: 24, lineHeight: 1.5, color: '#c1cbce'}}>{scene.summary}</div>
      </div>}
    </div>
    <div style={{position: 'absolute', left: 72, top: 1305, right: theme.safeRight}}>
      {scene.growth !== undefined ? <div style={{display: 'flex', alignItems: 'baseline', gap: 20}}>
        <span style={{fontSize: 88, fontWeight: 900, letterSpacing: -4, color: orange}}>+{growth.toLocaleString('en-US')}</span>
        <span style={{fontSize: 28, fontWeight: 700}}>今日 Star</span>
      </div> : <div style={{fontSize: 45, fontWeight: 800}}>{theme.tagline}</div>}
    </div>
    <div style={{position: 'absolute', bottom: 220, left: 72, right: theme.safeRight, fontSize: 22,
      color: '#5a6569', display: 'flex', justifyContent: 'space-between'}}>
      <span>GitHub 来源 · AI 配音</span><span>{String(number + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}</span>
    </div>
    <div style={{position: 'absolute', left: 0, bottom: 195, height: 7, width: `${progress * 100}%`, background: orange}} />
    <Caption scene={scene} />
    {scene.audio && <Audio src={assetUrl(scene.audio)} />}
  </AbsoluteFill>;
};

export const DailyVideo: React.FC<DailyProps> = ({day, scenes, font, theme = defaults}) => {
  let offset = 0;
  return <Theme.Provider value={theme}><AbsoluteFill>
    {font && <style>{`@font-face {font-family: DailyCJK; src: url('${assetUrl(font)}'); font-weight: 100 900;}`}</style>}
    {scenes.map((scene, index) => {
      const from = offset;
      offset += scene.durationInFrames;
      return <Sequence key={index} from={from} durationInFrames={scene.durationInFrames}>
        <ProjectScene scene={scene} day={day} number={index} total={scenes.length} />
      </Sequence>;
    })}
  </AbsoluteFill></Theme.Provider>;
};
