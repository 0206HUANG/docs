"use client";
import { useState } from "react";

export default function SettingsPage() {
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("gpt-4o-mini");
  const [saved, setSaved] = useState(false);

  async function save() {
    const token = localStorage.getItem("access_token");
    await fetch("/api/v1/settings/llm", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ provider, api_key_enc: apiKey, model }),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-xl font-semibold mb-6">设置</h1>
      <div className="bg-card border rounded-lg p-5">
        <h2 className="font-medium mb-4">LLM 配置</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">AI 提供商</label>
            <select
              className="w-full border rounded-md px-3 py-2 text-sm"
              value={provider}
              onChange={e => setProvider(e.target.value)}
            >
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="deepseek">DeepSeek</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">API Key</label>
            <input
              type="password"
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="sk-..."
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">模型</label>
            <input
              className="w-full border rounded-md px-3 py-2 text-sm"
              value={model}
              onChange={e => setModel(e.target.value)}
            />
          </div>
          <button
            onClick={save}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90"
          >
            {saved ? "已保存 ✓" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
