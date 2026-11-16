/** 本地化图谱依赖；使用 Pixi 的 CSP 安全实现，不放开 unsafe-eval。 */
import fs from 'node:fs/promises';
import { build } from 'esbuild';
const destination='quartz/static/vendor';
await fs.mkdir(destination,{recursive:true});
await fs.copyFile('node_modules/d3/dist/d3.min.js',`${destination}/d3.min.js`);
await fs.copyFile('node_modules/d3/LICENSE',`${destination}/D3-LICENSE`);
await build({stdin:{contents:'import * as PIXI from "pixi.js"; import "pixi.js/unsafe-eval"; window.PIXI = PIXI;',resolveDir:process.cwd()},bundle:true,format:'iife',platform:'browser',minify:true,outfile:`${destination}/pixi-csp.js`});
await fs.copyFile('node_modules/pixi.js/LICENSE',`${destination}/PIXI-LICENSE`);
console.log('Quartz 图谱本地资源已就绪（D3 + Pixi CSP）。');
