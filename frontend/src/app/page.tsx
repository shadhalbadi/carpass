"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatMoney, formatNumber, formatOmr } from "@/lib/format";

function importHref(car: any): string {
  const q = new URLSearchParams();
  if (car?.make) q.set("make", car.make);
  if (car?.model) q.set("model", car.model);
  if (car?.year) q.set("year", String(car.year));
  if (car?.vin) q.set("vin", car.vin);
  const origin = car?.location || car?.country;
  if (origin) q.set("origin_port", origin);
  return `/shipments?${q.toString()}`;
}

function CalculatorInner() {
  const searchParams = useSearchParams();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);
  const [autoRan, setAutoRan] = useState(false);
  const [copied, setCopied] = useState(false);

  async function calculateUrl(targetUrl: string) {
    setLoading(true);
    setError("");
    try {
      const data = await api.fetchCalculate(targetUrl);
      setResult(data);
      if (data?.car?.source_url) setUrl(data.car.source_url);
    } catch (err: any) {
      setError(err.message || "Failed");
    } finally {
      setLoading(false);
    }
  }

  async function calculateListing(listingId: number) {
    setLoading(true);
    setError("");
    try {
      const data = await api.calculateFromListing(listingId);
      setResult(data);
      const link = data?.car?.source_url || "";
      if (link) setUrl(link);
    } catch (err: any) {
      setError(err.message || "Failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (autoRan) return;
    const listingId = searchParams.get("listing_id");
    const qUrl = searchParams.get("url");
    if (listingId) {
      setAutoRan(true);
      calculateListing(Number(listingId));
      return;
    }
    if (qUrl) {
      setUrl(qUrl);
      setAutoRan(true);
      calculateUrl(qUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, autoRan]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!url.trim()) {
      setError("Paste a listing URL first");
      return;
    }
    await calculateUrl(url.trim());
  }

  function clearAll() {
    setUrl("");
    setResult(null);
    setError("");
  }

  async function copyQuote() {
    if (!result) return;
    const lines = [
      `${result.car.year} ${result.car.make} ${result.car.model}`,
      `Asking: ${formatMoney(result.car.price, result.car.currency)}`,
      ...result.line_items.map((i: any) => `${i.label}: ${formatOmr(i.amount_omr)} OMR`),
      `Total landed: ${formatOmr(result.total_landed_omr)} OMR`,
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  }

  const photo = result?.car?.photos?.[0];

  return (
    <div className="space-y-8">
      <section className="space-y-6">
        <div className="max-w-2xl">
          <p className="eyebrow mb-3">Landed Cost</p>
          <h1 className="page-title">
            Paste a car link.
            <br />
            See the true cost to Muscat.
          </h1>
          <p className="page-sub">
            Price + shipping + duty + VAT + port fees, all in OMR — with a clear import vs
            buy-local verdict in seconds.
          </p>
        </div>

        <form onSubmit={onSubmit} className="card space-y-2.5">
          <label className="label !mb-0" htmlFor="listing-url">
            Listing URL
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-400">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" strokeLinecap="round" />
                  <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" strokeLinecap="round" />
                </svg>
              </span>
              <input
                id="listing-url"
                className="input !pl-10"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.copart.com/lot/58412992"
              />
            </div>
            <div className="flex gap-2">
              <button className="btn shrink-0" disabled={loading}>
                {loading ? "Calculating…" : "Calculate"}
              </button>
              <button type="button" className="btn-secondary shrink-0" onClick={clearAll}>
                Clear
              </button>
            </div>
          </div>
          <p className="text-xs text-neutral-500">
            Tip: from{" "}
            <Link href="/search" className="link">
              Search
            </Link>{" "}
            → View details → Recalculate uses that listing&apos;s exact link and price.
          </p>
        </form>
        {error && <p className="danger-text text-sm">{error}</p>}
      </section>

      {result && (
        <>
          <section className="card overflow-hidden !p-0">
            <div className="relative">
              {photo ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={photo} alt="" className="h-72 w-full object-cover sm:h-96" />
              ) : (
                <div className="photo-placeholder flex h-72 items-center justify-center sm:h-96">
                  <span className="rounded-full bg-white px-3 py-1 font-mono text-xs tracking-widest text-neutral-400">
                    vehicle photo
                  </span>
                </div>
              )}
              {result.car.source && (
                <span className="badge absolute left-4 top-4 bg-white/90 text-neutral-600 shadow-sm">
                  {result.car.source}
                </span>
              )}
            </div>

            <div className="space-y-5 p-5 sm:p-6">
              <div>
                <p className="text-sm text-neutral-500">Vehicle</p>
                <p className="mt-1 text-2xl font-extrabold tracking-tight text-neutral-900">
                  {result.car.year} {result.car.make} {result.car.model}
                </p>
              </div>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
                <div>
                  <dt className="text-neutral-500">Asking price</dt>
                  <dd className="mt-0.5 font-bold text-neutral-900">
                    {formatMoney(result.car.price, result.car.currency)}
                  </dd>
                </div>
                <div>
                  <dt className="text-neutral-500">Location</dt>
                  <dd className="mt-0.5 font-bold text-neutral-900">
                    {result.car.location || result.car.country || "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-neutral-500">Mileage</dt>
                  <dd className="mt-0.5 font-bold text-neutral-900">
                    {result.car.mileage != null ? formatNumber(result.car.mileage, 0) : "—"}{" "}
                    {result.car.mileage_unit}
                  </dd>
                </div>
                <div>
                  <dt className="text-neutral-500">Damage</dt>
                  <dd className="mt-0.5 font-bold text-neutral-900">{result.car.damage || "—"}</dd>
                </div>
                {result.car.source_url && (
                  <div className="col-span-2">
                    <dt className="text-neutral-500">Source</dt>
                    <dd className="mt-0.5 break-all">
                      <a href={result.car.source_url} target="_blank" rel="noreferrer" className="link text-sm">
                        {result.car.source_url}
                      </a>
                    </dd>
                  </div>
                )}
              </dl>
              {result.route && (
                <div className="surface-inset flex items-center gap-2.5 px-4 py-3 text-sm text-neutral-600">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="shrink-0 text-neutral-400">
                    <path d="M17.8 19.2L16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" strokeLinejoin="round" />
                  </svg>
                  {result.route.origin_port} → {result.route.dest_port} · {result.route.mode} · ~
                  {result.route.transit_days} days transit
                </div>
              )}
            </div>
          </section>

          <section className="card space-y-5 !p-5 sm:!p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm text-neutral-500">Total landed cost</p>
                <p className="mt-1 text-4xl font-extrabold tracking-tight text-neutral-900 sm:text-5xl">
                  {formatOmr(result.total_landed_omr)}{" "}
                  <span className="text-xl font-semibold text-neutral-400">OMR</span>
                </p>
              </div>
              <VerdictBadge result={result} />
            </div>
            <p className="text-sm leading-relaxed text-neutral-600">{result.verdict_message}</p>

            <div className="overflow-hidden rounded-2xl border border-[color:var(--line)]">
              <table className="w-full text-sm">
                <thead className="bg-[#f6f2ea] text-neutral-500">
                  <tr>
                    <th className="px-4 py-2.5 text-left text-xs font-bold uppercase tracking-wider">
                      Cost breakdown
                    </th>
                    <th className="px-4 py-2.5 text-right text-xs font-bold uppercase tracking-wider">OMR</th>
                  </tr>
                </thead>
                <tbody>
                  {result.line_items.map((item: any) => (
                    <tr key={item.key} className="border-t border-[color:var(--line)]">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-neutral-800">{item.label}</div>
                        {item.notes && <div className="mt-0.5 text-xs text-neutral-400">{item.notes}</div>}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums text-neutral-800">
                        {formatOmr(item.amount_omr)}
                      </td>
                    </tr>
                  ))}
                  <tr className="border-t border-[color:var(--line)] bg-[#fbf9f4]">
                    <td className="px-4 py-3 font-bold text-neutral-900">Total landed</td>
                    <td className="px-4 py-3 text-right font-extrabold tabular-nums text-[color:var(--accent)]">
                      {formatOmr(result.total_landed_omr)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap gap-3 pt-1">
              <Link href={importHref(result.car)} className="btn">
                Start an import
              </Link>
              <button type="button" className="btn-secondary" onClick={copyQuote}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="12" height="12" rx="2" />
                  <path d="M5 15V5a2 2 0 012-2h10" strokeLinecap="round" />
                </svg>
                {copied ? "Copied!" : "Copy quote"}
              </button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function VerdictBadge({ result }: { result: any }) {
  const map: Record<string, string> = {
    import_saves: "bg-[color:var(--success-soft)] text-[color:var(--success)] border-transparent",
    buy_local: "bg-amber-50 text-amber-800 border-amber-200",
    similar: "bg-[color:var(--accent-soft)] text-[color:var(--accent-strong)] border-transparent",
    local: "bg-neutral-100 text-neutral-700 border-neutral-200",
    no_local_data: "bg-neutral-50 text-neutral-600 border-neutral-200",
  };
  const cls = map[result.verdict] || map.no_local_data;
  return (
    <div className={`rounded-2xl border px-4 py-2.5 text-sm ${cls}`}>
      <div className="text-xs font-extrabold uppercase tracking-wider">
        {(result.verdict || "n/a").replaceAll("_", " ")}
      </div>
      {result.local_compare_omr != null && (
        <div className="mt-0.5 text-xs opacity-90">Local median {formatOmr(result.local_compare_omr)} OMR</div>
      )}
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<div className="muted">Loading calculator…</div>}>
      <CalculatorInner />
    </Suspense>
  );
}
