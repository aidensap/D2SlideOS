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


def _get_client():
    _set_aicore_env()
    from gen_ai_hub.proxy.native.openai.clients import OpenAI
    return OpenAI()


def _chat(model: str, messages: list, max_tokens: int = 1024):
    """Unified chat call — supports both model names and config IDs (UUID format)."""
    import re
    _set_aicore_env()
    is_uuid = bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', model, re.I))
    if is_uuid:
        # Use direct HTTP call to AI Core with config_id as deployment target
        import requests, types
        from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
        proxy = get_proxy_client('gen-ai-hub')
        token = proxy.get_token()
        base = AICORE_BASE_URL.rstrip('/v2').rstrip('/')
        url = f"{base}/v2/inference/deployments/{model}/chat/completions"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "AI-Resource-Group": AICORE_RESOURCE_GROUP,
        }
        payload = {"messages": messages, "max_tokens": max_tokens}
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        msg = types.SimpleNamespace(content=content)
        choice = types.SimpleNamespace(message=msg)
        return types.SimpleNamespace(choices=[choice])
    else:
        from gen_ai_hub.proxy.native.openai.clients import OpenAI
        client = OpenAI()
        return client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens)


def analyze_data(df: pd.DataFrame, lang: str = "en") -> str:
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

    response = _chat(AI_MODEL, [{"role": "user", "content": prompt}], max_tokens=1024)
    return response.choices[0].message.content


def analyze_screenshot(image_path: str, lang: str = "en") -> str:
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

    response = _chat(
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


def ask_vision_for_click(image_path: str, question: str):
    import json, re
    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("utf-8")
    client = _get_client()
    prompt_suffix = (
        "\n\nReturn ONLY JSON: {\"x\": <int>, \"y\": <int>}. "
        "If not found: {\"x\": null, \"y\": null}. No extra text."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": question + prompt_suffix},
            ],
        }],
        max_tokens=60,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        import re
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        data = json.loads(m.group(0))
        x, y = data.get("x"), data.get("y")
        if x is not None and y is not None:
            return (int(x), int(y))
    return None


def natural_language_to_cron(text: str) -> dict:
    import json, re
    msgs = [{
        "role": "system",
        "content": """You are a cron expression generator. Convert natural language schedule descriptions to cron expressions.
Return ONLY a JSON object with two fields:
- "cron": the 5-field cron expression (minute hour day month weekday)
- "description": a clear human-readable description of the schedule in the same language as the input

Return only valid JSON, no explanation, no markdown."""
    }, {
        "role": "user",
        "content": text
    }]
    response = _chat(AI_MODEL, msgs, max_tokens=120)
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return json.loads(raw)


def generate_model_aliases(models: list) -> list:
    """Given a list of {id, name} SAC models, return [{id, name, alias}] with AI-generated friendly aliases."""
    import json, re
    result = []
    for i in range(0, len(models), 20):
        batch = models[i:i+20]
        names = [m["name"] for m in batch]
        prompt = f"""These are SAP Analytics Cloud model technical names. Give each a short friendly Chinese alias (max 12 chars).
Return ONLY a JSON array of strings in the same order as input, one alias per name.
Example input: ["20241024_Cathaylife_v3", "SAP__HR_COURSES_IM_SUMMARY__ZH"]
Example output: ["国泰人寿v3", "HR课程汇总"]

Input: {json.dumps(names, ensure_ascii=False)}"""
        try:
            resp = _chat(
                AI_MODEL,
                [{"role": "user", "content": prompt}],
                max_tokens=400,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```[a-z]*\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw).strip()
            aliases = json.loads(raw)
            for j, m in enumerate(batch):
                alias = aliases[j] if j < len(aliases) else m["name"]
                result.append({"id": m["id"], "name": m["name"], "alias": alias})
        except Exception as e:
            print(f"[alias_error] {e}", flush=True)
            result += [{"id": m["id"], "name": m["name"], "alias": m["name"]} for m in batch]
    return result


def infer_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Use AI to rename cryptic column names (e.g. ID_xxx) to human-readable ones."""
    import json, re
    col_samples = {col: df[col].dropna().head(3).tolist() for col in df.columns}
    prompt = f"""Given these DataFrame columns and their sample values, infer a short human-readable name for each column.
Return ONLY a JSON object mapping original column name to inferred name.
If a column already has a clear name, keep it as-is.
Samples: {json.dumps(col_samples, ensure_ascii=False)}"""
    try:
        resp = _chat(
            AI_MODEL,
            [{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
        rename_map = json.loads(raw)
        return df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns and k != v})
    except Exception:
        return df


def generate_chart_code(df: pd.DataFrame, chart_prompt: str, output_path: str) -> str:
    """Ask AI to write plotly/matplotlib code. Expects df already renamed via infer_column_names."""
    import json, re

    columns_info = []
    for col in df.columns:
        dtype = "text" if df[col].dtype == object else "number"
        sample = df[col].dropna().head(3).tolist()
        n_unique = int(df[col].nunique())
        columns_info.append({"name": col, "type": dtype, "n_unique": n_unique, "sample": sample})

    prompt = f"""You are a Python data visualization expert. Write code to create a chart and save it as a PNG.

The DataFrame is ALREADY loaded as variable `df` with {len(df)} rows and these columns:
{json.dumps(columns_info, ensure_ascii=False, indent=2)}

User request: {chart_prompt}

CRITICAL RULES:
- You MUST use the variable `df` directly. NEVER create sample/fake data or use hardcoded values.
- Use only column names that exist in the list above.
- ALL labels, titles, axis names, and legend text must be in the SAME language as the column names (if columns are Chinese, use Chinese everywhere; if English, use English).
- PREFER plotly over matplotlib — it supports maps, heatmaps, sankey, sunburst, 3D, etc.
- For plotly: use dark template `plotly_dark`, save with `fig.write_image('{output_path}', width=1000, height=600)`
- For matplotlib (only if plotly can't do it): dark bg `#0f172a`, save with `plt.savefig('{output_path}', dpi=150, ...); plt.close()`
- DO NOT use plt.show() or fig.show()
- DO NOT import pandas or load any data — df is already available
- Output ONLY raw Python code, no explanation, no markdown fences

CHART DESIGN RULES:
- For category axis (x or y): pick a text column with n_unique >= 3. NEVER use a column with n_unique <= 2 as the category axis — that means it's a dimension/type label, not a real category.
- If no text column has n_unique >= 3, group by the text column with the most unique values and aggregate numeric columns with sum().
- For "Top N" requests: sort by the numeric column descending and take the top N ROWS, then plot. Do NOT just aggregate all rows into 2 bars.
- If the data has columns that look like measure types (e.g. "Actual" vs "Forecast"), use them as color/legend grouping, not as the category axis.

Example plotly structure:
import plotly.express as px
fig = px.bar(df, x='ColA', y='ColB', title='...')
fig.update_layout(template='plotly_dark')
fig.write_image('{output_path}', width=1000, height=600)"""

    response = _chat(AI_MODEL, [{"role": "user", "content": prompt}], max_tokens=900)
    code = response.choices[0].message.content.strip()
    if code.startswith("```"):
        code = re.sub(r"^```[a-z]*\n?", "", code)
        code = re.sub(r"\n?```$", "", code).strip()

    try:
        exec(code, {"df": df, "__builtins__": __builtins__})
        return output_path
    except Exception as e:
        print(f"[chart_code exec error] {e}\n--- code ---\n{code}\n---")
        return ""


def parse_task_from_text(text: str, contacts: list, report_aliases: list) -> dict:
    import json, re
    contacts_str = "\n".join(f"- {c['name']}: {c['email']}" for c in contacts) or "（无）"
    reports_str = "\n".join(f"- {r['name']}: {r['url']} (source={r['source']})" for r in report_aliases) or "（无）"

    response = _chat(AI_MODEL, [{
            "role": "system",
            "content": f"""You are a task parser. Extract structured fields from a natural language task description.

Available contacts:
{contacts_str}

Available reports:
{reports_str}

Return ONLY a JSON object with these fields:
- "name": task name (short, describe report content only)
- "lang": "en" if user mentions English output, otherwise "zh"
- "schedule_text": the schedule part, empty string if not mentioned
- "report_name": matched report name, empty string if not found or ambiguous
- "report_url": MUST copy the exact URL/ID value from the matched report in the list above. Empty string only if not found or ambiguous.
- "report_source": source type — MUST copy the source field from the matched report. Default "screenshot" only if no report matched
- "ambiguous": true ONLY if 2+ reports equally match and user did not specify which one. If the user specifies a version (e.g. "v1"), match exactly and set ambiguous=false.
- "candidates": if ambiguous=true, list the matching report names so user can choose; otherwise empty list
- "recipient_names": list of matched contact names
- "recipient_emails": list of matched email addresses
- "email_body": write in the SAME language as the user. Chinese format: "下方是【{{report name}}】的{{月度/每周/etc if schedule mentioned, otherwise just 数据}}报告，由 D2SlideOS 自动生成。" English: "Please find the {{monthly/weekly/etc if mentioned, otherwise omit}} data report for [{{report name}}], auto-generated by D2SlideOS." Then 1 sentence on what the report covers. End with "如有问题请回复本邮件。" or "Reply if you have questions." Sign off: "D2SlideOS · SAP"

IMPORTANT rules:
1. If user says "国泰人寿v1", match ONLY 国泰人寿v1 — do NOT treat it as ambiguous.
2. report_url must be the exact string from the list (e.g. "Cavc5i0esdqj5s3q3dembpas122"), not the name.
3. Only set ambiguous=true when user is vague (e.g. just "国泰" with no version).
4. If the user mentions "模型", "SAC模型", "从模型", or "model", set report_source="sac" even if no report matched.
5. If the available reports list is empty but user clearly wants a SAC model report, set report_source="sac" and ambiguous=true with empty candidates so user can pick manually.

Return only valid JSON, no explanation."""
        }, {
            "role": "user",
            "content": text
        }],
        max_tokens=600,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return json.loads(raw)