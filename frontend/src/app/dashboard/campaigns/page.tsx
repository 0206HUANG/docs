"use client";
import { useEffect, useState } from "react";
import { api, Account, CampaignDetail, CampaignSummary } from "@/lib/api";

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600",
  running: "bg-green-100 text-green-700",
  paused: "bg-amber-100 text-amber-700",
  completed: "bg-blue-100 text-blue-700",
};
const RECIP_CN: Record<string, string> = {
  pending: "待发", sent: "跟进中", replied: "已回复", completed: "已完成", failed: "失败",
};

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [detail, setDetail] = useState<CampaignDetail | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [showCreate, setShowCreate] = useState(false);

  const load = () => api.campaigns.list().then(setCampaigns).catch(console.error);
  useEffect(() => { load(); api.accounts.list().then(setAccounts).catch(() => {}); }, []);

  const openDetail = async (id: string) => setDetail(await api.campaigns.get(id));
  async function toggle(c: CampaignSummary) {
    if (c.status === "running") await api.campaigns.pause(c.id);
    else await api.campaigns.start(c.id);
    load();
    if (detail?.id === c.id) openDetail(c.id);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">营销活动 / 主动发件</h1>
        <button onClick={() => setShowCreate(true)} className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-md hover:bg-blue-700">
          + 新建活动
        </button>
      </div>

      <div className="grid grid-cols-2 gap-6 max-w-4xl">
        <div className="space-y-3">
          {campaigns.map(c => (
            <div key={c.id} onClick={() => openDetail(c.id)}
              className={`bg-white border rounded-xl p-4 cursor-pointer transition-colors ${
                detail?.id === c.id ? "border-blue-500" : "border-slate-200 hover:border-blue-300"
              }`}>
              <div className="flex items-center justify-between">
                <p className="font-medium text-sm">{c.name}</p>
                <span className={`text-xs px-2 py-0.5 rounded ${STATUS_STYLE[c.status]}`}>{c.status}</span>
              </div>
              <p className="text-xs text-slate-500 mt-1">{c.sop_steps} 轮跟进 · 间隔 {c.sop_interval_hours}h</p>
              <div className="flex flex-wrap gap-2 mt-2 text-xs text-slate-500">
                {Object.entries(c.recipients).map(([s, n]) => (
                  <span key={s} className="bg-slate-50 rounded px-1.5 py-0.5">{RECIP_CN[s] || s}: {n}</span>
                ))}
              </div>
              <button onClick={e => { e.stopPropagation(); toggle(c); }}
                className="mt-2 text-xs border border-slate-200 rounded px-2 py-1 hover:bg-slate-50">
                {c.status === "running" ? "暂停" : "启动"}
              </button>
            </div>
          ))}
          {campaigns.length === 0 && <p className="text-sm text-slate-400">暂无活动,点击右上角新建</p>}
        </div>

        <div>
          {detail && (
            <div className="bg-white border border-slate-200 rounded-xl p-4">
              <h2 className="font-medium">{detail.name}</h2>
              <p className="text-xs text-slate-500 mt-1">主题模板:{detail.subject_template}</p>
              <h3 className="text-sm font-medium mt-3 mb-2">收件人 ({detail.recipients.length})</h3>
              <div className="space-y-1">
                {detail.recipients.map(r => (
                  <div key={r.id} className="flex items-center justify-between text-sm border-b border-slate-100 py-1.5">
                    <span className="truncate">{r.name || r.email}</span>
                    <span className="text-xs text-slate-500">第 {r.current_step} 封 · {RECIP_CN[r.status] || r.status}</span>
                  </div>
                ))}
                {detail.recipients.length === 0 && <p className="text-sm text-slate-400">暂无收件人</p>}
              </div>
            </div>
          )}
        </div>
      </div>

      {showCreate && (
        <CreateModal accounts={accounts} onClose={() => setShowCreate(false)} onDone={() => { setShowCreate(false); load(); }} />
      )}
    </div>
  );
}

function CreateModal({ accounts, onClose, onDone }: { accounts: Account[]; onClose: () => void; onDone: () => void }) {
  const [form, setForm] = useState({
    account_id: accounts[0]?.id || "", name: "", subject_template: "", body_template: "",
    sop_steps: 2, sop_interval_hours: 72,
  });
  const [recipients, setRecipients] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit() {
    setSaving(true);
    try {
      const { id } = await api.campaigns.create(form);
      const list = recipients.split("\n").map(l => l.trim()).filter(Boolean).map(email => ({ email }));
      if (list.length) await api.campaigns.addRecipients(id, list);
      onDone();
    } catch (e: any) { alert(e.message); } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 overflow-y-auto py-8">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-lg">新建营销活动</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl">×</button>
        </div>
        <div className="space-y-3">
          <F label="发送邮箱">
            <select className={inp} value={form.account_id} onChange={e => setForm(f => ({ ...f, account_id: e.target.value }))}>
              {accounts.map(a => <option key={a.id} value={a.id}>{a.email_address}</option>)}
            </select>
          </F>
          <F label="活动名称"><input className={inp} value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="例:Q3 客户开发" /></F>
          <F label="主题模板（{name} 为收件人变量）"><input className={inp} value={form.subject_template} onChange={e => setForm(f => ({ ...f, subject_template: e.target.value }))} placeholder="您好 {name}，关于合作洽谈" /></F>
          <F label="正文模板"><textarea className={inp} rows={4} value={form.body_template} onChange={e => setForm(f => ({ ...f, body_template: e.target.value }))} placeholder="{name} 您好，我们是……" /></F>
          <div className="grid grid-cols-2 gap-3">
            <F label="跟进轮数（含首封）"><input className={inp} type="number" value={form.sop_steps} onChange={e => setForm(f => ({ ...f, sop_steps: +e.target.value }))} /></F>
            <F label="间隔（小时）"><input className={inp} type="number" value={form.sop_interval_hours} onChange={e => setForm(f => ({ ...f, sop_interval_hours: +e.target.value }))} /></F>
          </div>
          <F label="收件人（每行一个邮箱）"><textarea className={inp} rows={4} value={recipients} onChange={e => setRecipients(e.target.value)} placeholder={"a@company.com\nb@company.com"} /></F>
          <button onClick={submit} disabled={saving || !form.name || !form.account_id}
            className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {saving ? "创建中..." : "创建（草稿，需手动启动）"}
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
