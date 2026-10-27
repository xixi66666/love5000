import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { dailyApi } from '@/api/dailyReports'
import type { TemplateDocument, TemplatePreview } from '@/api/templates'
import TemplateEditor from '@/components/TemplateEditor.vue'

function document(): TemplateDocument {
  const theme = {accent:'#ff6038', background:'#f4f1e9', foreground:'#101618', brand:'SKILL FINDER', tagline:'先看用途',
    headlineSize:80, captionSize:48, captionBottom:310, safeRight:150, mediaTop:610, motion:1}
  return {revision:'a'.repeat(64), theme, defaults:{...theme}, versions:[], fields:[
    {key:'accent',kind:'color',label:'强调色'}, {key:'captionSize',kind:'number',label:'字幕字号',min:28,max:68,step:1},
  ], sources:[{path:'src/video.tsx', code:'export const DailyVideo = () => <div>original</div>', editable:true},
    {path:'src/demo.tsx',code:'export const RenderDemo = () => null',editable:true},
    {path:'src/types.ts',code:'export type DailyProps = {}',editable:true},
    {path:'src/root.tsx',code:'// fixed video specification',editable:false}]}
}
const preview = (): TemplatePreview => ({id:'b'.repeat(32),revision:'c'.repeat(64),created_at:'2026-10-19T16:00:00+08:00',
  props:{day:'模板预览',theme:document().theme,scenes:[]}})
let wrappers: ReturnType<typeof mount>[]
beforeEach(() => {
  wrappers=[]
  vi.stubGlobal('isSecureContext',true)
  vi.spyOn(dailyApi,'get').mockResolvedValue({data:document()})
  vi.spyOn(dailyApi,'post').mockResolvedValue({data:preview()})
})
afterEach(() => {wrappers.forEach(wrapper=>wrapper.unmount());vi.restoreAllMocks();vi.unstubAllGlobals()})
async function open(key='editor-test-only', engine: 'remotion' | 'hyperframes' = 'remotion') {
  const wrapper=mount(TemplateEditor,{props:{adminKey:key, engine}})
  wrappers.push(wrapper);await flushPromises();return wrapper
}
describe('模板编辑器',()=>{
  it('does not read source or compile until the operator supplies a key',async()=>{
    const wrapper=await open('')
    expect(wrapper.text()).toContain('连接模板编辑器')
    expect(dailyApi.get).not.toHaveBeenCalled()
    expect(dailyApi.post).not.toHaveBeenCalled()
  })
  it('compiles a draft into a sandboxed player without enabling it',async()=>{
    const wrapper=await open()
    expect(wrapper.get('iframe').attributes('sandbox')).toBe('allow-scripts')
    expect(dailyApi.post).toHaveBeenCalledWith('/daily-reports/template/preview',expect.objectContaining({expected_revision:'a'.repeat(64)}),expect.anything())
    expect(wrapper.get('[data-testid="save-template"]').attributes('disabled')).toBeDefined()
  })
  it('saves editable source and theme with a revision guard while excluding protected files',async()=>{
    const wrapper=await open()
    const replacement='export const DailyVideo = () => <div>changed</div>'
    await wrapper.get('#template-source').setValue(replacement)
    const changed=document()
    changed.revision='d'.repeat(64);changed.sources[0].code=replacement
    const put=vi.spyOn(dailyApi,'put').mockResolvedValue({data:{...changed,preview:preview()}})
    await wrapper.get('[data-testid="save-template"]').trigger('click');await flushPromises()
    const body=put.mock.calls[0][1] as {sources:Record<string,string>;expected_revision:string}
    expect(body.sources['src/video.tsx']).toBe(replacement)
    expect(body.sources).not.toHaveProperty('src/root.tsx')
    expect(body.expected_revision).toBe('a'.repeat(64))
    expect(wrapper.text()).toContain('新版本已启用')
  })
  it('keeps invalid source in the editor and displays compiler locations',async()=>{
    const wrapper=await open()
    await wrapper.get('#template-source').setValue('broken source')
    vi.mocked(dailyApi.post).mockRejectedValueOnce({isAxiosError:true,response:{status:422,data:{diagnostics:[
      {file:'src/video.tsx',line:9,column:3,message:'Expected expression'},
    ]}}})
    await wrapper.get('[data-testid="compile-template"]').trigger('click');await flushPromises()
    expect(wrapper.get('textarea').element.value).toBe('broken source')
    expect(wrapper.text()).toContain('src/video.tsx:9:3')
    expect(wrapper.text()).toContain('Expected expression')
    expect(wrapper.text()).toContain('草稿未保存')
  })
  it('updates visual parameters in the player without sending the admin key to the frame',async()=>{
    const wrapper=await open()
    const frame=wrapper.get('iframe').element as HTMLIFrameElement
    const post=vi.fn()
    Object.defineProperty(frame,'contentWindow',{value:{postMessage:post},configurable:true})
    await wrapper.findAll('.editing-tabs button')[1].trigger('click')
    await wrapper.get('#theme-accent').setValue('#123456');await flushPromises()
    const payload=post.mock.calls.at(-1)?.[0] as {props:{theme:{accent:string}}}
    expect(payload.props.theme.accent).toBe('#123456')
    expect(JSON.stringify(payload)).not.toContain('editor-test-only')
    expect(wrapper.get('#theme-captionSize').attributes('max')).toBe('68')
  })
  it('edits and saves the exact HyperFrames HTML source with a bound engine',async()=>{
    const hf={...document(),engine:'hyperframes' as const, engine_label:'HyperFrames', current_engine:'hyperframes',sources:[
      {path:'src/template.html',code:'<main>original HTML</main>',editable:true},
      {path:'src/demo.html',code:'<main>demo HTML</main>',editable:true},
    ]}
    vi.mocked(dailyApi.get).mockResolvedValueOnce({data:hf})
    vi.mocked(dailyApi.post).mockResolvedValueOnce({data:{...preview(),engine:'hyperframes'}})
    const wrapper=await open('editor-test-only','hyperframes')
    expect(dailyApi.get).toHaveBeenCalledWith('/daily-reports/template',expect.objectContaining({params:{engine:'hyperframes'}}))
    expect(wrapper.get('iframe').attributes('src')).toContain('/engines/hyperframes/previews/')
    expect(wrapper.get<HTMLTextAreaElement>('#template-source').element.value).toBe('<main>original HTML</main>')
    expect(wrapper.get('iframe').attributes('sandbox')).toBe('allow-scripts')
    await wrapper.get('#template-source').setValue('<main>changed HTML</main>')
    expect(wrapper.get('#template-engine').attributes('disabled')).toBeDefined()
    const put=vi.spyOn(dailyApi,'put').mockResolvedValueOnce({data:{...hf,preview:{...preview(),engine:'hyperframes'}}})
    await wrapper.get('[data-testid="save-template"]').trigger('click');await flushPromises()
    expect(put.mock.calls[0][1]).toMatchObject({engine:'hyperframes',sources:{'src/template.html':'<main>changed HTML</main>'}})
    expect((put.mock.calls[0][1] as {sources: Record<string,string>}).sources).not.toHaveProperty('src/video.tsx')
  })
  it('binds a version restore to the selected engine',async()=>{
    const hf={...document(),engine:'hyperframes' as const,versions:[{revision:'d'.repeat(64),created_at:'2026-10-23T12:00:00+08:00'}],
      sources:[{path:'src/template.html',code:'<main>HTML</main>',editable:true},{path:'src/demo.html',code:'<main>demo</main>',editable:true}]}
    vi.mocked(dailyApi.get).mockResolvedValueOnce({data:hf})
    const wrapper=await open('editor-test-only','hyperframes')
    await wrapper.get('#template-version').setValue('d'.repeat(64))
    vi.mocked(dailyApi.post).mockResolvedValueOnce({data:hf})
    const restore=wrapper.findAll('button').find(button=>button.text()==='恢复此版本')!
    await restore.trigger('click');await flushPromises()
    expect(dailyApi.post).toHaveBeenCalledWith('/daily-reports/template/restore',expect.objectContaining({engine:'hyperframes',revision:'d'.repeat(64)}),expect.anything())
  })
})
