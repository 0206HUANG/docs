"use client";
import { useEffect, useState } from "react";
import { api, ResumeProfile } from "@/lib/api";

function MatchBadge({ score }: { score: number }) {
  const color = score >= 70 ? "bg-green-100 text-green-700" : score >= 40 ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500";
  return <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${color}`}>{score}分</span>;
}

export default function ResumesPage() {
  const [resumes, setResumes] = useState<ResumeProfile[]>([]);
  const [selected, setSelected] = useState<ResumeProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.resumes.list().then(r => { setResumes(r); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  return (
    <div className="flex gap-6 h-full">
      <div className="w-72 shrink-0">
        <h1 className="text-xl font-semibold mb-4">简历库</h1>
        {loading ? (
          <p className="text-sm text-slate-400">加载中...</p>
        ) : resumes.length === 0 ? (
          <p className="text-sm text-slate-400">暂无简历(收到求职邮件后 AI 自动解析)</p>
        ) : (
          <div className="space-y-2">
            {resumes.map(r => (
              <button
                key={r.id}
                onClick={() => setSelected(r)}
                className={`w-full text-left border rounded-lg p-3 transition-colors ${
                  selected?.id === r.id ? "border-blue-500 bg-blue-50" : "border-slate-200 bg-white hover:border-blue-300"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium truncate">{r.candidate_name || "(未知)"}</p>
                  {r.match_score != null && <MatchBadge score={r.match_score} />}
                </div>
                <p className="text-xs text-slate-500 mt-0.5 truncate">{r.desired_position || "—"}</p>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex-1">
        {selected ? (
          <div className="bg-white border border-slate-200 rounded-xl p-5 max-w-2xl">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-lg font-semibold">{selected.candidate_name || "(未知候选人)"}</h2>
                <p className="text-sm text-slate-500 mt-0.5">
                  {selected.candidate_email} · {selected.candidate_phone}
                </p>
              </div>
              {selected.match_score != null && (
                <div className="text-right">
                  <MatchBadge score={selected.match_score} />
                  <p className="text-xs text-slate-400 mt-1 max-w-[160px]">{selected.match_notes}</p>
                </div>
              )}
            </div>

            <div className="grid grid-cols-3 gap-3 mt-4">
              <Field label="期望岗位" value={selected.desired_position} />
              <Field label="期望薪资" value={selected.expected_salary} />
              <Field label="工作年限" value={selected.years_experience != null ? `${selected.years_experience} 年` : null} />
            </div>

            {selected.summary && (
              <div className="mt-4 bg-slate-50 rounded-lg p-3 text-sm text-slate-700">{selected.summary}</div>
            )}

            <Section title="教育背景">
              {selected.education.map((e, i) => (
                <div key={i} className="text-sm">
                  <span className="font-medium">{e.school}</span>
                  <span className="text-slate-500"> · {e.degree} · {e.major} · {e.year}</span>
                </div>
              ))}
            </Section>

            <Section title="工作经历">
              {selected.experience.map((e, i) => (
                <div key={i} className="text-sm">
                  <p><span className="font-medium">{e.company}</span> · {e.title} <span className="text-slate-400">({e.duration})</span></p>
                  {e.summary && <p className="text-xs text-slate-500 mt-0.5">{e.summary}</p>}
                </div>
              ))}
            </Section>

            {selected.skills.length > 0 && (
              <Section title="技能">
                <div className="flex flex-wrap gap-1.5">
                  {selected.skills.map((s, i) => (
                    <span key={i} className="text-xs bg-blue-50 text-blue-700 rounded px-2 py-0.5">{s}</span>
                  ))}
                </div>
              </Section>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 text-slate-400 text-sm">← 选择候选人查看简历详情</div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="bg-slate-50 rounded-lg p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm font-medium mt-0.5">{value || "—"}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-5">
      <h3 className="font-medium text-sm mb-2 text-slate-700">{title}</h3>
      <div className="space-y-2">{children}</div>
    </div>
  );
}
