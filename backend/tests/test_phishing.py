from app.services.pipeline.phishing import detect_phishing


def test_clean_business_email_is_not_phishing():
    ok, reasons = detect_phishing(
        "client@acme.com", "Acme Corp", "报价咨询", "你好，请问贵司产品的价格和交货期？", []
    )
    assert ok is False
    assert reasons == []


def test_executable_attachment_flagged():
    ok, reasons = detect_phishing("x@y.com", "X", "invoice", "see attached", ["invoice.exe"])
    assert ok is True
    assert any("附件" in r for r in reasons)


def test_payment_account_change_is_phishing():
    ok, reasons = detect_phishing(
        "cfo@vendor.com", "CFO", "urgent",
        "请将本月货款改为以下新账户并尽快付款至新账户", [],
    )
    assert ok is True
    assert any("付款账号" in r for r in reasons)


def test_ip_address_link_flagged():
    ok, reasons = detect_phishing(
        "a@b.com", "A", "hi", "please login at http://192.168.1.10/verify now", []
    )
    assert ok is True
    assert any("IP" in r for r in reasons)


def test_impersonation_from_free_mailbox():
    ok, reasons = detect_phishing(
        "random8899@gmail.com", "工商银行客服", "账户异常",
        "您的账号存在异常，请立即验证身份： http://secure-fake.example/login", [],
    )
    assert ok is True


def test_mismatched_link_without_lure_is_ok():
    # a plain link to another domain, no urgency lure → should NOT trip
    ok, reasons = detect_phishing(
        "sales@acme.com", "Acme", "资料", "详见我们官网 https://partner-site.com/catalog", []
    )
    assert ok is False
