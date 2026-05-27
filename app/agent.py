import os
import pandas as pd
from app.config import (
    AICORE_AUTH_URL, AICORE_CLIENT_ID, AICORE_CLIENT_SECRET,
    AICORE_BASE_URL, AICORE_RESOURCE_GROUP, AI_MODEL,
)


def analyze_data(df: pd.DataFrame, lang: str = "en") -> str:
    os.environ["AICORE_AUTH_URL"] = AICORE_AUTH_URL
    os.environ["AICORE_CLIENT_ID"] = AICORE_CLIENT_ID
    os.environ["AICORE_CLIENT_SECRET"] = AICORE_CLIENT_SECRET
    os.environ["AICORE_BASE_URL"] = AICORE_BASE_URL
    os.environ["AICORE_RESOURCE_GROUP"] = AICORE_RESOURCE_GROUP

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
