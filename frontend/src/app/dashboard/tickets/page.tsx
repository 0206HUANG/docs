"use client";
import { useEffect, useState } from "react";
import { api, Ticket } from "@/lib/api";
import { LiveBadge } from "@/lib/useLivePolling";

const STATUS_STYLES: Record<string, string> = {
  open: "bg-blue-100 text-blue-700",
  claimed: "bg-yellow-100 text-yellow-700",
  resolved: "bg-green-100 text-green-700",
  closed: "bg-gray-100 text-gray-600",
};

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [replyText, setReplyText] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = () =>
    api.tickets.list(filter || undefined).then(t => { setTickets(t); setLastUpdated(new Date()); }).catch(console.error);

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  async function handleClaim(id: string) {
    await api.tickets.claim(id).catch(console.error);
    load();
  }

  async function handleResolve(id: string) {
    await api.tickets.resolve(id).catch(console.error);
    load();
    setSelected(null);
  }

  async function handleReply(id: string) {
    if (!replyText.trim()) return;
    await api.tickets.reply(id, replyText).catch(console.error);
    setReplyText("");
    const updated = await api.tickets.get(id);
    setSelected(updated);
  }

  return (
    <div className="flex gap-6 h-full">
      <div className="w-80 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">工单</h1>
            <LiveBadge lastUpdated={lastUpdated} />
          </div>
          <select
            className="text-xs border rounded-md px-2 py-1"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          >
            <option value="">全部</option>
            <option value="open">待处理</option>
            <option value="claimed">处理中</option>
            <option value="resolved">已解决</option>
          </select>
        </div>
        <div className="space-y-2">
          {tickets.map(t => (
            <div
              key={t.id}
              onClick={() => api.tickets.get(t.id).then(setSelected)}
              className={`border rounded-lg p-3 cursor-pointer hover:border-primary/40 transition-colors ${selected?.id === t.id ? "border-primary" : ""}`}
            >
              <p className="text-sm font-medium truncate">{t.title}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_STYLES[t.status]}`}>
                  {t.status}
                </span>
                <span className="text-xs text-muted-foreground">优先级 {t.priority}</span>
              </div>
            </div>
          ))}
          {tickets.length === 0 && <p className="text-muted-foreground text-sm">暂无工单</p>}
        </div>
      </div>

      {selected && (
        <div className="flex-1 bg-card border rounded-lg flex flex-col">
          <div className="p-4 border-b">
            <h2 className="font-medium">{selected.title}</h2>
            <p className="text-sm text-muted-foreground">原因: {selected.reason}</p>
          </div>
          <div className="flex-1 p-4 space-y-2 overflow-auto">
            {(selected.replies || []).map(r => (
              <div key={r.id} className="bg-muted/30 rounded p-3 text-sm">{r.content}</div>
            ))}
          </div>
          <div className="p-4 border-t space-y-3">
            <textarea
              className="w-full border rounded-md p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary"
              rows={3}
              placeholder="添加备注..."
              value={replyText}
              onChange={e => setReplyText(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                onClick={() => handleReply(selected.id)}
                className="px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
              >
                添加备注
              </button>
              {selected.status === "open" && (
                <button
                  onClick={() => handleClaim(selected.id)}
                  className="px-3 py-1.5 text-sm border rounded-md hover:bg-muted"
                >
                  认领工单
                </button>
              )}
              {["open", "claimed"].includes(selected.status) && (
                <button
                  onClick={() => handleResolve(selected.id)}
                  className="px-3 py-1.5 text-sm border border-green-300 text-green-700 rounded-md hover:bg-green-50"
                >
                  标记解决
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
