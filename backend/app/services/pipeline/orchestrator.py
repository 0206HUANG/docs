import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Email, EmailAccount, EmailClassification, EmailReply, Ticket, Notification
from app.repos.email_repo import AuditLogRepo, EmailRepo
from app.repos.kb_repo import KBChunkRepo, KBGroupRepo
from app.repos.ticket_repo import SensitiveWordRepo, StrategyRepo, NotificationRepo
from app.services.llm import get_embed_provider, get_llm_provider
from app.services.pipeline.classifier import classify_email
from app.services.pipeline.rag import retrieve_context
from app.services.pipeline.reply_generator import generate_reply
from app.services.pipeline.router import decide_strategy
from app.services.pipeline.phishing import detect_phishing
from app.services.pipeline.sensitive import check_sensitive_words

logger = logging.getLogger(__name__)


async def process_email(
    db: AsyncSession,
    email: Email,
    account: EmailAccount,
    tenant_settings: dict,
) -> None:
    """
    Full pipeline for one inbound email. Writes classification, reply, ticket, audit logs.
    On any exception: logs failure, creates human ticket to avoid losing email.
    """
    tenant_id = email.tenant_id
    audit = AuditLogRepo(db, tenant_id)
    sw_repo = SensitiveWordRepo(db, tenant_id)

    # ── 0. Black/white list + phishing gate (before any LLM call) ───────────
    list_verdict = await _check_lists(db, email, tenant_id)
    if list_verdict == "black":
        await audit.log(email.id, "blacklisted", detail={"from": email.from_addr})
        await _save_classification(db, email, tenant_id, email_type="spam",
                                   language="zh", urgency=1, has_sensitive=False, sensitive_words=[])
        await db.commit()
        return
    trusted = list_verdict == "white"

    if not trusted:
        att_names = await _attachment_names(db, email.id)
        is_phish, phish_reasons = detect_phishing(
            email.from_addr, email.from_name, email.subject, email.body_text, att_names
        )
        if is_phish:
            await audit.log(email.id, "phishing_blocked", detail={"reasons": phish_reasons})
            await _save_classification(db, email, tenant_id, email_type="spam",
                                       language="zh", urgency=3, has_sensitive=True,
                                       sensitive_words=phish_reasons)
            await _create_ticket(db, email, account, reason="phishing",
                                 title=f"[钓鱼风险] {email.subject or '无标题'}", priority=3)
            await db.commit()
            return

    # ── 1. Sensitive word check (highest priority) ──────────────────────────
    full_text = f"{email.subject or ''} {email.body_text or ''} {email.body_html or ''}"
    sw_list = await sw_repo.get_all_active()
    matched_words = check_sensitive_words(full_text, sw_list)

    if matched_words:
        await audit.log(
            email.id, "sensitive_blocked",
            detail={"matched": matched_words},
        )
        await _create_ticket(
            db, email, account,
            reason="sensitive_word",
            title=f"[敏感词拦截] {email.subject or '无标题'}",
            priority=3,
        )
        await _save_classification(
            db, email, tenant_id,
            email_type="other", language="zh", urgency=3,
            has_sensitive=True, sensitive_words=matched_words,
        )
        await db.commit()
        return

    # ── 2. LLM Classification ───────────────────────────────────────────────
    llm_config = tenant_settings.get("llm_config", {})
    try:
        llm = get_llm_provider(llm_config)
        cls_result = await classify_email(
            llm=llm,
            subject=email.subject,
            body=email.body_text,
            from_addr=email.from_addr,
            model=llm_config.get("model"),
        )
    except Exception as e:
        logger.error("LLM classify failed email=%s: %s", email.id, e)
        await audit.log(email.id, "classified", status="failure", error_msg=str(e))
        await _create_ticket(db, email, account, reason="classification",
                             title=f"[LLM不可用] {email.subject or '无标题'}", priority=2)
        await db.commit()
        return

    email_type = cls_result["email_type"]
    language = cls_result.get("language", "zh")
    urgency = cls_result.get("urgency", 1)

    cls_obj = await _save_classification(
        db, email, tenant_id, email_type=email_type, language=language,
        urgency=urgency, has_sensitive=False, sensitive_words=[],
        llm_model=cls_result.get("llm_model"),
        prompt_tokens=cls_result.get("prompt_tokens", 0),
        completion_tokens=cls_result.get("completion_tokens", 0),
        confidence=cls_result.get("confidence"),
    )
    await audit.log(email.id, "classified", detail={"type": email_type, "urgency": urgency})

    # ── 3a. Resume parsing (job-application emails) ──────────────────────────
    if email_type == "resume":
        try:
            await _parse_resume(db, email, account, llm, llm_config, audit)
        except Exception as e:
            logger.error("Resume parse failed email=%s: %s", email.id, e)

    # ── 3. RAG retrieval ────────────────────────────────────────────────────
    kb_group_repo = KBGroupRepo(db, tenant_id)
    kb_chunk_repo = KBChunkRepo(db, tenant_id)
    query_text = f"{email.subject or ''} {(email.body_text or '')[:500]}"

    try:
        embed_provider = get_embed_provider(llm_config)
        context_chunks, chunk_ids = await retrieve_context(
            embed_provider=embed_provider,
            kb_group_repo=kb_group_repo,
            kb_chunk_repo=kb_chunk_repo,
            positioning=account.positioning,
            email_type=email_type,
            query_text=query_text,
        )
    except Exception as e:
        logger.error("RAG retrieval failed email=%s: %s", email.id, e)
        context_chunks, chunk_ids = [], []

    rag_found = len(context_chunks) > 0
    await audit.log(
        email.id, "rag_retrieved",
        detail={"chunks": len(context_chunks), "ids": [str(i) for i in chunk_ids]},
    )

    # ── 4. Route decision ───────────────────────────────────────────────────
    strategy_repo = StrategyRepo(db, tenant_id)
    strategy_obj = await strategy_repo.get_strategy(email_type, account.positioning)
    tenant_strategy = strategy_obj.send_strategy if strategy_obj else None
    tone = strategy_obj.tone if strategy_obj else tenant_settings.get("default_tone", "business")

    decision = decide_strategy(email_type, has_sensitive=False, rag_found=rag_found,
                                tenant_strategy=tenant_strategy)

    if decision == "skip":
        await audit.log(email.id, "skipped", detail={"reason": "no_reply_type"})
        await db.commit()
        return

    if decision == "human_only":
        reason = "rag_miss" if not rag_found else "strategy"
        await _create_ticket(
            db, email, account,
            reason=reason,
            title=f"[人工处理] {email.subject or '无标题'}",
            priority=urgency,
        )
        await audit.log(email.id, "human_routed", detail={"reason": reason})
        await db.commit()
        return

    # ── 5. Reply generation ─────────────────────────────────────────────────
    try:
        reply_text, reply_model = await generate_reply(
            llm=llm,
            subject=email.subject,
            body=email.body_text,
            from_addr=email.from_addr,
            language=language,
            tone=tone,
            context_chunks=context_chunks,
            model=llm_config.get("model"),
        )
    except Exception as e:
        logger.error("Reply generation failed email=%s: %s", email.id, e)
        await _create_ticket(db, email, account, reason="classification",
                             title=f"[生成失败] {email.subject or '无标题'}", priority=urgency)
        await audit.log(email.id, "reply_generated", status="failure", error_msg=str(e))
        await db.commit()
        return

    await audit.log(email.id, "reply_generated", detail={"strategy": decision, "model": reply_model})

    # ── 6. Persist reply and route ──────────────────────────────────────────
    reply = EmailReply(
        email_id=email.id,
        tenant_id=tenant_id,
        draft_content=reply_text,
        final_content=reply_text if decision == "auto_send" else None,
        status="pending_review" if decision == "draft_review" else "approved",
        send_strategy=decision,
        llm_model=reply_model,
        rag_chunk_ids=[str(i) for i in chunk_ids],
    )
    db.add(reply)
    await db.flush()

    if decision == "draft_review":
        await _create_ticket(
            db, email, account,
            reason="strategy",
            title=f"[草稿待审] {email.subject or '无标题'}",
            priority=urgency,
        )

    await audit.log(email.id, "sent" if decision == "auto_send" else "draft_created",
                    detail={"strategy": decision})
    await db.commit()

    # auto_send: enqueue actual SMTP send task (imported lazily to avoid circular)
    if decision == "auto_send":
        from app.worker.tasks import enqueue_send_reply
        await enqueue_send_reply(str(reply.id))


async def _save_classification(
    db, email, tenant_id, email_type, language, urgency,
    has_sensitive, sensitive_words,
    llm_model=None, prompt_tokens=0, completion_tokens=0, confidence=None,
) -> EmailClassification:
    cls_obj = EmailClassification(
        email_id=email.id,
        tenant_id=tenant_id,
        email_type=email_type,
        language=language,
        urgency=urgency,
        has_sensitive=has_sensitive,
        sensitive_words=sensitive_words,
        confidence=confidence,
        llm_model=llm_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        classified_at=datetime.now(timezone.utc),
    )
    db.add(cls_obj)
    await db.flush()
    return cls_obj


async def _create_ticket(db, email, account, reason, title, priority=1) -> Ticket:
    ticket = Ticket(
        tenant_id=email.tenant_id,
        email_id=email.id,
        account_id=account.id,
        title=title,
        reason=reason,
        status="open",
        priority=priority,
    )
    db.add(ticket)
    await db.flush()
    return ticket


def _clip(v, n):
    """Truncate a string to fit a column; pass through non-strings."""
    return v[:n] if isinstance(v, str) else v


async def _parse_resume(db, email, account, llm, llm_config, audit) -> None:
    """Extract structured resume data from a job-application email's attachment
    (or body as fallback) and persist a ResumeProfile."""
    from sqlalchemy import select

    from app.db.models import EmailAttachment, ResumeProfile
    from app.services.kb.ingestion import _extract_text
    from app.services.pipeline.resume_parser import parse_resume

    result = await db.execute(
        select(EmailAttachment).where(EmailAttachment.email_id == email.id)
    )
    attachments = result.scalars().all()

    resume_text = ""
    source = "body"
    used_att = None
    for att in attachments:
        name = (att.filename or "").lower()
        if att.storage_path and name.endswith((".pdf", ".doc", ".docx", ".txt")):
            try:
                with open(att.storage_path, "rb") as fh:
                    text = _extract_text(fh.read(), att.filename)
                if text and text.strip():
                    resume_text, source, used_att = text, "attachment", att
                    break
            except Exception as e:
                logger.warning("Read resume attachment failed %s: %s", att.filename, e)

    if not resume_text.strip():
        resume_text = f"{email.subject or ''}\n{email.body_text or ''}"
        source = "body"

    parsed = await parse_resume(
        llm, resume_text, target_role=account.positioning, model=llm_config.get("model")
    )
    if not parsed:
        return

    profile = ResumeProfile(
        tenant_id=email.tenant_id,
        email_id=email.id,
        attachment_id=used_att.id if used_att else None,
        candidate_name=_clip(parsed.get("candidate_name"), 200),
        candidate_email=_clip(parsed.get("candidate_email"), 200),
        candidate_phone=_clip(parsed.get("candidate_phone"), 50),
        education=parsed.get("education", []),
        experience=parsed.get("experience", []),
        skills=parsed.get("skills", []),
        desired_position=_clip(parsed.get("desired_position"), 200),
        expected_salary=_clip(parsed.get("expected_salary"), 100),
        years_experience=parsed.get("years_experience"),
        summary=parsed.get("summary"),
        match_score=parsed.get("match_score"),
        match_notes=parsed.get("match_notes"),
        llm_model=parsed.get("llm_model"),
        source=source,
    )
    db.add(profile)
    await db.flush()
    await audit.log(email.id, "resume_parsed", detail={
        "candidate": parsed.get("candidate_name"),
        "match_score": parsed.get("match_score"),
        "source": source,
    })


async def _check_lists(db, email, tenant_id) -> str | None:
    """Return 'black' / 'white' / None for the sender against list rules."""
    from sqlalchemy import select

    from app.db.models import EmailListRule

    sender = (email.from_addr or "").strip().lower()
    domain = sender.split("@")[-1] if "@" in sender else ""

    result = await db.execute(
        select(EmailListRule).where(
            EmailListRule.tenant_id == tenant_id,
            EmailListRule.is_active == True,
        )
    )
    rules = result.scalars().all()

    def _hit(r) -> bool:
        val = (r.value or "").strip().lower()
        return (r.match_type == "email" and val == sender) or (r.match_type == "domain" and val == domain)

    # blacklist wins over whitelist
    if any(_hit(r) for r in rules if r.list_type == "black"):
        return "black"
    if any(_hit(r) for r in rules if r.list_type == "white"):
        return "white"
    return None


async def _attachment_names(db, email_id) -> list[str]:
    from sqlalchemy import select

    from app.db.models import EmailAttachment

    result = await db.execute(select(EmailAttachment).where(EmailAttachment.email_id == email_id))
    return [a.filename for a in result.scalars().all()]
