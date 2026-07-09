"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<{ emails_today: number; open_tickets: number } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.stats().then(setStats).catch(e => setError(e.message));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold mb-6">概览</h1>
      {error && <p className="text-destructive text-sm mb-4">{error}</p>}
      <div className="grid grid-cols-2 gap-4 max-w-lg">
        <StatCard title="今日收件" value={stats?.emails_today ?? "—"} />
        <StatCard title="待处理工单" value={stats?.open_tickets ?? "—"} />
      </div>
    </div>
  );
}

function StatCard({ title, value }: { title: string; value: number | string }) {
  return (
    <div className="bg-card border rounded-lg p-5">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
    </div>
  );
}
