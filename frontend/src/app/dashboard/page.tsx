"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Stats = {
  emails_today: number;
  emails_week: number;
  open_tickets: number;
  auto_sent_week: number;
  high_risk_week: number;
};

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [user, setUser] = useState<{ name: string; email: string; roles: string[] } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.me().then(setUser).catch(() => {});
    api.stats().then(setStats).catch(e => setError(e.message));
  }, []);

  const autoRate = stats && stats.emails_week > 0
    ? Math.round((stats.auto_sent_week / stats.emails_week) * 100)
    : null;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-slate-900">
          {user ? `你好，${user.name}` : "概览"}
        </h1>
        {user && (
          <p className="text-sm text-slate-500 mt-0.5">
            {user.email} · {user.roles.join(", ")}
          </p>
        )}
      </div>

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 mb-4 text-sm text-amber-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 max-w-2xl">
        <StatCard
          title="今日收件"
          value={stats?.emails_today ?? "—"}
          sub="封邮件"
          color="blue"
        />
        <StatCard
          title="本周收件"
          value={stats?.emails_week ?? "—"}
          sub="封邮件"
          color="indigo"
        />
        <StatCard
          title="待处理工单"
          value={stats?.open_tickets ?? "—"}
          sub="个工单"
          color="amber"
        />
        <StatCard
          title="本周 AI 处理"
          value={stats?.auto_sent_week ?? "—"}
          sub="封自动处理"
          color="green"
        />
        <StatCard
          title="高风险拦截"
          value={stats?.high_risk_week ?? "—"}
          sub="封本周"
          color="red"
        />
        <StatCard
          title="AI 处理率"
          value={autoRate !== null ? `${autoRate}%` : "—"}
          sub="本周自动化"
          color="purple"
        />
      </div>

      <div className="mt-8 max-w-2xl bg-slate-50 border border-slate-200 rounded-xl p-5">
        <h2 className="font-medium text-slate-800 mb-3">系统说明</h2>
        <ul className="text-sm text-slate-600 space-y-1.5">
          <li>• 邮件收到后自动分类、检索知识库、生成回复</li>
          <li>• 含敏感词的邮件强制转人工，触发工单</li>
          <li>• 普通咨询自动回复，报价/投诉等进入草稿审核队列</li>
          <li>• 每日/周/月自动生成处理总结报告</li>
        </ul>
      </div>
    </div>
  );
}

function StatCard({
  title, value, sub, color,
}: {
  title: string;
  value: number | string;
  sub: string;
  color: "blue" | "indigo" | "amber" | "green" | "red" | "purple";
}) {
  const colors = {
    blue: "bg-blue-50 border-blue-100",
    indigo: "bg-indigo-50 border-indigo-100",
    amber: "bg-amber-50 border-amber-100",
    green: "bg-green-50 border-green-100",
    red: "bg-red-50 border-red-100",
    purple: "bg-purple-50 border-purple-100",
  };
  const textColors = {
    blue: "text-blue-700",
    indigo: "text-indigo-700",
    amber: "text-amber-700",
    green: "text-green-700",
    red: "text-red-700",
    purple: "text-purple-700",
  };
  return (
    <div className={`border rounded-xl p-5 ${colors[color]}`}>
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{title}</p>
      <p className={`text-3xl font-bold mt-1 ${textColors[color]}`}>{value}</p>
      <p className="text-xs text-slate-400 mt-0.5">{sub}</p>
    </div>
  );
}
