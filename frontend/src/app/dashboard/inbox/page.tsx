"use client";
import { useEffect, useRef, useState } from "react";
import { api, EmailSummary } from "@/lib/api";
import { useRouter } from "next/navigation";

const TYPE_LABELS: Record<string, string> = {
  customer_inquiry: "客户咨询",
  quote_request: "报价请求",
  material_request: "资料索取",
  complaint: "投诉",
  payment_reminder: "催付款",
  order_confirm: "订单确认",
  supplier: "供应商",
  resume: "简历投递",
  partnership: "合作邀约",
  legal: "法律函件",
  spam: "垃圾邮件",
  ad_no_reply: "广告",
  other: "其他",
};

const URGENCY_COLOR: Record<number, string> = {
  1: "text-green-600",
  2: "text-yellow-600",
  3: "text-red-600",
};

const POLL_MS = 10000; // auto-refresh every 10s

export default function InboxPage() {
  const [emails, setEmails] = useState<EmailSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const router = useRouter();
  const seenIds = useRef<Set<string>>(new Set());
  const [flashIds, setFlashIds] = useState<Set<string>>(new Set());

  async function refresh() {
    try {
      const r = await api.emails.list({ limit: 50 });
      // detect newly-arrived emails to briefly highlight them
      const fresh = new Set<string>();
      for (const e of r.items) if (!seenIds.current.has(e.id)) fresh.add(e.id);
      if (seenIds.current.size > 0 && fresh.size > 0) {
        setFlashIds(fresh);
        setTimeout(() => setFlashIds(new Set()), 4000);
      }
      r.items.forEach(e => seenIds.current.add(e.id));
      setEmails(r.items);
      setTotal(r.total);
      setLastUpdated(new Date());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function syncNow() {
    setSyncing(true);
    try {
      await api.emails.sync();
      // give the worker a moment to fetch, then poll a few times
      for (let i = 0; i < 4; i++) {
        await new Promise(r => setTimeout(r, 2000));
        await refresh();
      }
    } catch (e: any) {
      alert("收取失败: " + e.message);
    } finally {
      setSyncing(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("删除这封邮件?会同时从 Gmail 收件箱移除。")) return;
    // optimistic removal
    setEmails(list => list.filter(x => x.id !== id));
    try {
      const r = await api.emails.remove(id);
      if (!r.gmail_removed) {
        // local delete succeeded; Gmail removal may have been skipped (inactive account)
      }
    } catch (e: any) {
      alert("删除失败: " + e.message);
      refresh();
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">收件箱</h1>
          <span className="text-sm text-slate-400">共 {total} 封</span>
          <span className="flex items-center gap-1 text-xs text-green-600">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            实时
          </span>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-slate-400">
              更新于 {lastUpdated.toLocaleTimeString("zh-CN")}
            </span>
          )}
          <button
            onClick={syncNow}
            disabled={syncing}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {syncing ? "收取中..." : "立即收取"}
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-slate-400 text-sm">加载中...</p>
      ) : emails.length === 0 ? (
        <p className="text-slate-400 text-sm">暂无邮件。点击「立即收取」从邮箱拉取,或等待自动同步。</p>
      ) : (
        <div className="space-y-2">
          {emails.map(e => (
            <div
              key={e.id}
              className={`group bg-card border rounded-lg p-4 cursor-pointer transition-colors ${
                flashIds.has(e.id) ? "border-green-400 bg-green-50" : "border-slate-200 hover:border-blue-300"
              }`}
              onClick={() => router.push(`/dashboard/inbox/${e.id}`)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-medium text-sm truncate">
                    {flashIds.has(e.id) && <span className="text-green-600 mr-1">●</span>}
                    {e.subject || "(无主题)"}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {e.from_name ? `${e.from_name} <${e.from_addr}>` : e.from_addr}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  {e.received_at && (
                    <span className="text-xs text-slate-400">
                      {new Date(e.received_at).toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </span>
                  )}
                  <div className="flex gap-1 items-center">
                    {e.has_sensitive && (
                      <span className="px-1.5 py-0.5 rounded text-xs bg-red-100 text-red-700 font-medium">敏感</span>
                    )}
                    {e.email_type && (
                      <span className="px-1.5 py-0.5 rounded text-xs bg-slate-100 text-slate-600">
                        {TYPE_LABELS[e.email_type] || e.email_type}
                      </span>
                    )}
                    {e.urgency && (
                      <span className={`text-xs font-medium ${URGENCY_COLOR[e.urgency]}`}>
                        {e.urgency === 3 ? "紧急" : e.urgency === 2 ? "中" : "低"}
                      </span>
                    )}
                    <button
                      onClick={ev => { ev.stopPropagation(); remove(e.id); }}
                      className="ml-1 text-xs text-slate-300 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                      title="删除(同步到 Gmail)"
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
