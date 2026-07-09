"use client";
import { useEffect, useState } from "react";
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

export default function InboxPage() {
  const [emails, setEmails] = useState<EmailSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    api.emails.list({ limit: 50 })
      .then(r => { setEmails(r.items); setTotal(r.total); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">收件箱</h1>
        <span className="text-sm text-muted-foreground">共 {total} 封</span>
      </div>
      {loading ? (
        <p className="text-muted-foreground text-sm">加载中...</p>
      ) : emails.length === 0 ? (
        <p className="text-muted-foreground text-sm">暂无邮件</p>
      ) : (
        <div className="space-y-2">
          {emails.map(e => (
            <div
              key={e.id}
              className="bg-card border rounded-lg p-4 cursor-pointer hover:border-primary/40 transition-colors"
              onClick={() => router.push(`/dashboard/inbox/${e.id}`)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-medium text-sm truncate">{e.subject || "(无主题)"}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {e.from_name ? `${e.from_name} <${e.from_addr}>` : e.from_addr}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  {e.received_at && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(e.received_at).toLocaleDateString("zh-CN")}
                    </span>
                  )}
                  <div className="flex gap-1">
                    {e.has_sensitive && (
                      <span className="px-1.5 py-0.5 rounded text-xs bg-red-100 text-red-700 font-medium">敏感</span>
                    )}
                    {e.email_type && (
                      <span className="px-1.5 py-0.5 rounded text-xs bg-muted text-muted-foreground">
                        {TYPE_LABELS[e.email_type] || e.email_type}
                      </span>
                    )}
                    {e.urgency && (
                      <span className={`text-xs font-medium ${URGENCY_COLOR[e.urgency]}`}>
                        {e.urgency === 3 ? "紧急" : e.urgency === 2 ? "中" : "低"}
                      </span>
                    )}
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
