import re

import httpx

from services import model_hub
from services import _model_properties as model_properties

SYSTEM_PROMPT = "You are a CSS/XPath selector repair expert. Given a broken selector, the action type, and page HTML context, suggest a corrected selector. Respond with ONLY the corrected selector — no explanation, no markdown."

async def heal_selector(
    broken_selector: str,
    action_type: str,
    page,
) -> str | None:
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

    route = model_properties.ModelProperties.load().route("scrapling-ui")
    if route is None or not route.provider.api_key:
        raise RuntimeError("模型未配置：请在项目根目录 model.properties 填写 service.scrapling-ui 与对应 api-key。")
    payload = {
        "model": route.model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
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
