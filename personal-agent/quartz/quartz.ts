import { loadQuartzConfig, loadQuartzLayout } from "./quartz/plugins/loader/config-loader"
import rehypeSanitize, { defaultSchema } from "rehype-sanitize"

const config = await loadQuartzConfig()
// 每次构建由 Java 提供当前 Vault 名称，仅构造本机 Obsidian 打开链接。

// Vault 可包含原始 HTML；清除活动内容，避免私人资料站中的脚本注入。
const schema = {
  ...defaultSchema,
  clobberPrefix: "",
  tagNames: [...(defaultSchema.tagNames ?? []), "button", "select", "option"],
  attributes: {
    ...defaultSchema.attributes,
    button: ["type", "disabled", "value"],
    select: ["name", "disabled"],
    option: ["value", "selected"],
    "*": [...(defaultSchema.attributes?.["*"] ?? []), "className", "data*", "ariaSelected", "ariaPressed", "role", "tabIndex"],
  },
}
config.plugins.transformers.push({
  name: "PrivateVaultSanitize",
  htmlPlugins: () => [[rehypeSanitize, schema]],
  virtualPageHtmlPlugins: () => [[rehypeSanitize, schema]],
})
export default config
export const layout = await loadQuartzLayout()
