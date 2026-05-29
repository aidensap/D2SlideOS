import base64
import os
import pandas as pd
from app.config import (
    AICORE_AUTH_URL, AICORE_CLIENT_ID, AICORE_CLIENT_SECRET,
    AICORE_BASE_URL, AICORE_RESOURCE_GROUP, AI_MODEL,
)


def _set_aicore_env():
    os.environ["AICORE_AUTH_URL"] = AICORE_AUTH_URL
    os.environ["AICORE_CLIENT_ID"] = AICORE_CLIENT_ID
    os.environ["AICORE_CLIENT_SECRET"] = AICORE_CLIENT_SECRET
    os.environ["AICORE_BASE_URL"] = AICORE_BASE_URL
    os.environ["AICORE_RESOURCE_GROUP"] = AICORE_RESOURCE_GROUP


def analyze_data(df: pd.DataFrame, lang: str = "en") -> str:
    _set_aicore_env()

    if lang == "zh":
        prompt = f"""你是一位资深业务分析师。以下是报表数据（CSV 格式）：

{df.to_csv(index=False)}

请用纯文本输出，不要使用任何 Markdown 符号（###、**、* 等）。

【关键发现】
1. （数据驱动，带具体数字）
2.
3.
4.

【业务建议】
1. （可执行的行动建议）
2.
3.

按上述格式输出，简洁专业。"""
    else:
        prompt = f"""You are a senior business analyst. Here is report data in CSV format:

{df.to_csv(index=False)}

Output in plain text only — no Markdown symbols (###, **, * etc.).

Key Findings:
1. (data-driven, with specific numbers)
2.
3.
4.

Recommendations:
1. (actionable)
2.
3.

Follow the format above. Be concise and professional."""

    if "gpt" in AI_MODEL.lower():
        from gen_ai_hub.proxy.native.openai.clients import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return response.choices[0].message.content
    else:
        from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
        llm = ChatOpenAI(proxy_model_name=AI_MODEL)
        return llm.invoke(prompt).content


def analyze_screenshot(image_path: str, lang: str = "en") -> str:
    """
    Analyze a dashboard screenshot using a vision-capable model.
    Uses current AI_MODEL if it's GPT-based, otherwise falls back to gpt-4o-mini.
    """
    _set_aicore_env()

    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    vision_model = AI_MODEL if "gpt" in AI_MODEL.lower() else "gpt-4o-mini"

    if lang == "zh":
        text_prompt = """你是一位资深业务分析师。请仔细观察这张业务报表截图，用纯文本输出，不要使用任何 Markdown 符号。

【关键发现】
1. （描述图表中的核心数据和趋势，带具体数字）
2.
3.
4.

【业务建议】
1. （基于图表数据的可执行建议）
2.
3.

按上述格式输出，简洁专业。"""
    else:
        text_prompt = """You are a senior business analyst. Carefully examine this business dashboard screenshot. Output in plain text only — no Markdown symbols.

Key Findings:
1. (describe key data and trends visible in the chart, with specific numbers)
2.
3.
4.

Recommendations:
1. (actionable recommendations based on the data)
2.
3.

Follow the format above. Be concise and professional."""

    from gen_ai_hub.proxy.native.openai.clients import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model=vision_model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": text_prompt},
            ],
        }],
        max_tokens=1024,
    )
    return response.choices[0].message.content

def natural_language_to_cron(text: str) -> dict:
    """Convert natural language schedule description to cron expression using GPT."""
    _set_aicore_env()
    from gen_ai_hub.proxy.native.openai.clients import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": """You are a cron expression generator. Convert natural language schedule descriptions to cron expressions.
Return ONLY a JSON object with two fields:
- "cron": the 5-field cron expression (minute hour day month weekday)
- "description": a clear human-readable description of the schedule in the same language as the input

Rules:
- Support HH:MM time format (e.g. "10:39", "2:39", "14:05") mixed with any language
- Support Chinese: 上午=AM, 下午=PM (+12h if hour<12), 早上/早=AM, 晚上/晚=PM
- Chinese number mapping for minutes: 零=0, 五=5, 十=10, 十五=15, 二十=20, 二十五=25, 三十/半=30, 三十五=35, 四十=40, 四十五=45, 五十=50, 五十五=55
- Weekday (Chinese): 周一/星期一=1, 周二=2, 周三=3, 周四=4, 周五=5, 周六=6, 周日=0
- "工作日/weekday" = 1-5

Examples:
Input: "每周一早上9点" -> {"cron": "0 9 * * 1", "description": "每周一 09:00"}
Input: "每周五 10:39" -> {"cron": "39 10 * * 5", "description": "每周五 10:39"}
Input: "每周五上午10点二十" -> {"cron": "20 10 * * 5", "description": "每周五 10:20"}
Input: "每天下午3点" -> {"cron": "0 15 * * *", "description": "每天 15:00"}
Input: "每月1号 14:30" -> {"cron": "30 14 1 * *", "description": "每月1日 14:30"}
Input: "每周五下午5点半" -> {"cron": "30 17 * * 5", "description": "每周五 17:30"}
Input: "每周三下午2点15分" -> {"cron": "15 14 * * 3", "description": "每周三 14:15"}
Input: "every Monday at 9am" -> {"cron": "0 9 * * 1", "description": "Every Monday at 09:00"}
Input: "every day at 8:30am" -> {"cron": "30 8 * * *", "description": "Every day at 08:30"}
Input: "every weekday at 9:15am" -> {"cron": "15 9 * * 1-5", "description": "Every weekday at 09:15"}
Input: "每周二 2:39" -> {"cron": "39 2 * * 2", "description": "每周二 02:39"}

Return only valid JSON, no explanation, no markdown."""
        }, {
            "role": "user",
            "content": text
        }],
        max_tokens=120,
    )
    import json, re
    raw = response.choices[0].message.content.strip()
    # strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    # extract first JSON object in case of extra text
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return json.loads(raw)
