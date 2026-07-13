"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatMoney, formatNumber, formatOmr } from "@/lib/format";

function CalculatorInner() {
  const searchParams = useSearchParams();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);
  const [autoRan, setAutoRan] = useState(false);

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

  return (
    <div className="space-y-8">
      <section className="space-y-6">
        <div className="max-w-2xl">
          <p className="mb-2 text-sm font-semibold uppercase tracking-wider text-teal-700">Landed cost</p>
          <h1 className="page-title">
            Paste a car link. See the true cost to Muscat.
          </h1>
          <p className="page-sub">
            Price + shipping + duty + VAT + port fees — in OMR — with an import vs buy-local verdict.
          </p>
        </div>

        <form onSubmit={onSubmit} className="card flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label className="label" htmlFor="listing-url">
              Listing URL
            </label>
            <input
              id="listing-url"
              className="input"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Paste a live listing URL from Search…"
            />
          </div>
          <button className="btn shrink-0 sm:mb-0" disabled={loading}>
            {loading ? "Calculating…" : "Calculate"}
          </button>
        </form>
        {error && <p className="danger-text text-sm">{error}</p>}
        <p className="text-xs text-slate-500">
          Tip: from{" "}
          <Link href="/search" className="link">
            Search
          </Link>{" "}
          → View details → Recalculate uses that listing&apos;s exact link and price.
        </p>
      </section>

      {result && (
        <section className="grid gap-6 lg:grid-cols-5">
          <div className="card space-y-4 lg:col-span-2">
            <h2 className="text-lg font-semibold text-slate-900">Vehicle</h2>
            <p className="text-2xl font-bold tracking-tight text-slate-900">
              {result.car.year} {result.car.make} {result.car.model}
            </p>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-slate-500">Price</dt>
                <dd className="mt-0.5 font-medium">{formatMoney(result.car.price, result.car.currency)}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Location</dt>
                <dd className="mt-0.5 font-medium">{result.car.location || result.car.country || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Mileage</dt>
                <dd className="mt-0.5 font-medium">
                  {result.car.mileage != null ? formatNumber(result.car.mileage, 0) : "—"}{" "}
                  {result.car.mileage_unit}
                </dd>
              </div>
              <div>
                <dt className="text-slate-500">Damage</dt>
                <dd className="mt-0.5 font-medium">{result.car.damage || "—"}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-slate-500">Source</dt>
                <dd className="mt-0.5 break-all text-sm">
                  {result.car.source_url ? (
                    <a href={result.car.source_url} target="_blank" rel="noreferrer" className="link">
                      {result.car.source_url}
                    </a>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
            </dl>
            {result.route && (
              <div className="surface-inset p-3 text-sm text-slate-600">
                Route: {result.route.origin_port} → {result.route.dest_port} ({result.route.mode}), transit{" "}
                {result.route.transit_days} days
              </div>
            )}
          </div>

          <div className="card space-y-5 lg:col-span-3">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-sm text-slate-500">Total landed cost</p>
                <p className="mt-1 text-4xl font-bold tracking-tight text-teal-700">
                  {formatOmr(result.total_landed_omr)} <span className="text-2xl font-semibold">OMR</span>
                </p>
              </div>
              <VerdictBadge result={result} />
            </div>
            <p className="text-sm leading-relaxed text-slate-600">{result.verdict_message}</p>
            <div className="overflow-hidden rounded-xl border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-4 py-2.5 text-left font-medium">Item</th>
                    <th className="px-4 py-2.5 text-right font-medium">OMR</th>
                  </tr>
                </thead>
                <tbody>
                  {result.line_items.map((item: any) => (
                    <tr key={item.key} className="border-t border-slate-100">
                      <td className="px-4 py-2.5">
                        <div className="font-medium text-slate-800">{item.label}</div>
                        {item.notes && <div className="text-xs text-slate-500">{item.notes}</div>}
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono text-slate-800">
                        {formatOmr(item.amount_omr)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function VerdictBadge({ result }: { result: any }) {
  const map: Record<string, string> = {
    import_saves: "bg-teal-50 text-teal-800 border-teal-200",
    buy_local: "bg-amber-50 text-amber-800 border-amber-200",
    similar: "bg-sky-50 text-sky-800 border-sky-200",
    local: "bg-slate-100 text-slate-700 border-slate-200",
    no_local_data: "bg-slate-50 text-slate-600 border-slate-200",
  };
  const cls = map[result.verdict] || map.no_local_data;
  return (
    <div className={`rounded-xl border px-3 py-2 text-sm ${cls}`}>
      <div className="font-semibold uppercase tracking-wide">{(result.verdict || "n/a").replaceAll("_", " ")}</div>
      {result.local_compare_omr != null && (
        <div className="mt-0.5 text-xs opacity-80">Local median: {formatOmr(result.local_compare_omr)} OMR</div>
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
