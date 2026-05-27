import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from app.config import EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD


def send_report(file_path: str, recipients: str, job_name: str, insights: str):
    if not EMAIL_HOST or not EMAIL_USER:
        print(f"[邮件] 未配置邮件服务，跳过发送。收件人：{recipients}")
        return

    to_list = [r.strip() for r in recipients.split(",") if r.strip()]
    if not to_list:
        return

    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = f"[AI 报告] {job_name}"

    body = f"您好，\n\n以下是 {job_name} 的 AI 分析摘要：\n\n{insights}\n\n完整报告见附件。\n\n-- Aiden AI Report Agent"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={Path(file_path).name}")
        msg.attach(part)

    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_list, msg.as_string())

    print(f"[邮件] 已发送给 {to_list}")
