"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { User, api } from "@/lib/api";

const nav = [
  { href: "/", label: "Calculator", labelAr: "الحاسبة" },
  { href: "/search", label: "Search", labelAr: "بحث" },
  { href: "/track", label: "Track", labelAr: "تتبع" },
  { href: "/shipments", label: "Imports", labelAr: "وارداتي" },
  { href: "/watches", label: "Alerts", labelAr: "تنبيهات" },
  { href: "/agent", label: "Agent", labelAr: "وكيل" },
  { href: "/admin", label: "Admin", labelAr: "إدارة" },
];

/** Minimal geometric mark — no letters. */
function LogoMark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <rect width="40" height="40" rx="12" fill="#0d9488" />
      <path
        d="M10 22.5c4.5-8 15.5-8 20 0"
        stroke="white"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <path
        d="M13 17.5c3.2-4.8 10.8-4.8 14 0"
        stroke="white"
        strokeWidth="2.4"
        strokeLinecap="round"
        opacity="0.55"
      />
      <circle cx="20" cy="25.5" r="2.2" fill="white" />
    </svg>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [lang, setLang] = useState<"en" | "ar">("en");
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("carpass_token");
    if (!token) return;
    api.me().then(setUser).catch(() => localStorage.removeItem("carpass_token"));
  }, [pathname]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  function logout() {
    localStorage.removeItem("carpass_token");
    setUser(null);
    router.push("/login");
  }

  return (
    <div className="min-h-screen text-slate-900">
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5 shrink-0">
            <LogoMark className="h-9 w-9" />
            <span className="text-lg font-bold tracking-tight text-slate-900">
              CarPass <span className="font-semibold text-teal-700">Oman</span>
            </span>
          </Link>

          <nav className="hidden items-center gap-0.5 lg:flex" aria-label="Primary">
            {nav.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                    active
                      ? "bg-teal-50 text-teal-800"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  {lang === "ar" ? item.labelAr : item.label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setLang(lang === "en" ? "ar" : "en")}
              className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              {lang === "en" ? "عربي" : "EN"}
            </button>
            {user ? (
              <>
                <span className="hidden max-w-[10rem] truncate text-sm text-slate-500 sm:inline">
                  {user.full_name || user.email}
                </span>
                <button type="button" onClick={logout} className="btn-secondary !py-1.5 !text-xs">
                  Logout
                </button>
              </>
            ) : (
              <Link href="/login" className="btn !py-1.5 !text-xs">
                Login
              </Link>
            )}
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 lg:hidden"
              aria-label="Menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((o) => !o)}
            >
              <span className="sr-only">Menu</span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {menuOpen ? (
                  <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                ) : (
                  <>
                    <path d="M4 7h16" strokeLinecap="round" />
                    <path d="M4 12h16" strokeLinecap="round" />
                    <path d="M4 17h16" strokeLinecap="round" />
                  </>
                )}
              </svg>
            </button>
          </div>
        </div>

        {menuOpen && (
          <nav className="border-t border-slate-200 bg-white px-4 py-3 lg:hidden" aria-label="Mobile">
            <div className="mx-auto grid max-w-6xl gap-1 sm:grid-cols-2">
              {nav.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-lg px-3 py-2.5 text-sm font-medium ${
                      active ? "bg-teal-50 text-teal-800" : "text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    {lang === "ar" ? item.labelAr : item.label}
                  </Link>
                );
              })}
            </div>
          </nav>
        )}
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>

      <footer className="border-t border-slate-200 bg-white/70 py-8 text-center text-sm text-slate-500">
        CarPass Oman — true landed cost &amp; import tracking
      </footer>
    </div>
  );
}
