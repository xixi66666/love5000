import React, {createContext, useContext} from 'react';
import {
  AbsoluteFill, Audio, Freeze, Img, OffthreadVideo, Sequence, interpolate,
  spring, useCurrentFrame, useVideoConfig, staticFile,
} from 'remotion';
import type {Cue, DailyProps, Scene} from './types';
import defaults from './template-defaults.json';

const Theme = createContext(defaults);
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const assetUrl = (src: string) => /^(https?:\/\/|blob:|data:|\/)/.test(src) ? src : staticFile(src);

// 分镜变化只调整画面，不插入片头帧，也不改变配音与字幕的原始时间轴。
export const sceneBeatFrames = (duration: number, fps: number) => Math.max(1, Math.min(fps * 3, Math.floor(duration / 3)));
export const sceneStage = (frame: number, duration: number, fps: number) => Math.min(2, Math.floor(frame / sceneBeatFrames(duration, fps)));
export const activeCaption = (cues: Cue[], seconds: number) => cues.find(cue => cue.start <= seconds && cue.end > seconds);
export const sourceFrame = (frame: number, start: number, duration?: number) =>
  Math.min(Math.max(0, frame - start), duration === undefined ? Infinity : Math.max(0, duration - 1));
export function summaryExcerpt(summary: string, limit = 82) {
  const chars = Array.from(summary.trim());
  return chars.length > limit ? `${chars.slice(0, limit).join('').replace(/[，、；：\s]+$/u, '')}…` : summary.trim();
}

const textUnits = (text: string) => Array.from(text).reduce((sum, char) =>
  sum + (/\s/u.test(char) ? 0.3 : /[\u0000-\u00ff]/u.test(char) ? 0.56 : 1), 0);

// 仅在同一条真实 cue 内排版；不分摊时间、不截字、不伪造逐字高亮。
export function captionLayout(text: string, width: number, preferredSize: number) {
  const clean = text.replace(/\s+/gu, ' ').trim();
  const chars = Array.from(clean);
  if (textUnits(clean) * preferredSize <= width) return {lines: [clean], fontSize: preferredSize};
  let split = 1;
  let best = Infinity;
  for (let i = 1; i < chars.length; i++) {
    const left = chars.slice(0, i).join('');
    const right = chars.slice(i).join('');
    const insideWord = /[a-z0-9]$/i.test(left) && /^[a-z0-9]/i.test(right);
    const badPunctuation = /^[，。！？、：；,.!?;:]/u.test(right);
    const cost = Math.max(textUnits(left), textUnits(right)) + (insideWord ? 3 : 0) + (badPunctuation ? 3 : 0);
    if (cost < best) {best = cost; split = i;}
  }
  const lines = [chars.slice(0, split).join('').trim(), chars.slice(split).join('').trim()];
  return {lines, fontSize: Math.min(preferredSize, Math.floor(width / Math.max(...lines.map(textUnits))))};
}

const Caption: React.FC<{scene: Scene}> = ({scene}) => {
  const theme = useContext(Theme);
  const {fps, width} = useVideoConfig();
  const cue = activeCaption(scene.captions, useCurrentFrame() / fps);
  if (!cue) return null;
  const layout = captionLayout(cue.text, width - 64 - theme.safeRight - 48, theme.captionSize);
  return <div style={{position: 'absolute', bottom: theme.captionBottom, left: 64, right: theme.safeRight,
    display: 'flex', justifyContent: 'center', pointerEvents: 'none'}}>
    <div style={{maxWidth: '100%', padding: '16px 24px', background: '#101618f2', borderRadius: 12,
      color: '#ffffff', fontSize: layout.fontSize, lineHeight: 1.32, fontWeight: 800,
      textAlign: 'center', textShadow: '0 2px 4px #0008', whiteSpace: 'pre', letterSpacing: 0}}>
      {layout.lines.join('\n')}
    </div>
  </div>;
};

const ProjectScene: React.FC<{scene: Scene; day: string; number: number; total: number}> = ({scene, day, number, total}) => {
  const theme = useContext(Theme);
  const {accent, background, foreground} = theme;
  const frame = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const beat = sceneBeatFrames(scene.durationInFrames, fps);
  const stage = sceneStage(frame, scene.durationInFrames, fps);
  const stageFrame = frame - stage * beat;
  const enter = spring({frame, fps, config: {damping: 24, stiffness: 140}});
  const reveal = interpolate(stageFrame, [0, 12], [0, 1], clamp);
  const outgoing = interpolate(frame, [Math.max(0, scene.durationInFrames - 7), scene.durationInFrames], [1, 0], clamp);
  const heading = scene.heading.includes('/') ? scene.heading.split('/').slice(1).join('/') : scene.heading;
  const owner = scene.heading.includes('/') ? scene.heading.split('/')[0] : theme.brand;
  const hasProject = scene.heading.includes('/');
  const excerpt = summaryExcerpt(scene.summary, stage === 2 ? 76 : 94);
  const abbreviated = excerpt !== scene.summary.trim();
  const compact = stage > 0;
  const mediaTop = stage === 0 ? theme.mediaTop : stage === 1 ? theme.mediaTop - 220 : theme.mediaTop - 160;
  const textWidth = 1080 - 64 - theme.safeRight;
  const titleSize = Math.min(compact ? theme.headlineSize * 0.64 : theme.headlineSize,
    heading.length > 30 ? 58 : heading.length > 20 ? 68 : theme.headlineSize,
    textWidth * (compact ? 1.7 : 2.4) / Math.max(1, textUnits(heading)));
  const captionTop = height - theme.captionBottom - theme.captionSize * 2.64 - 32;
  // 演示镜头横向铺满画幅，横屏素材始终 contain，不为填满竖屏而裁掉文字。
  const mediaHeight = Math.max(280, Math.min(stage === 1 ? 960 : stage === 2 ? 680 : 610,
    captionTop - mediaTop - (stage === 2 ? 280 : stage === 0 ? 120 : 60)));
  const briefSize = stage === 1 ? 52 : 44;
  const briefLines = Math.ceil(textUnits(excerpt) * briefSize / (stage === 1 ? 1000 : textWidth - 80));
  const fittedBriefSize = Math.min(briefSize, (mediaHeight - 180) / Math.max(1, briefLines) / 1.4);
  const sourceEnded = scene.asset?.kind === 'video' && scene.asset.durationInFrames !== undefined
    && frame - beat >= scene.asset.durationInFrames;
  const summaryTop = mediaTop + mediaHeight + 34;
  const summarySize = excerpt.length > 65 ? 39 : 45;
  const availableSummary = Math.max(100, captionTop - summaryTop - 26);
  return <AbsoluteFill style={{backgroundColor: background, color: foreground,
    fontFamily: 'DailyCJK, "Microsoft YaHei", "Noto Sans CJK SC", sans-serif', overflow: 'hidden'}}>
    <div style={{position: 'absolute', left: 64, right: theme.safeRight, top: 142,
      display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 24,
      paddingBottom: 22, borderBottom: `2px solid ${foreground}`, fontSize: 24, fontWeight: 800}}>
      <span>{theme.brand}<span style={{color: accent}}> / DAILY</span></span><span style={{fontSize: 22}}>{day}</span>
    </div>
    <div style={{position: 'absolute', top: 234, left: 64, right: theme.safeRight,
      transform: `translateY(${(1 - enter) * 40 * theme.motion}px)`, opacity: 0.35 + enter * 0.65}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 20}}>
        <span style={{background: accent, color: '#101618', padding: '8px 14px', fontSize: compact ? 24 : 30,
          fontWeight: 900}}>{scene.label}</span>
        <span style={{fontSize: 24, fontWeight: 700, opacity: 0.72, overflowWrap: 'anywhere'}}>{owner}</span>
        {compact && scene.growth !== undefined && <span style={{marginLeft: 'auto', fontSize: 25, fontWeight: 800,
          whiteSpace: 'nowrap'}}>+{scene.growth.toLocaleString('en-US')} Star</span>}
      </div>
      <div style={{fontSize: titleSize, lineHeight: 1.14, fontWeight: 900, marginTop: compact ? 18 : 26,
        letterSpacing: '-0.025em', overflowWrap: 'anywhere'}}>{heading}</div>
      {!compact && <div style={{fontSize: 27, fontWeight: 600, marginTop: 24, lineHeight: 1.45, opacity: 0.72}}>
        {scene.asset ? '项目来源素材 · 接下来直接看画面' : hasProject ? '项目资料解读 · 当前未提供演示素材' : theme.tagline}
      </div>}
    </div>
    <div style={{position: 'absolute', top: mediaTop, left: stage === 1 ? 0 : 64,
      right: stage === 1 ? 0 : theme.safeRight, height: mediaHeight, background: '#101618', overflow: 'hidden',
      transform: `translateY(${(1 - reveal) * 18 * theme.motion}px)`, opacity: 0.6 + reveal * 0.4}}>
      {scene.asset ? <>
        <div style={{position: 'absolute', inset: '0 0 66px', overflow: 'hidden'}}>
          {scene.asset.kind === 'video'
            ? <Freeze frame={sourceFrame(frame, beat, scene.asset.durationInFrames)}>
                <OffthreadVideo src={assetUrl(scene.asset.src)} muted style={{width: '100%', height: '100%', objectFit: 'contain'}} />
              </Freeze>
            : <Img src={assetUrl(scene.asset.src)} style={{width: '100%', height: '100%', objectFit: 'contain',
              transform: `scale(${interpolate(frame, [0, scene.durationInFrames], [0.975, 1], clamp)})`}} />}
        </div>
        <div style={{position: 'absolute', bottom: 0, left: stage === 1 ? 64 : 20,
          right: stage === 1 ? theme.safeRight : 20, height: 66, display: 'flex', flexDirection: 'column',
          justifyContent: 'center', color: '#fff', gap: 4}}>
          <span style={{fontSize: 18, fontWeight: 700, opacity: 0.72}}>
            {scene.asset.kind === 'image' ? '项目来源图片' : frame < beat ? '项目演示 · 首帧预览' : sourceEnded ? '项目演示 · 已播放完毕，保留末帧' : '项目演示 · 原始素材'}
          </span>
          <span style={{fontSize: 18, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', lineHeight: 1.2}}>{scene.asset.source}</span>
        </div>
      </> : <div style={{padding: '48px 40px', color: '#ffffff'}}>
        <div style={{fontSize: 23, opacity: 0.7, fontWeight: 700}}>{hasProject ? abbreviated ? '资料摘要 · 节选' : '资料摘要' : theme.brand}</div>
        <div style={{fontSize: fittedBriefSize, fontWeight: 800, lineHeight: 1.4,
          marginTop: 26, overflowWrap: 'anywhere'}}>{excerpt}</div>
        <div style={{position: 'absolute', bottom: 32, left: 40, right: 40, fontSize: 22, opacity: 0.75}}>
          {hasProject ? '未提供实机演示 · 本画面仅展示已收集的项目资料' : '内容与数据以本期来源为准'}
        </div>
      </div>}
    </div>
    {scene.asset && stage === 2 && <div style={{position: 'absolute', top: summaryTop, left: 64,
      right: theme.safeRight, transform: `translateY(${(1 - reveal) * 16 * theme.motion}px)`, opacity: reveal}}>
      <div style={{color: foreground, opacity: 0.65, fontSize: 22, fontWeight: 700, marginBottom: 14}}>{abbreviated ? '资料摘要 · 节选' : '资料摘要'}</div>
      <div style={{fontSize: Math.min(summarySize, availableSummary / Math.max(1,
        Math.ceil(textUnits(excerpt) * summarySize / (1080 - 64 - theme.safeRight))) / 1.35),
        fontWeight: 750, lineHeight: 1.35, overflowWrap: 'anywhere'}}>{excerpt}</div>
    </div>}
    {stage === 0 && <div style={{position: 'absolute', top: mediaTop + mediaHeight + 34, left: 64, right: theme.safeRight}}>
      {scene.growth !== undefined ? <div style={{fontSize: 34, fontWeight: 800}}>
        <span style={{color: foreground, fontSize: 56, letterSpacing: '-0.025em'}}>+{scene.growth.toLocaleString('en-US')}</span>
        <span style={{marginLeft: 18, fontSize: 27}}>今日新增 Star</span>
      </div> : <div style={{fontSize: 31, fontWeight: 800}}>{theme.tagline}</div>}
    </div>}
    <div style={{position: 'absolute', bottom: 224, left: 64, right: theme.safeRight,
      fontSize: 21, opacity: 0.7, display: 'flex', justifyContent: 'space-between', gap: 24}}>
      <span>GitHub 来源 · AI 配音</span><span>{String(number + 1).padStart(2, '0')} / {String(total).padStart(2, '0')}</span>
    </div>
    <div style={{position: 'absolute', left: 64, right: theme.safeRight, bottom: 198, height: 3,
      background: `${foreground}25`}}><div style={{height: '100%', width: `${Math.min(1, frame / Math.max(1, scene.durationInFrames - 1)) * 100}%`, background: accent}} /></div>
    <Caption scene={scene} />
    <AbsoluteFill style={{backgroundColor: background, opacity: 1 - outgoing, pointerEvents: 'none'}} />
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
