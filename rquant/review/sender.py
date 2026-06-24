"""
rquant.review.sender — 复盘报告邮件发送

通过 SMTP 将复盘报告的 HTML 版本发送到配置的收件人列表。
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from config import config
from rquant.log import error, info, warning


def _build_message(
    subject: str,
    html_body: str,
    sender: str,
    recipients: list[str],
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _validate_config() -> Optional[str]:
    """校验 SMTP 配置是否完整，返回错误描述或 None"""
    if not config.review.smtp_host:
        return "SMTP 服务器未配置（smtp_host 为空）"
    if not config.review.sender_email:
        return "发件人邮箱未配置（sender_email 为空）"
    recipients: list[str] = config.review.email_recipients
    if not recipients or not any(r.strip() for r in recipients):
        return "收件人列表为空（email_recipients 为空）"
    return None


def send_report(report_date: str | None = None) -> bool:
    """发送指定日期的复盘报告 HTML 到配置的收件人列表

    Args:
        report_date: 报告日期（YYYY-MM-DD），默认今天

    Returns:
        True 表示发送成功
    """
    err = _validate_config()
    if err:
        warning("review.sender", f"SMTP 配置不完整，跳过发送: {err}")
        return False

    from datetime import date

    report_date = report_date or date.today().isoformat()
    report_dir = config.project_root / config.review.report_dir
    html_path = report_dir / f"{report_date}.html"

    if not html_path.exists():
        error("review.sender", f"复盘报告 HTML 不存在: {html_path}")
        return False

    html_body = html_path.read_text(encoding="utf-8")
    recipients: list[str] = [r.strip() for r in config.review.email_recipients if r.strip()]
    subject = f"复盘报告 — {report_date}"

    msg = _build_message(subject, html_body, config.review.sender_email, recipients)

    try:
        ctx = None
        if config.review.smtp_use_tls:
            ctx = ssl.create_default_context()
        with smtplib.SMTP(config.review.smtp_host, config.review.smtp_port) as server:
            if config.review.smtp_use_tls:
                server.starttls(context=ctx)
            username = config.review.smtp_username
            password = config.review.smtp_password
            if username and password:
                server.login(username, password)
            server.sendmail(config.review.sender_email, recipients, msg.as_string())
        info("review.sender", f"复盘报告已发送 → {', '.join(recipients)}")
        return True
    except smtplib.SMTPException as e:
        error("review.sender", f"SMTP 发送失败: {e}")
        return False
    except OSError as e:
        error("review.sender", f"网络错误: {e}")
        return False
