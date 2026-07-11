"use client";
import { useEffect, useState } from "react";
import { api, SensitiveWord, EmailStrategy } from "@/lib/api";

type Tab = "llm" | "sensitive" | "strategies";

const STRATEGY_OPTIONS = ["auto_send", "draft_review", "human_only", "skip"];
const STRATEGY_LABELS: Record<string, string> = {
  auto_send: "自动发送",
  draft_review: "草稿审核",
  human_only: "转人工",
  skip: "忽略",
};
const TONE_OPTIONS = ["business", "formal", "friendly", "concise"];
const EMAIL_TYPE_LABELS: Record<string, string> = {
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

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("llm");
  const [llm, setLlm] = useState({ provider: "openai", api_key_enc: "", model: "gpt-4o-mini" });
  const [llmSaved, setLlmSaved] = useState(false);
  const [words, setWords] = useState<SensitiveWord[]>([]);
  const [newWord, setNewWord] = useState({ word: "", category: "custom" });
  const [strategies, setStrategies] = useState<EmailStrategy[]>([]);

  useEffect(() => {
    if (tab === "sensitive") {
      api.settings.getSensitiveWords().then(setWords).catch(console.error);
    }
    if (tab === "strategies") {
      api.settings.getStrategies().then(setStrategies).catch(console.error);
    }
    if (tab === "llm") {
      api.settings.getLLM().then(d => setLlm(l => ({ ...l, provider: d.provider, model: d.model }))).catch(() => {});
    }
  }, [tab]);

  async function saveLLM() {
    await api.settings.saveLLM(llm).catch(e => alert(e.message));
    setLlmSaved(true);
    setTimeout(() => setLlmSaved(false), 2000);
  }

  async function addWord() {
    if (!newWord.word.trim()) return;
    await api.settings.addSensitiveWord(newWord.word, newWord.category).catch(e => alert(e.message));
    setNewWord({ word: "", category: "custom" });
    api.settings.getSensitiveWords().then(setWords);
  }

  async function deleteWord(id: string) {
    await api.settings.deleteSensitiveWord(id).catch(e => alert(e.message));
    setWords(w => w.filter(x => x.id !== id));
  }

  async function updateStrategy(email_type: string, send_strategy: string, tone: string) {
    await api.settings.updateStrategy(email_type, { send_strategy, tone }).catch(e => alert(e.message));
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "llm", label: "AI 配置" },
    { key: "sensitive", label: "敏感词" },
    { key: "strategies", label: "路由策略" },
  ];

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-semibold mb-5">设置</h1>

      <div className="flex border-b border-slate-200 mb-6">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t.key
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "llm" && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">AI 提供商</label>
            <select
              className={inp}
              value={llm.provider}
              onChange={e => setLlm(l => ({ ...l, provider: e.target.value }))}
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="deepseek">DeepSeek</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
            <input
              type="password"
              className={inp}
              placeholder="sk-..."
              value={llm.api_key_enc}
              onChange={e => setLlm(l => ({ ...l, api_key_enc: e.target.value }))}
            />
            <p className="text-xs text-slate-400 mt-1">加密存储，不可反查。修改时重新输入完整 key。</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">模型</label>
            <input
              className={inp}
              value={llm.model}
              onChange={e => setLlm(l => ({ ...l, model: e.target.value }))}
              placeholder="gpt-4o-mini"
            />
          </div>
          <button
            onClick={saveLLM}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
          >
            {llmSaved ? "已保存 ✓" : "保存"}
          </button>
        </div>
      )}

      {tab === "sensitive" && (
        <div className="space-y-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <p className="text-sm font-medium text-slate-700 mb-3">添加敏感词</p>
            <div className="flex gap-2">
              <input
                className={inp + " flex-1"}
                placeholder="输入关键词"
                value={newWord.word}
                onChange={e => setNewWord(w => ({ ...w, word: e.target.value }))}
                onKeyDown={e => e.key === "Enter" && addWord()}
              />
              <select
                className="border border-slate-200 rounded-lg px-3 py-2 text-sm"
                value={newWord.category}
                onChange={e => setNewWord(w => ({ ...w, category: e.target.value }))}
              >
                <option value="custom">自定义</option>
                <option value="legal">法律</option>
                <option value="financial">财务</option>
                <option value="hr">人事</option>
              </select>
              <button
                onClick={addWord}
                className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
              >
                添加
              </button>
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <p className="text-sm font-medium text-slate-700 mb-3">
              当前敏感词 ({words.length} 个) — 命中后强制转人工
            </p>
            {words.length === 0 ? (
              <p className="text-sm text-slate-400">暂无敏感词</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {words.map(w => (
                  <div key={w.id} className="flex items-center gap-1.5 bg-red-50 border border-red-100 rounded-full px-3 py-1">
                    <span className="text-sm text-red-700">{w.word}</span>
                    <span className="text-xs text-red-400">{w.category}</span>
                    <button
                      onClick={() => deleteWord(w.id)}
                      className="text-red-400 hover:text-red-600 text-xs leading-none ml-1"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "strategies" && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500">邮件类型</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500">处理策略</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-slate-500">语气</th>
              </tr>
            </thead>
            <tbody>
              {strategies.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-slate-400 text-sm">
                    暂无策略配置
                  </td>
                </tr>
              ) : strategies.map((s, i) => (
                <tr key={s.email_type} className={i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}>
                  <td className="px-4 py-3 text-slate-700">
                    {EMAIL_TYPE_LABELS[s.email_type] || s.email_type}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      className="border border-slate-200 rounded-md px-2 py-1 text-xs"
                      defaultValue={s.send_strategy}
                      onChange={e => updateStrategy(s.email_type, e.target.value, s.tone)}
                    >
                      {STRATEGY_OPTIONS.map(o => (
                        <option key={o} value={o}>{STRATEGY_LABELS[o]}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      className="border border-slate-200 rounded-md px-2 py-1 text-xs"
                      defaultValue={s.tone}
                      onChange={e => updateStrategy(s.email_type, s.send_strategy, e.target.value)}
                    >
                      {TONE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const inp = "w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";
