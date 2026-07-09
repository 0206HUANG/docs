"use client";

export default function KBPage() {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-6">知识库</h1>
      <p className="text-muted-foreground text-sm">
        知识库管理 — 通过 API 上传文档后，系统自动分块、Embedding 入库。
        支持 PDF、Word、Excel、TXT 及手工录入话术。
      </p>
      <div className="mt-4 bg-muted/30 rounded-lg p-4 text-sm">
        <p className="font-medium mb-2">上传文档 API 示例</p>
        <pre className="text-xs font-mono text-muted-foreground overflow-x-auto">
{`POST /api/v1/kb/documents
Content-Type: multipart/form-data

group_id=<group-uuid>
title=产品手册
file=@product_manual.pdf`}
        </pre>
      </div>
    </div>
  );
}
