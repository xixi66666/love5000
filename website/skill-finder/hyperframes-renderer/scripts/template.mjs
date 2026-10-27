import {parseHTML} from 'linkedom';
import vm from 'node:vm';

// 模板代码属于管理员受信任源码；此检查同时保护上游编译/媒体探测阶段。
export function inspectTemplate(html, {generated = false, resources = new Set(['gsap.min.js'])} = {}) {
  if (typeof html !== 'string' || Buffer.byteLength(html) > 400000) throw new Error('Template exceeds size limit');
  const {document} = parseHTML(html);
  if (!document.querySelector('[data-composition-id="daily"]')) throw new Error('Template needs daily composition');
  if (document.querySelector('base,iframe,object,embed,form,link,[srcset],[data-composition-src],meta[http-equiv="refresh"]')) {
    throw new Error('Template contains unsupported external content');
  }
  const scripts = [];
  for (const node of document.querySelectorAll('*')) {
    for (const attribute of node.attributes) {
      if (/^on/i.test(attribute.name)) throw new Error('Use the authored script for event handlers');
      if (['src', 'href', 'poster', 'action', 'xlink:href'].includes(attribute.name)) {
        if (!resources.has(attribute.value)) throw new Error('Only frozen manifest resources are allowed');
      }
    }
  }
  for (const node of document.querySelectorAll('script')) {
    if (node.src) {
      if (node.getAttribute('src') !== 'gsap.min.js') throw new Error('Only bundled GSAP script is allowed');
    } else {
      if (node.type && !['text/javascript', 'application/javascript'].includes(node.type)) throw new Error('Unsupported template script type');
      // 只做语法编译，绝不在 Node 中执行模板。
      new vm.Script(node.textContent, {filename: 'template.html'});
      scripts.push(node.textContent);
    }
  }
  for (const node of document.querySelectorAll('style,[style]')) {
    const css = node.localName === 'style' ? node.textContent : node.getAttribute('style');
    if (/@import|\\/i.test(css)) throw new Error('External CSS imports and escaped resource references are disabled');
    for (const match of css.matchAll(/url\(\s*['"]?([^'"\s)]+)['"]?\s*\)/gi)) {
      if (!generated || !resources.has(match[1])) throw new Error('CSS can only use the frozen manifest font');
    }
  }
  return {document, scripts};
}

export function withCsp(html) {
  // 不开放网络、iframe、插件；内联脚本只运行受鉴权保存的作者动画和官方 runtime。
  const policy = "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' data:; media-src 'self'; font-src 'self' data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'";
  return html.replace(/<head[^>]*>/i, head => `${head}<meta http-equiv="Content-Security-Policy" content="${policy}">`);
}
