"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, EmailDetail, AuditEntry } from "@/lib/api";

const STAGE_LABELS: Record<string, string> = {
  received: "收件",
  sensitive_blocked: "敏感词拦截",
  classified: "分类完成",
  rag_retrieved: "知识库检索",
  reply_generated: "生成草稿",
  draft_created: "草稿待审",
  sent: "已发送",
  human_routed: "转人工",
  skipped: "跳过（无需回复）",
};

export default function EmailDetailPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();
  const [email, setEmail] = useState<EmailDetail | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [tab, setTab] = useState<"email" | "audit">("email");

  useEffect(() => {
    api.emails.get(id).then(setEmail).catch(console.error);
    api.emails.audit(id).then(setAudit).catch(() => {});
  }, [id]);

  if (!email) return <p className="text-muted-foreground text-sm">加载中...</p>;

  return (
    <div className="max-w-3xl">
      <button onClick={() => router.back()} className="text-sm text-muted-foreground hover:text-foreground mb-4 flex items-center gap-1">
        ← 返回
      </button>
      <div className="bg-card border rounded-lg">
        <div className="p-5 border-b">
          <h2 className="font-semibold text-lg">{email.subject || "(无主题)"}</h2>
          <p className="text-sm text-muted-foreground mt-1">
            来自: {email.from_name ? `${email.from_name} <${email.from_addr}>` : email.from_addr}
          </p>
          {email.received_at && (
            <p className="text-xs text-muted-foreground">
              {new Date(email.received_at).toLocaleString("zh-CN")}
            </p>
          )}
          <div className="flex gap-2 mt-2">
            {email.email_type && <Badge>{email.email_type}</Badge>}
            {email.language && <Badge>{email.language.toUpperCase()}</Badge>}
            {email.has_sensitive && <Badge variant="destructive">敏感词</Badge>}
          </div>
        </div>

        <div className="flex border-b">
          {(["email", "audit"] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                tab === t ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "email" ? "邮件内容" : "处理链路"}
            </button>
          ))}
        </div>

        <div className="p-5">
          {tab === "email" ? (
            <div>
              <div className="whitespace-pre-wrap text-sm font-mono bg-muted/30 rounded-md p-4 mb-4">
                {email.body_text || "(无正文)"}
              </div>
              {email.reply && (
                <div>
                  <h3 className="font-medium text-sm mb-2">AI 回复草稿</h3>
                  <div className={`rounded-md p-4 text-sm whitespace-pre-wrap border ${
                    email.reply.status === "sent" ? "border-green-200 bg-green-50" : "border-yellow-200 bg-yellow-50"
                  }`}>
                    {email.reply.final_content || email.reply.draft_content}
                    <p className="mt-2 text-xs text-muted-foreground">
                      策略: {email.reply.send_strategy} · 状态: {email.reply.status}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {audit.length === 0 && <p className="text-muted-foreground text-sm">暂无审计记录</p>}
              {audit.map((entry, i) => (
                <div key={i} className="flex gap-3">
                  <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${
                    entry.status === "success" ? "bg-green-500" : "bg-red-500"
                  }`} />
                  <div>
                    <p className="text-sm font-medium">{STAGE_LABELS[entry.stage] || entry.stage}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(entry.created_at).toLocaleTimeString("zh-CN")}
                    </p>
                    {entry.error_msg && (
                      <p className="text-xs text-destructive mt-1">{entry.error_msg}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Badge({ children, variant }: { children: React.ReactNode; variant?: "destructive" }) {
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
      variant === "destructive" ? "bg-red-100 text-red-700" : "bg-muted text-muted-foreground"
    }`}>
      {children}
    </span>
  );
}
