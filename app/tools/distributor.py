import base64
from pathlib import Path
import resend
from app.config import RESEND_API_KEY, EMAIL_FROM

DEFAULT_BODY = {
    "zh": {
        "insights_label": "AI 分析摘要：",
        "attachment_note": "完整 PowerPoint 报告见附件。",
        "footer": "由 D2SlideOS 自动发送 · Powered by SAP AI Core",
        "greeting": "您好，",
        "body": "您的报表任务 <strong>{job_name}</strong> 已完成。",
        "custom_attachment": "完整报告见附件",
    },
    "en": {
        "insights_label": "AI Insights:",
        "attachment_note": "The full PowerPoint report is attached.",
        "footer": "Sent by D2SlideOS · Powered by SAP AI Core",
        "greeting": "Hi,",
        "body": "Your scheduled report <strong>{job_name}</strong> is ready.",
        "custom_attachment": "Full report attached",
    },
}


def send_report(file_path: str, recipients: str, job_name: str, insights: str, email_body: str = "", lang: str = "zh"):
    if not RESEND_API_KEY:
        print(f"[Email] RESEND_API_KEY not configured, skipping. Recipients: {recipients}")
        return

    to_list = [r.strip() for r in recipients.split(",") if r.strip()]
    if not to_list:
        return

    resend.api_key = RESEND_API_KEY

    with open(file_path, "rb") as f:
        file_content = base64.b64encode(f.read()).decode("utf-8")
    filename = Path(file_path).name

    t = DEFAULT_BODY.get(lang, DEFAULT_BODY["zh"])

    if email_body.strip():
        html = f"""<div style="font-family:sans-serif;font-size:14px;line-height:1.7">
{email_body.replace(chr(10), '<br>')}
<br><br>
<strong>{t['insights_label']}</strong>
<pre style="background:#f4f4f4;padding:12px;border-radius:6px;font-size:13px">{insights}</pre>
<p style="font-size:12px;color:#888">{t['custom_attachment']} · {t['footer']}</p>
</div>"""
    else:
        html = f"""<div style="font-family:sans-serif;font-size:14px;line-height:1.7">
<p>{t['greeting']}</p>
<p>{t['body'].format(job_name=job_name)}</p>
<p><strong>{t['insights_label']}</strong></p>
<pre style="background:#f4f4f4;padding:12px;border-radius:6px;font-size:13px">{insights}</pre>
<p>{t['attachment_note']}</p>
<hr>
<p style="color:#888;font-size:12px">{t['footer']}</p>
</div>"""

    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": to_list,
        "subject": f"[D2SlideOS] {job_name}",
        "html": html,
        "attachments": [{"filename": filename, "content": file_content}],
    })

    print(f"[Email] Sent to {to_list}")