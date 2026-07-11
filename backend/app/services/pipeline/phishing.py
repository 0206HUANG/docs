"""
Rule-based phishing / fraud heuristics. Runs before any LLM call, cheap and
deterministic. Returns (is_phishing, reasons). Tuned to favor precision on the
high-confidence signals (executable attachments, payment-account changes) and
require corroborating lure context for the softer link/impersonation signals.
"""
import re
from urllib.parse import urlparse

DANGEROUS_EXT = (
    ".exe", ".bat", ".scr", ".js", ".vbs", ".cmd", ".com", ".pif", ".jar", ".msi", ".hta",
)

FREE_MAIL_DOMAINS = {
    "gmail.com", "qq.com", "163.com", "126.com", "outlook.com", "hotmail.com",
    "yahoo.com", "foxmail.com", "sina.com", "aol.com",
}

IMPERSONATE_TERMS = [
    "银行", "bank", "财务部", "财务", "admin", "administrator", "官方", "official",
    "客服", "support team", "security team", "it support", "系统管理员", "总裁", "ceo", "老板",
]

PAYMENT_CHANGE = [
    "更改付款", "更改账户", "变更账号", "变更银行", "更换收款", "新的账户", "新账号", "新银行账户",
    "汇款至", "转账至", "改为以下账户", "付款到新账户", "尽快付款", "紧急付款",
    "change bank", "new account number", "update payment", "wire transfer to",
    "bank details have changed", "updated banking", "remit to", "change of account",
]

URGENCY_LURE = [
    "立即验证", "账号异常", "账户异常", "点击登录", "验证身份", "冻结", "限时", "立即处理",
    "verify your account", "click here to login", "account suspended", "confirm your password",
    "urgent action required", "unusual activity", "reset your password", "validate your account",
]

URL_RE = re.compile(r"https?://[^\s\)\]>\"'）】]+", re.I)
IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _domain(addr: str) -> str:
    addr = (addr or "").strip().lower()
    return addr.split("@")[-1] if "@" in addr else ""


def detect_phishing(
    from_addr: str | None,
    from_name: str | None,
    subject: str | None,
    body_text: str | None,
    attachment_names: list[str] | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    from_name = from_name or ""
    text = f"{subject or ''}\n{body_text or ''}"
    low = text.lower()
    sender_domain = _domain(from_addr)

    # 1. Dangerous / executable attachment (malware vector) — high confidence
    for name in attachment_names or []:
        if name and name.lower().strip().endswith(DANGEROUS_EXT):
            reasons.append(f"可执行/高危附件: {name}")

    # 2. Payment / bank-account change (business email compromise) — high confidence
    if any(k in low for k in (p.lower() for p in PAYMENT_CHANGE)):
        reasons.append("涉及更改付款账号 / 转账诱导(疑似商业邮件诈骗)")

    # 3. Suspicious links: IP-host, or domain mismatch under lure context
    lure = any(k in low for k in (u.lower() for u in URGENCY_LURE))
    for u in URL_RE.findall(text):
        host = (urlparse(u).hostname or "").lower()
        if not host:
            continue
        if IP_RE.match(host):
            reasons.append(f"链接指向 IP 地址: {host}")
        elif sender_domain and host != sender_domain and not host.endswith("." + sender_domain) and lure:
            reasons.append(f"诱导性链接域名与发件人不符: {host}")

    # 4. Display-name impersonation from a free mailbox
    if sender_domain in FREE_MAIL_DOMAINS and any(t.lower() in from_name.lower() for t in IMPERSONATE_TERMS):
        reasons.append(f"显示名冒充机构但使用免费邮箱: \"{from_name}\" <{sender_domain}>")

    # de-dup while preserving order
    seen = set()
    uniq = [r for r in reasons if not (r in seen or seen.add(r))]
    return (len(uniq) > 0, uniq)
