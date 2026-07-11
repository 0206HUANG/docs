"use client";
import { useEffect, useState } from "react";
import { api, KBGroup } from "@/lib/api";

const CATEGORIES = ["general", "faq", "product", "hr", "finance", "legal", "supplier"];
const POSITIONINGS = ["sales", "hr", "finance", "support", "general", "legal"];
const EMAIL_TYPES = ["customer_inquiry", "quote_request", "complaint", "resume", "supplier", "payment_reminder", "other"];

export default function KBPage() {
  const [groups, setGroups] = useState<KBGroup[]>([]);
  const [selected, setSelected] = useState<KBGroup | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [showManual, setShowManual] = useState(false);
  const [loading, setLoading] = useState(true);

  const [newGroup, setNewGroup] = useState({ name: "", category: "general", positioning: [] as string[], email_types: [] as string[] });
  const [manualDoc, setManualDoc] = useState({ title: "", content: "" });
  const [saving, setSaving] = useState(false);

  const load = () => {
    api.kb.groups().then(g => { setGroups(g); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  function toggleItem(arr: string[], val: string): string[] {
    return arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val];
  }

  async function createGroup() {
    if (!newGroup.name.trim()) return;
    setSaving(true);
    try {
      await api.kb.createGroup(newGroup);
      setNewGroup({ name: "", category: "general", positioning: [], email_types: [] });
      setShowAdd(false);
      load();
    } catch (e: any) {
      alert(e.message);
    } finally { setSaving(false); }
  }

  async function addManual() {
    if (!selected || !manualDoc.title.trim() || !manualDoc.content.trim()) return;
    setSaving(true);
    try {
      await api.kb.addManual({ group_id: selected.id, ...manualDoc });
      setManualDoc({ title: "", content: "" });
      setShowManual(false);
      alert("话术已入库，正在后台处理 Embedding");
    } catch (e: any) {
      alert(e.message);
    } finally { setSaving(false); }
  }

  return (
    <div className="flex gap-6 h-full">
      {/* Left: group list */}
      <div className="w-64 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold">知识库</h1>
          <button
            onClick={() => setShowAdd(true)}
            className="text-xs bg-blue-600 text-white px-2.5 py-1.5 rounded-md hover:bg-blue-700"
          >
            + 新建分组
          </button>
        </div>
        {loading ? (
          <p className="text-sm text-slate-400">加载中...</p>
        ) : (
          <div className="space-y-1.5">
            {groups.map(g => (
              <button
                key={g.id}
                onClick={() => setSelected(g)}
                className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  selected?.id === g.id
                    ? "bg-blue-600 text-white"
                    : "bg-white border border-slate-200 hover:border-blue-300 text-slate-700"
                }`}
              >
                <p className="font-medium truncate">{g.name}</p>
                <p className={`text-xs mt-0.5 ${selected?.id === g.id ? "text-blue-100" : "text-slate-400"}`}>
                  {g.category} · {g.is_active ? "启用" : "停用"}
                </p>
              </button>
            ))}
            {groups.length === 0 && (
              <p className="text-sm text-slate-400 px-1">暂无知识库分组</p>
            )}
          </div>
        )}
      </div>

      {/* Right: group detail */}
      <div className="flex-1">
        {selected ? (
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold">{selected.name}</h2>
                <p className="text-sm text-slate-500">
                  分类: {selected.category} ·
                  定位: {selected.positioning.join(", ") || "全部"} ·
                  邮件类型: {selected.email_types.join(", ") || "全部"}
                </p>
              </div>
              <button
                onClick={() => setShowManual(true)}
                className="text-sm bg-green-600 text-white px-3 py-1.5 rounded-md hover:bg-green-700"
              >
                + 录入话术
              </button>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <p className="text-sm font-medium text-slate-700 mb-3">上传文档 (PDF / Word / TXT)</p>
              <div className="bg-white border-2 border-dashed border-slate-300 rounded-lg p-6 text-center">
                <p className="text-sm text-slate-500">拖拽文件到此处，或</p>
                <label className="mt-2 inline-block cursor-pointer text-sm text-blue-600 hover:text-blue-700 font-medium">
                  点击选择文件
                  <input type="file" className="hidden" accept=".pdf,.doc,.docx,.txt,.xlsx"
                    onChange={async (e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      const fd = new FormData();
                      fd.append("file", f);
                      fd.append("group_id", selected.id);
                      fd.append("title", f.name);
                      const token = localStorage.getItem("access_token");
                      const r = await fetch("/api/v1/kb/documents", {
                        method: "POST",
                        headers: { Authorization: `Bearer ${token}` },
                        body: fd,
                      });
                      if (r.ok) alert("上传成功，正在后台处理 Embedding");
                      else alert("上传失败: " + (await r.json()).detail);
                    }}
                  />
                </label>
                <p className="text-xs text-slate-400 mt-1">支持 PDF、Word、Excel、TXT，单文件 ≤ 50MB</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-48 text-slate-400 text-sm">
            ← 选择左侧知识库分组
          </div>
        )}
      </div>

      {/* Modal: new group */}
      {showAdd && (
        <Modal title="新建知识库分组" onClose={() => setShowAdd(false)}>
          <div className="space-y-4">
            <Field label="分组名称">
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="例：产品FAQ、招聘话术"
                value={newGroup.name}
                onChange={e => setNewGroup(g => ({ ...g, name: e.target.value }))}
              />
            </Field>
            <Field label="业务分类">
              <select
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={newGroup.category}
                onChange={e => setNewGroup(g => ({ ...g, category: e.target.value }))}
              >
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="邮箱定位 (多选)">
              <div className="flex flex-wrap gap-2">
                {POSITIONINGS.map(p => (
                  <Tag key={p} active={newGroup.positioning.includes(p)}
                    onClick={() => setNewGroup(g => ({ ...g, positioning: toggleItem(g.positioning, p) }))}>
                    {p}
                  </Tag>
                ))}
              </div>
            </Field>
            <Field label="适用邮件类型 (多选)">
              <div className="flex flex-wrap gap-2">
                {EMAIL_TYPES.map(t => (
                  <Tag key={t} active={newGroup.email_types.includes(t)}
                    onClick={() => setNewGroup(g => ({ ...g, email_types: toggleItem(g.email_types, t) }))}>
                    {t}
                  </Tag>
                ))}
              </div>
            </Field>
            <button
              onClick={createGroup}
              disabled={saving || !newGroup.name.trim()}
              className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "创建中..." : "创建分组"}
            </button>
          </div>
        </Modal>
      )}

      {/* Modal: manual doc */}
      {showManual && selected && (
        <Modal title={`录入话术 → ${selected.name}`} onClose={() => setShowManual(false)}>
          <div className="space-y-4">
            <Field label="标题">
              <input
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="例：产品价格常见问题解答"
                value={manualDoc.title}
                onChange={e => setManualDoc(d => ({ ...d, title: e.target.value }))}
              />
            </Field>
            <Field label="话术内容">
              <textarea
                className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                rows={8}
                placeholder="在此输入知识库内容，AI 回复时将参考此内容..."
                value={manualDoc.content}
                onChange={e => setManualDoc(d => ({ ...d, content: e.target.value }))}
              />
            </Field>
            <button
              onClick={addManual}
              disabled={saving || !manualDoc.title.trim() || !manualDoc.content.trim()}
              className="w-full bg-green-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              {saving ? "入库中..." : "提交入库"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      {children}
    </div>
  );
}

function Tag({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
        active ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
      }`}
    >
      {children}
    </button>
  );
}
