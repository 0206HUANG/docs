"use client";
import { useEffect, useState } from "react";
import { api, Account } from "@/lib/api";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [testing, setTesting] = useState<string | null>(null);

  const load = () => api.accounts.list().then(setAccounts).catch(console.error);
  useEffect(() => { load(); }, []);

  async function toggleAccount(id: string) {
    await api.accounts.toggle(id).catch(console.error);
    load();
  }

  async function testAccount(id: string) {
    setTesting(id);
    try {
      const r = await api.accounts.test(id);
      alert(r.success ? "连接成功" : "连接失败");
    } catch (e: any) {
      alert("连接失败: " + e.message);
    } finally {
      setTesting(null);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-6">邮箱账号</h1>
      <div className="space-y-3">
        {accounts.map(a => (
          <div key={a.id} className="bg-card border rounded-lg p-4 flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">{a.email_address}</p>
              <p className="text-xs text-muted-foreground">
                定位: {a.positioning} · 状态: {a.sync_status}
                {a.last_synced_at && ` · 上次同步: ${new Date(a.last_synced_at).toLocaleString("zh-CN")}`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${a.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                {a.is_active ? "运行中" : "已停止"}
              </span>
              <button
                onClick={() => testAccount(a.id)}
                disabled={testing === a.id}
                className="text-xs border rounded-md px-2 py-1 hover:bg-muted disabled:opacity-50"
              >
                {testing === a.id ? "测试中..." : "测试连接"}
              </button>
              <button
                onClick={() => toggleAccount(a.id)}
                className="text-xs border rounded-md px-2 py-1 hover:bg-muted"
              >
                {a.is_active ? "停止" : "启用"}
              </button>
            </div>
          </div>
        ))}
        {accounts.length === 0 && (
          <p className="text-muted-foreground text-sm">暂无绑定邮箱。请联系管理员添加。</p>
        )}
      </div>
    </div>
  );
}
