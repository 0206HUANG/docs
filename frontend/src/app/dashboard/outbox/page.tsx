"use client";
import { useEffect, useState } from "react";
import { api, Account, ScheduledEmailT } from "@/lib/api";
import { LiveBadge } from "@/lib/useLivePolling";

const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  sent: "bg-green-100 text-green-700",
  cancelled: "bg-slate-100 text-slate-500",
  failed: "bg-red-100 text-red-700",
};
const STATUS_CN: Record<string, string> = {
  pending: "待发送", sent: "已发送", cancelled: "已撤回", failed: "失败",
};

function fmt(s: string | null) {
  return s ? new Date(s).toLocaleString("zh-CN") : "—";
}

export default function OutboxPage() {
  const [items, setItems] = useState<ScheduledEmailT[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [showCreate, setShowCreate] = useState(false);

  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const load = () => api.outbox.list().then(i => { setItems(i); setLastUpdated(new Date()); }).catch(console.error);
  useEffect(() => {
    load();
    api.accounts.list().then(setAccounts).catch(() => {});
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  async function cancel(id: string) {
    try { await api.outbox.cancel(id); load(); } catch (e: any) { alert(e.message); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold">定时发送</h1>
          <LiveBadge lastUpdated={lastUpdated} />
        </div>
        <button onClick={() => setShowCreate(true)} className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-md hover:bg-blue-700">
          + 定时发送
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden max-w-4xl">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">收件人</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">主题</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">计划时间</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">状态</th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-slate-500">打开</th>
              <th className="px-4 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {items.map(s => (
              <tr key={s.id} className="border-b border-slate-100">
                <td className="px-4 py-2.5 text-slate-600">{(s.to_addrs || []).join(", ")}</td>
                <td className="px-4 py-2.5">{s.subject}</td>
                <td className="px-4 py-2.5 text-slate-500 text-xs">{fmt(s.scheduled_at)}</td>
                <td className="px-4 py-2.5">
                  <span className={`text-xs px-2 py-0.5 rounded ${STATUS_STYLE[s.status]}`}>{STATUS_CN[s.status] || s.status}</span>
                </td>
                <td className="px-4 py-2.5 text-xs">
                  {s.track_opens ? (s.open_count > 0 ? `${s.open_count} 次 ✓` : "未打开") : "—"}
                </td>
                <td className="px-4 py-2.5 text-right">
                  {s.status === "pending" && (
                    <button onClick={() => cancel(s.id)} className="text-xs text-red-600 hover:text-red-700">撤回</button>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400 text-sm">暂无定时邮件</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {showCreate && (
        <CreateModal accounts={accounts} onClose={() => setShowCreate(false)} onDone={() => { setShowCreate(false); load(); }} />
      )}
    </div>
  );
}

function CreateModal({ accounts, onClose, onDone }: { accounts: Account[]; onClose: () => void; onDone: () => void }) {
  const usable = accounts.filter(a => a.is_active);
  const [form, setForm] = useState({
    account_id: usable[0]?.id || "", to: "", subject: "", body_text: "",
    delay_minutes: 5, track_opens: true,
  });
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    try {
      await api.outbox.schedule({
        account_id: form.account_id,
        to_addrs: form.to.split(",").map(s => s.trim()).filter(Boolean),
        subject: form.subject, body_text: form.body_text,
        delay_minutes: form.delay_minutes, track_opens: form.track_opens,
      });
      onDone();
    } catch (e: any) { alert(e.message); } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 overflow-y-auto py-8">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-lg">定时发送邮件</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl">×</button>
        </div>
        <div className="space-y-3">
          <F label="发送邮箱">
            <select className={inp} value={form.account_id} onChange={e => setForm(f => ({ ...f, account_id: e.target.value }))}>
              {usable.length === 0 && <option value="">（无已启用邮箱,请先在「邮箱账号」启用）</option>}
              {usable.map(a => <option key={a.id} value={a.id}>{a.email_address}</option>)}
            </select>
          </F>
          <F label="收件人（逗号分隔）"><input className={inp} value={form.to} onChange={e => setForm(f => ({ ...f, to: e.target.value }))} placeholder="a@x.com, b@y.com" /></F>
          <F label="主题"><input className={inp} value={form.subject} onChange={e => setForm(f => ({ ...f, subject: e.target.value }))} /></F>
          <F label="正文"><textarea className={inp} rows={5} value={form.body_text} onChange={e => setForm(f => ({ ...f, body_text: e.target.value }))} /></F>
          <div className="grid grid-cols-2 gap-3 items-end">
            <F label="延迟发送（分钟后）"><input className={inp} type="number" value={form.delay_minutes} onChange={e => setForm(f => ({ ...f, delay_minutes: +e.target.value }))} /></F>
            <label className="flex items-center gap-2 text-sm text-slate-600 pb-2">
              <input type="checkbox" checked={form.track_opens} onChange={e => setForm(f => ({ ...f, track_opens: e.target.checked }))} />
              打开追踪
            </label>
          </div>
          <button onClick={submit} disabled={saving || !form.account_id || !form.to || !form.subject}
            className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {saving ? "排队中..." : "加入定时队列"}
          </button>
        </div>
      </div>
    </div>
  );
}

const inp = "w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";
function F({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>{children}</div>;
}
