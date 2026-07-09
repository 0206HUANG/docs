"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

const NAV = [
  { href: "/dashboard", label: "概览" },
  { href: "/dashboard/inbox", label: "收件箱" },
  { href: "/dashboard/tickets", label: "工单" },
  { href: "/dashboard/accounts", label: "邮箱账号" },
  { href: "/dashboard/kb", label: "知识库" },
  { href: "/dashboard/settings", label: "设置" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    if (!token) router.replace("/login");
  }, [router]);

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    router.replace("/login");
  }

  return (
    <div className="flex h-screen bg-muted/20">
      <aside className="w-52 bg-card border-r flex flex-col shrink-0">
        <div className="p-4 border-b">
          <span className="font-bold text-primary">EmailAI</span>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {NAV.map(n => (
            <Link
              key={n.href}
              href={n.href}
              className={`block px-3 py-2 rounded-md text-sm transition-colors ${
                pathname === n.href
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted text-foreground"
              }`}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="p-3 border-t">
          <button onClick={logout} className="text-xs text-muted-foreground hover:text-foreground">
            退出登录
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}
