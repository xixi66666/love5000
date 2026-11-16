/** 真实 Quartz 冒烟：只使用临时构造笔记，验证双链、Bases、搜索索引与活动 HTML 清理。 */
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';

const moduleRoot=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const fixture=await fs.mkdtemp(path.join(moduleRoot,'.runtime','quartz-check-'));
const source=path.join(fixture,'source'),output=path.join(fixture,'site');
await fs.mkdir(source,{recursive:true});
await fs.writeFile(path.join(source,'index.md'),'---\ntitle: 测试资料库\n---\n\n[[构造记录]]\n\n![[资料视图.base]]\n');
await fs.writeFile(path.join(source,'构造记录.md'),'---\ntitle: 构造记录\ndomain: work\n---\n\n[[index]]\n\n<script>window.PRIVATE_XSS=true</script>\n<img src=x onerror="window.PRIVATE_XSS=true">\n');
await fs.writeFile(path.join(source,'资料视图.base'),'filters: \'file.ext == "md"\'\nformulas:\n  note: \'link(file.path, if(title, title, file.name))\'\nviews:\n  - type: table\n    name: 全部记录\n    order: [formula.note, domain]\n');
const result=spawnSync(process.execPath,['quartz/bootstrap-cli.mjs','build','-d',source,'-o',output,'--concurrency','1'],{cwd:path.join(moduleRoot,'quartz'),encoding:'utf8',timeout:180000,windowsHide:true});
assert.equal(result.status,0,result.stderr||result.stdout);
const html=await fs.readFile(path.join(output,'构造记录.html'),'utf8');
assert.ok(!/<script[^>]*>\s*window\.PRIVATE_XSS/i.test(html),'不得执行原笔记脚本');
assert.ok(!/\sonerror\s*=/i.test(html),'不得保留事件处理属性');
assert.ok(!/<script[^>]+src="https?:/i.test(html),'不得加载远程脚本');
assert.ok(html.includes('我的长期资料库'));
const index=JSON.parse(await fs.readFile(path.join(output,'static/contentIndex.json'),'utf8'));
assert.ok(index['构造记录']);assert.ok(index.index.links.includes('构造记录'));
const base=await fs.readFile(path.join(output,'资料视图.base.html'),'utf8');
assert.ok(base.includes('bases-table')&&base.includes('构造记录'),'必须实际生成 Bases 表格与记录');
await assert.rejects(fs.access(path.join(output,'构造记录.md')));
for (const filename of await fs.readdir(path.join(output,'static/scripts'))) {
  const script=await fs.readFile(path.join(output,'static/scripts',filename),'utf8');
  assert.ok(!script.includes('https://cdn.jsdelivr.net/npm/d3'),'图谱 D3 必须本地加载');
  assert.ok(!script.includes('https://cdn.jsdelivr.net/npm/pixi.js'),'图谱 Pixi 必须本地加载');
}
await fs.access(path.join(output,'static/vendor/pixi-csp.js'));
console.log('Quartz 5.1: 笔记、双链、Bases、搜索索引、HTML 清理和本地脚本验证通过。');
console.log('构造产物：'+output);
