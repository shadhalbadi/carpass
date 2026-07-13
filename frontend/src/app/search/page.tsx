"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Combobox } from "@/components/Combobox";
import { api } from "@/lib/api";
import { CAR_MAKES, modelsForMake, yearOptions } from "@/lib/cars";
import { formatMoney, formatOmr } from "@/lib/format";

const SOURCE_LABELS: Record<string, string> = {
  copart: "Copart",
  iaai: "IAAI",
  beforward: "BE FORWARD",
  sbt: "SBT Japan",
  dubizzle_uae: "Dubizzle UAE",
  dubizzle_om: "Dubizzle Oman",
  opensooq: "OpenSooq",
  sooq_cars: "Sooq Cars",
};

const YEARS = yearOptions();

type QueryKey = {
  make: string;
  model: string;
  yearMin: string;
  maxLanded: string;
  source: string;
};

function queryKey(q: QueryKey): string {
  return JSON.stringify({
    make: q.make.trim().toLowerCase(),
    model: q.model.trim().toLowerCase(),
    yearMin: q.yearMin.trim(),
    maxLanded: q.maxLanded.trim().replace(/,/g, ""),
    source: q.source.trim(),
  });
}

const STORAGE_KEY = "carpass_search_state";

export default function SearchPage() {
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [yearMin, setYearMin] = useState("");
  const [maxLanded, setMaxLanded] = useState("");
  const [source, setSource] = useState("");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [loadingHint, setLoadingHint] = useState("");
  const [error, setError] = useState("");
  const [restored, setRestored] = useState(false);
  const appliedQuery = useRef<string | null>(null);
  const clearTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const modelOptions = useMemo(() => modelsForMake(make), [make]);
  const currentFields: QueryKey = { make, model, yearMin, maxLanded, source };

  // Restore last search (fields + results) so results survive navigating
  // to a listing's detail page and back.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        setMake(saved.make || "");
        setModel(saved.model || "");
        setYearMin(saved.yearMin || "");
        setMaxLanded(saved.maxLanded || "");
        setSource(saved.source || "");
        if (saved.data) {
          setData(saved.data);
          appliedQuery.current = saved.appliedQuery || null;
        }
      }
    } catch {
      /* corrupt/absent state — start fresh */
    }
    setRestored(true);
  }, []);

  const LOADING_HINTS = [
    "Contacting marketplaces…",
    "Fetching BE FORWARD & OpenSooq…",
    "Checking Dubizzle UAE…",
    "Pulling Copart & IAAI lots…",
    "Calculating landed costs in OMR…",
  ];

  useEffect(() => {
    if (!loading) {
      setLoadingHint("");
      return;
    }
    let i = 0;
    setLoadingHint(LOADING_HINTS[0]);
    const id = setInterval(() => {
      i = (i + 1) % LOADING_HINTS.length;
      setLoadingHint(LOADING_HINTS[i]);
    }, 2800);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  // Keep the saved state in sync so it's always up to date when we navigate away.
  useEffect(() => {
    if (!restored) return;
    try {
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ make, model, yearMin, maxLanded, source, data, appliedQuery: appliedQuery.current }),
      );
    } catch {
      /* storage full/unavailable */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restored, make, model, yearMin, maxLanded, source, data]);

  useEffect(() => {
    if (!restored) return;
    if (!data || !appliedQuery.current) return;
    if (queryKey(currentFields) === appliedQuery.current) return;
    if (clearTimer.current) clearTimeout(clearTimer.current);
    clearTimer.current = setTimeout(() => {
      if (appliedQuery.current && queryKey(currentFields) !== appliedQuery.current) {
        setData(null);
        setError("");
        appliedQuery.current = null;
      }
    }, 450);
    return () => {
      if (clearTimer.current) clearTimeout(clearTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [restored, make, model, yearMin, maxLanded, source]);

  const fieldsChanged =
    data != null && appliedQuery.current != null && queryKey(currentFields) !== appliedQuery.current;

  function onMakeChange(next: string) {
    setMake(next);
    const models = modelsForMake(next);
    if (model && !models.some((m) => m.toLowerCase() === model.toLowerCase())) {
      setModel("");
    }
  }

  async function runSearch(e?: FormEvent) {
    e?.preventDefault();
    if (!make.trim()) {
      setError("Choose or type a make to search live listings");
      return;
    }
    const snapshot: QueryKey = { make, model, yearMin, maxLanded, source };
    setLoading(true);
    setError("");
    try {
      const res = await api.searchListings({
        make: make || undefined,
        model: model || undefined,
        year_min: yearMin || undefined,
        max_landed_omr: maxLanded || undefined,
        source: source || undefined,
        live: true,
        page: 1,
        page_size: 40,
      });
      setData(res);
      appliedQuery.current = queryKey(snapshot);
      if (!res.items?.length && res.message) {
        setError(res.message);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="page-title">Live search</h1>
        <p className="page-sub">Real listings from marketplaces for your query — with landed cost in OMR.</p>
      </div>

      <form onSubmit={runSearch} className="card grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <label className="label">Make *</label>
          <Combobox value={make} onChange={onMakeChange} options={CAR_MAKES} placeholder="Type or select make" required />
        </div>
        <div>
          <label className="label">Model</label>
          <Combobox
            value={model}
            onChange={setModel}
            options={modelOptions}
            placeholder={make ? "Type or select model" : "Select make first"}
            disabled={!make.trim()}
          />
        </div>
        <div>
          <label className="label">Year min</label>
          <Combobox value={yearMin} onChange={setYearMin} options={YEARS} placeholder="Type or select year" />
        </div>
        <div>
          <label className="label">Max landed OMR</label>
          <input className="input" value={maxLanded} onChange={(e) => setMaxLanded(e.target.value)} placeholder="e.g. 7,000" />
        </div>
        <div>
          <label className="label">Source</label>
          <select className="input" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">All sources</option>
            <option value="beforward">BE FORWARD</option>
            <option value="opensooq">OpenSooq</option>
            <option value="sooq_cars">Sooq Cars</option>
            <option value="dubizzle_uae">Dubizzle UAE</option>
            <option value="copart">Copart</option>
            <option value="iaai">IAAI</option>
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2 lg:col-span-5">
          <button className="btn" disabled={loading}>
            {loading && <span className="search-spinner" aria-hidden />}
            {loading ? "Searching…" : "Search live"}
          </button>
          {fieldsChanged && !loading && (
            <span className="text-sm text-amber-700">Filters changed — run Search live for new results.</span>
          )}
        </div>
      </form>

      {loading && (
        <div className="card flex items-start gap-4 border-blue-200 bg-blue-50/60" role="status" aria-live="polite">
          <span className="search-spinner search-spinner-lg mt-0.5 shrink-0" aria-hidden />
          <div className="min-w-0 space-y-1">
            <p className="font-semibold text-blue-900">Searching marketplaces</p>
            <p className="text-sm text-slate-700">{loadingHint}</p>
            <p className="text-xs text-slate-500">This can take up to a minute.</p>
            {data?.items?.length > 0 && (
              <p className="text-xs text-slate-500">Previous results stay visible until the new search finishes.</p>
            )}
          </div>
        </div>
      )}

      {error && <p className="danger-text text-sm">{error}</p>}

      {data?.message && data.items?.length > 0 && !loading && (
        <p className="text-sm font-medium text-blue-700">{data.message}</p>
      )}

      {data?.errors && Object.keys(data.errors).length > 0 && !loading && (
        <div className="card space-y-2 text-sm">
          <p className="font-semibold text-amber-800">Source notes</p>
          {Object.entries(data.errors).map(([src, msg]) => (
            <p key={src} className="text-slate-600">
              <span className="font-medium text-slate-800">{SOURCE_LABELS[src] || src}:</span> {String(msg)}
            </p>
          ))}
        </div>
      )}

      {loading && !data?.items?.length && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-hidden>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card space-y-3">
              <div className="skeleton h-5 w-2/3" />
              <div className="skeleton h-7 w-1/2" />
              <div className="skeleton h-4 w-3/4" />
              <div className="skeleton h-4 w-full" />
            </div>
          ))}
        </div>
      )}

      <div className={`grid gap-4 sm:grid-cols-2 xl:grid-cols-3 ${loading && data?.items?.length ? "opacity-55" : ""}`}>
        {(data?.items || []).map((item: any) => (
          <article key={item.id} className="card flex flex-col gap-3">
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-base font-semibold leading-snug text-slate-900">
                {item.year || ""} {item.make} {item.model}
              </h2>
              <span className="badge-muted shrink-0">{item.source}</span>
            </div>
            <p className="text-xl font-bold text-blue-700">
              {item.landed_cost_omr != null ? `${formatOmr(item.landed_cost_omr)} OMR` : "—"}
              {item.landed_cost_omr != null && <span className="ml-1 text-sm font-medium text-slate-500">landed</span>}
            </p>
            <p className="text-sm text-slate-500">
              Asking {formatMoney(item.price, item.currency)} · {item.location || item.country}
            </p>
            <p className="line-clamp-2 text-xs text-slate-500">{item.title}</p>
            <div className="mt-auto flex flex-wrap gap-4 border-t border-slate-100 pt-3">
              <Link href={`/listings/${item.id}`} className="link text-sm">
                View details
              </Link>
              <Link href={importHref(item)} className="text-sm font-semibold text-blue-700 hover:text-blue-900">
                Import this car
              </Link>
              {item.source_url && (
                <a href={item.source_url} target="_blank" rel="noreferrer" className="text-sm font-medium text-slate-500 hover:text-slate-800">
                  Open listing
                </a>
              )}
            </div>
          </article>
        ))}
      </div>

      {data && (
        <p className="text-sm text-slate-500">
          {formatNumberSafe(data.total)} live listing{data.total === 1 ? "" : "s"}
          {data.sources_ok?.length ? ` from ${data.sources_ok.join(", ")}` : ""}
        </p>
      )}

      {!loading && !data && (
        <p className="text-sm text-slate-500">Choose make and model, then search live marketplaces.</p>
      )}
    </div>
  );
}

function importHref(item: any): string {
  const q = new URLSearchParams();
  if (item.id) q.set("listing_id", String(item.id));
  if (item.make) q.set("make", item.make);
  if (item.model) q.set("model", item.model);
  if (item.year) q.set("year", String(item.year));
  if (item.vin) q.set("vin", item.vin);
  const origin = item.location || item.country;
  if (origin) q.set("origin_port", origin);
  return `/shipments?${q.toString()}`;
}

function formatNumberSafe(n: number | undefined) {
  if (n == null) return "0";
  return new Intl.NumberFormat("en-US").format(n);
}
