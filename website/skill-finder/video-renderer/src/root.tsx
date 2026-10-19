import React from 'react';
import {Composition} from 'remotion';
import {DailyVideo} from './video';
import type {DailyProps} from './types';
import {RenderDemo} from './demo';

const defaults: DailyProps = {
  day: '模板预览', preview: true,
  scenes: [{label: 'AI DAILY', heading: '今天的 AI 工具，先看效果。',
    summary: '传入当天项目、配音与演示素材，生成你的榜单视频。',
    narration: '', durationInFrames: 240, captions: []}],
};

export const Root: React.FC = () => <><Composition
  id="SkillFinderDaily" component={DailyVideo} width={1080} height={1920} fps={30}
  durationInFrames={240} defaultProps={defaults}
  calculateMetadata={({props}) => ({
    durationInFrames: Math.max(1, props.scenes.reduce((sum, scene) => sum + scene.durationInFrames, 0)),
  })}
/>
  <Composition id="RenderDemo" component={RenderDemo} width={1080} height={720} fps={30} durationInFrames={180} />
</>;
