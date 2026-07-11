"use client";
import { useEffect, useState } from "react";
import { api, Account } from "@/lib/api";

const PROVIDERS = [
  { value: "generic", label: "通用 IMAP/SMTP" },
  { value: "gmail", label: "Gmail" },
  { value: "outlook", label: "Outlook / Exchange" },
  { value: "qq", label: "QQ企业邮" },
  { value: "163", label: "网易企业邮" },
  { value: "exmail", label: "腾讯企业邮" },
];

const PROVIDER_DEFAULTS: Record<string, { imap_host: string; imap_port: number; smtp_host: string; smtp_port: number }> = {
  gmail: { imap_host: "imap.gmail.com", imap_port: 993, smtp_host: "smtp.gmail.com", smtp_port: 465 },
  outlook: { imap_host: "outlook.office365.com", imap_port: 993, smtp_host: "smtp.office365.com", smtp_port: 587 },
  qq: { imap_host: "imap.exmail.qq.com", imap_port: 993, smtp_host: "smtp.exmail.qq.com", smtp_port: 465 },
  "163": { imap_host: "imap.qiye.163.com", imap_port: 993, smtp_host: "smtp.qiye.163.com", smtp_port: 465 },
  exmail: { imap_host: "imap.exmail.qq.com", imap_port: 993, smtp_host: "smtp.exmail.qq.com", smtp_port: 465 },
  generic: { imap_host: "", imap_port: 993, smtp_host: "", smtp_port: 465 },
};

const POSITIONINGS = ["general", "sales", "hr", "finance", "support", "legal", "supplier"];

const empty = {
  email_address: "", display_name: "", provider: "generic",
  imap_host: "", imap_port: 993, smtp_host: "", smtp_port: 465,
  username: "", password: "", positioning: "general",
};

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [testing, setTesting] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const load = () => api.accounts.list().then(setAccounts).catch(console.error);
  useEffect(() => { load(); }, []);

  function patchProvider(p: string) {
    const defaults = PROVIDER_DEFAULTS[p] || PROVIDER_DEFAULTS.generic;
    setForm(f => ({ ...f, provider: p, ...defaults, username: f.email_address }));
  }

  async function toggleAccount(id: string) {
    await api.accounts.toggle(id).catch(console.error);
    load();
  }

  async function testAccount(id: string) {
    setTesting(id);
    try {
      const r = await api.accounts.test(id);
      alert(r.success ? "✅ 连接成功" : "❌ 连接失败");
    } catch (e: any) {
      alert("连接失败: " + e.message);
    } finally { setTesting(null); }
  }

  async function addAccount() {
    setSaving(true);
    try {
      await api.createAccount(form);
      setForm(empty);
      setShowAdd(false);
      load();
    } catch (e: any) {
      alert("添加失败: " + e.message);
    } finally { setSaving(false); }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">邮箱账号</h1>
        <button
          onClick={() => setShowAdd(true)}
          className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-md hover:bg-blue-700"
        >
          + 绑定邮箱
        </button>
      </div>

      <div className="space-y-3 max-w-2xl">
        {accounts.map(a => (
          <div key={a.id} className="bg-white border border-slate-200 rounded-xl p-4 flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">{a.email_address}</p>
              <p className="text-xs text-slate-500 mt-0.5">
                {a.display_name && <span>{a.display_name} · </span>}
                定位: <span className="font-medium">{a.positioning}</span>
                {" · "}同步: {a.sync_status}
                {a.last_synced_at && ` · 上次: ${new Date(a.last_synced_at).toLocaleString("zh-CN")}`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                a.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"
              }`}>
                {a.is_active ? "运行中" : "已停止"}
              </span>
              <button
                onClick={() => testAccount(a.id)}
                disabled={testing === a.id}
                className="text-xs border border-slate-200 rounded-md px-2.5 py-1 hover:bg-slate-50 disabled:opacity-50"
              >
                {testing === a.id ? "测试中..." : "测试"}
              </button>
              <button
                onClick={() => toggleAccount(a.id)}
                className={`text-xs border rounded-md px-2.5 py-1 ${
                  a.is_active
                    ? "border-red-200 text-red-600 hover:bg-red-50"
                    : "border-green-200 text-green-600 hover:bg-green-50"
                }`}
              >
                {a.is_active ? "停止" : "启用"}
              </button>
            </div>
          </div>
        ))}
        {accounts.length === 0 && (
          <div className="text-center py-12 text-slate-400">
            <p className="text-sm">暂无绑定邮箱</p>
            <p className="text-xs mt-1">点击右上角「绑定邮箱」添加企业邮箱账号</p>
          </div>
        )}
      </div>

      {showAdd && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 overflow-y-auto py-8">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-semibold text-lg">绑定新邮箱账号</h3>
              <button onClick={() => setShowAdd(false)} className="text-slate-400 hover:text-slate-600 text-xl">×</button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <F label="邮箱地址">
                  <input className={inp} value={form.email_address}
                    onChange={e => setForm(f => ({ ...f, email_address: e.target.value, username: e.target.value }))}
                    placeholder="sales@company.com" />
                </F>
                <F label="显示名称">
                  <input className={inp} value={form.display_name}
                    onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                    placeholder="Sales Team" />
                </F>
              </div>
              <F label="邮箱服务商">
                <select className={inp} value={form.provider}
                  onChange={e => patchProvider(e.target.value)}>
                  {PROVIDERS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </F>
              <div className="grid grid-cols-2 gap-3">
                <F label="IMAP 服务器">
                  <input className={inp} value={form.imap_host}
                    onChange={e => setForm(f => ({ ...f, imap_host: e.target.value }))} />
                </F>
                <F label="IMAP 端口">
                  <input className={inp} type="number" value={form.imap_port}
                    onChange={e => setForm(f => ({ ...f, imap_port: +e.target.value }))} />
                </F>
                <F label="SMTP 服务器">
                  <input className={inp} value={form.smtp_host}
                    onChange={e => setForm(f => ({ ...f, smtp_host: e.target.value }))} />
                </F>
                <F label="SMTP 端口">
                  <input className={inp} type="number" value={form.smtp_port}
                    onChange={e => setForm(f => ({ ...f, smtp_port: +e.target.value }))} />
                </F>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <F label="登录用户名">
                  <input className={inp} value={form.username}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
                </F>
                <F label="密码 / 授权码">
                  <input className={inp} type="password" value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
                </F>
              </div>
              <F label="邮箱定位">
                <select className={inp} value={form.positioning}
                  onChange={e => setForm(f => ({ ...f, positioning: e.target.value }))}>
                  {POSITIONINGS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </F>
              <button
                onClick={addAccount}
                disabled={saving || !form.email_address || !form.imap_host || !form.smtp_host || !form.password}
                className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 mt-2"
              >
                {saving ? "绑定中..." : "绑定账号"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const inp = "w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

function F({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-600 mb-1">{label}</label>
      {children}
    </div>
  );
}
