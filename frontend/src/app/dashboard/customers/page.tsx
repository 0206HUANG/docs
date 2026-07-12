"use client";
import { useEffect, useState } from "react";
import { api, Customer, CustomerDetail } from "@/lib/api";

function fmt(s: string | null) {
  return s ? new Date(s).toLocaleString("zh-CN") : "—";
}

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selected, setSelected] = useState<CustomerDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.customers.list().then(c => { setCustomers(c); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  return (
    <div className="flex gap-6 h-full">
      <div className="w-80 shrink-0">
        <h1 className="text-xl font-semibold mb-4">客户画像</h1>
        {loading ? (
          <p className="text-sm text-slate-400">加载中...</p>
        ) : customers.length === 0 ? (
          <p className="text-sm text-slate-400">暂无客户(收到外部邮件后自动聚合建立)</p>
        ) : (
          <div className="space-y-2">
            {customers.map(c => (
              <button
                key={c.id}
                onClick={() => api.customers.get(c.id).then(setSelected)}
                className={`w-full text-left border rounded-lg p-3 transition-colors ${
                  selected?.id === c.id ? "border-blue-500 bg-blue-50" : "border-slate-200 bg-white hover:border-blue-300"
                }`}
              >
                <p className="text-sm font-medium truncate">{c.name || c.email}</p>
                <p className="text-xs text-slate-500 mt-0.5 truncate">{c.company} · {c.email_count} 封往来</p>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex-1">
        {selected ? (
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h2 className="text-lg font-semibold">{selected.name || selected.email}</h2>
            <p className="text-sm text-slate-500 mt-0.5">{selected.email} · {selected.company}</p>
            <div className="grid grid-cols-3 gap-3 mt-4 max-w-md">
              <Stat label="往来邮件" value={selected.email_count} />
              <Stat label="状态" value={selected.status} />
              <Stat label="重要度" value={selected.importance} />
            </div>
            <p className="text-xs text-slate-400 mt-3">
              首次往来: {fmt(selected.first_seen)} · 最近: {fmt(selected.last_seen)}
            </p>
            <h3 className="font-medium text-sm mt-6 mb-2">最近往来邮件</h3>
            <div className="space-y-2">
              {selected.recent_emails.map(e => (
                <div key={e.id} className="border border-slate-100 rounded-lg p-3">
                  <p className="text-sm font-medium">{e.subject || "(无主题)"}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{e.snippet}</p>
                  <p className="text-xs text-slate-400 mt-1">{fmt(e.received_at)}</p>
                </div>
              ))}
              {selected.recent_emails.length === 0 && <p className="text-sm text-slate-400">暂无往来记录</p>}
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 text-slate-400 text-sm">← 选择左侧客户查看画像</div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-slate-50 rounded-lg p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-semibold mt-0.5">{value}</p>
    </div>
  );
}
