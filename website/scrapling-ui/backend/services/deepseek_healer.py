"""用统一文本模型修复失效的 CSS 选择器。

对外只有一个入口 `heal_selector`：抓一段简化后的页面 HTML 作为上下文，让模型
只回答一个选择器字符串，再把结果清洗成裸选择器返回给 ``/api/ai/heal-selector``。

两条调用路径，顺序固定：

1. 先走统一模型入口（`model_hub.try_chat`）；用户在主页选了模型就走这里。
2. 返回 ``None`` 时才用 ``model.properties`` 里 ``service.scrapling-ui`` 的原配置
   直连 ``/chat/completions``（密钥只在此处从配置读取，不出现在日志与响应里）。

失败行为：模型未配置抛 ``RuntimeError``（消息指向 ``model.properties``）；统一网关
报错时直接抛错、不再回退；原配置路径失败只打印一行不含异常细节的日志并返回
``None``，由路由转成 ``healed_selector: null``。``_model_properties`` 是
``scripts/sync-model-routing.py`` 生成的部署副本，只读，不要在这里改模型读取逻辑。
"""

import re

import httpx

from services import model_hub
from services import _model_properties as model_properties

# 固定提示词：要求「只回答选择器」，否则模型的解释性文字会混进选择器里，
# 正则清洗只能去掉代码围栏，去不掉自然语言。
SYSTEM_PROMPT = "You are a CSS/XPath selector repair expert. Given a broken selector, the action type, and page HTML context, suggest a corrected selector. Respond with ONLY the corrected selector — no explanation, no markdown."

async def heal_selector(
    broken_selector: str,
    action_type: str,
    page,
) -> str | None:
    """请模型给出一个可用的替代选择器。

    Args:
        broken_selector: 当前失效的选择器，会原样放进提示词。
        action_type: 该选择器原本要执行的动作（click/fill/extract 等），
            帮助模型判断目标元素类型。
        page: Playwright ``Page``；用于抓取简化 HTML 上下文，不用它执行动作。

    Returns:
        清洗后的选择器字符串；模型没给出结果、或给出的字符串与入参相同
        （说明没修好）时返回 ``None``。

    Raises:
        RuntimeError: 未配置 ``service.scrapling-ui`` 或缺少 api-key；或走统一模型
            入口时网关失败。消息为面向用户的中文提示，不含密钥与上游细节。
    """
    # 页面上下文：克隆 body 后清掉脚本/样式/图标等噪声，只留前 6000 字符，
    # 既避免超长提示词，也避免把大段内联脚本发给模型。
    page_context = await page.evaluate("""
    () => {
        try {
            let el = document.body;
            if (!el) return '';
            let clone = el.cloneNode(true);
            clone.querySelectorAll('script, style, link, meta, noscript, svg, path, iframe').forEach(n => n.remove());
            let html = clone.innerHTML.substring(0, 6000);
            return html;
        } catch(e) { return ''; }
    }
    """)

    prompt = (
        f"A web scraper failed. The broken selector is: \"{broken_selector}\"\n"
        f"The action being performed: {action_type}\n\n"
        f"Page HTML context (simplified):\n{page_context[:6000]}\n\n"
        "Suggest a corrected CSS selector. Rules:\n"
        "1. Prefer CSS selectors over XPath\n"
        "2. If the element likely changed classes/IDs, use attribute selectors or nth-child\n"
        "3. Use parent/sibling relationships for robustness\n"
        "4. For text-based elements, consider :contains() or attribute-contains selectors\n"
        "5. Respond with ONLY the corrected selector"
    )

    # 原配置只在没有统一模型选择时才用到；api_key 为空说明运维没配，
    # 此时没有任何可用模型，直接给出可操作的配置提示。
    route = model_properties.ModelProperties.load().route("scrapling-ui")
    if route is None or not route.provider.api_key:
        raise RuntimeError("模型未配置：请在项目根目录 model.properties 填写 service.scrapling-ui 与对应 api-key。")
    payload = {
        "model": route.model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        # 温度压到 0.1、输出限 150 token：修复只需一个选择器，不需要创作。
        "temperature": 0.1,
        "max_tokens": 150,
    }
    try:
        data = await model_hub.try_chat(payload)
    except Exception as exc:
        raise RuntimeError("已选模型修复失败，请检查统一模型入口") from exc
    use_hub = data is not None
    try:
        if data is None:
            async with httpx.AsyncClient(timeout=30) as client:
                data = await model_hub.native_chat(
                    client, f"{route.provider.base_url}/chat/completions",
                    route.provider.api_key, payload, timeout=30)
        healed = data["choices"][0]["message"]["content"].strip()
        # 模型仍常把答案包在 ```css 围栏或引号里，逐层削掉再做「是否变化」判断。
        healed = re.sub(r'^```(?:css|xpath)?\s*', '', healed)
        healed = re.sub(r'\s*```$', '', healed)
        healed = healed.strip().strip("'").strip('"')
        if healed and healed != broken_selector:
            return healed
    except Exception as exc:
        if use_hub:
            raise RuntimeError("已选模型修复失败，请检查统一模型入口") from exc
        print("[AI] 选择器修复失败，请检查模型配置")
    return None
