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

/** Blue rounded-square mark with an upward arc, per the design. */
function LogoMark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <rect width="40" height="40" rx="13" fill="#2b5fe3" />
      <path
        d="M12 24c4-7 12-7 16 0"
        stroke="white"
        strokeWidth="3"
        strokeLinecap="round"
      />
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
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-[color:var(--line)] bg-[color:var(--bg)]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link href="/" className="flex shrink-0 items-center gap-2.5">
            <LogoMark className="h-9 w-9" />
            <span className="text-lg font-extrabold tracking-tight text-neutral-900">
              CarPass <span className="font-semibold text-neutral-400">Oman</span>
            </span>
          </Link>

          <nav className="hidden items-center gap-0.5 lg:flex" aria-label="Primary">
            {nav.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`rounded-full px-3.5 py-2 text-sm font-medium transition ${
                    active
                      ? "bg-[color:var(--accent-soft)] font-semibold text-[color:var(--accent)]"
                      : "text-neutral-500 hover:bg-black/5 hover:text-neutral-900"
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
              className="rounded-full border border-[color:var(--line-strong)] bg-white px-3 py-1.5 text-xs font-semibold text-neutral-600 hover:bg-neutral-50"
            >
              {lang === "en" ? "عربي" : "EN"}
            </button>
            {user ? (
              <>
                <span className="hidden max-w-[10rem] truncate text-sm text-neutral-500 sm:inline">
                  {user.full_name || user.email}
                </span>
                <button type="button" onClick={logout} className="btn-dark !py-1.5 !text-xs">
                  Logout
                </button>
              </>
            ) : (
              <Link href="/login" className="btn-dark !py-1.5 !text-xs">
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-white/20 text-[9px] font-bold">
                  A
                </span>
                Sign in
              </Link>
            )}
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-[color:var(--line-strong)] lg:hidden"
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
          <nav className="border-t border-[color:var(--line)] bg-[color:var(--bg)] px-4 py-3 lg:hidden" aria-label="Mobile">
            <div className="mx-auto grid max-w-6xl gap-1 sm:grid-cols-2">
              {nav.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-xl px-3 py-2.5 text-sm font-medium ${
                      active
                        ? "bg-[color:var(--accent-soft)] text-[color:var(--accent)]"
                        : "text-neutral-700 hover:bg-black/5"
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

      <footer className="border-t border-[color:var(--line)] bg-white/60">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm sm:px-6">
          <div className="flex items-center gap-2.5">
            <LogoMark className="h-7 w-7" />
            <span className="font-bold text-neutral-900">
              CarPass Oman{" "}
              <span className="font-normal text-neutral-500">— true landed cost &amp; import tracking</span>
            </span>
          </div>
          <div className="flex items-center gap-5 text-neutral-500">
            <span className="font-medium text-neutral-700">Help</span>
            <span>© 2026 CarPass Oman</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
