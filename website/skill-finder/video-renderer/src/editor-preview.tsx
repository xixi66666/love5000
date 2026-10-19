import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Player} from '@remotion/player';
import {DailyVideo} from './video';
import {RenderDemo} from './demo';
import type {DailyProps} from './types';

class PreviewBoundary extends React.Component<React.PropsWithChildren, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() {return {failed: true};}
  componentDidCatch(error: Error) {window.parent.postMessage({kind: 'sf-template-error', message: error.message.slice(0, 400)}, '*');}
  render() {return this.state.failed ? <p style={{padding: 24}}>模板运行失败，请检查源码后重新预览。</p> : this.props.children;}
}

const Preview = () => {
  const [data, setData] = useState<{props: DailyProps; demo: boolean} | null>(null);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.source !== window.parent || event.data?.kind !== 'sf-template-props') return;
      if (!Array.isArray(event.data.props?.scenes)) return;
      setData({props: event.data.props, demo: event.data.demo === true});
    };
    window.addEventListener('message', receive);
    window.parent.postMessage({kind: 'sf-template-ready'}, '*');
    return () => window.removeEventListener('message', receive);
  }, []);
  if (!data) return <p style={{padding: 24}}>正在连接模板预览…</p>;
  return <PreviewBoundary><div style={{height: '100vh', display: 'flex', alignItems: 'center'}}>
    {data.demo ? <Player component={RenderDemo} durationInFrames={180} fps={30}
      compositionWidth={1080} compositionHeight={720} controls style={{width: '100%'}} />
      : <Player component={DailyVideo} inputProps={data.props} durationInFrames={Math.max(1,
        data.props.scenes.reduce((sum, scene) => sum + scene.durationInFrames, 0))}
        fps={30} compositionWidth={1080} compositionHeight={1920} controls loop
        style={{width: '100%', maxHeight: '100vh'}} />}
  </div></PreviewBoundary>;
};
createRoot(document.getElementById('root')!).render(<Preview />);
