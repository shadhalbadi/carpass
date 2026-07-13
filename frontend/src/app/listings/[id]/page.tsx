"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatMoney, formatOmr } from "@/lib/format";

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

export default function ListingDetailPage() {
  const params = useParams();
  const id = Number(params.id);
  const [item, setItem] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    api
      .getListing(id)
      .then(setItem)
      .catch((err: any) => setError(err.message || "Listing not found"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="muted">Loading listing…</p>;
  if (error || !item) return <p className="danger-text">{error || "Not found"}</p>;

  return (
    <div className="space-y-6">
      <Link href="/search" className="text-sm font-medium text-slate-500 hover:text-teal-700">
        ← Back to search
      </Link>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card overflow-hidden !p-0">
          {item.photos?.[0] ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.photos[0]} alt={item.title} className="h-72 w-full object-cover" />
          ) : (
            <div className="flex h-72 items-center justify-center bg-slate-100 text-slate-400">No photo</div>
          )}
        </div>

        <div className="card space-y-5">
          <div className="flex items-start justify-between gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              {item.year} {item.make} {item.model}
            </h1>
            <span className="badge-muted shrink-0">{item.source}</span>
          </div>
          <p className="text-3xl font-bold text-teal-700">
            {item.landed_cost_omr != null ? `${formatOmr(item.landed_cost_omr)} OMR` : "—"}
            {item.landed_cost_omr != null && (
              <span className="ml-2 text-base font-medium text-slate-500">landed</span>
            )}
          </p>
          <p className="text-slate-600">
            Asking {formatMoney(item.price, item.currency)} · {item.location || item.country}
          </p>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-slate-500">Mileage</dt>
              <dd className="mt-0.5 font-medium">
                {item.mileage != null
                  ? `${new Intl.NumberFormat("en-US").format(Number(item.mileage))} ${item.mileage_unit || ""}`.trim()
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Damage</dt>
              <dd className="mt-0.5 font-medium">{item.damage || "—"}</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-slate-500">VIN</dt>
              <dd className="mt-0.5 font-mono text-xs">{item.vin || "—"}</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-slate-500">Freshness</dt>
              <dd className="mt-0.5 font-medium">{item.freshness}</dd>
            </div>
          </dl>

          <div className="flex flex-wrap gap-3 pt-1">
            <Link href={`/?listing_id=${item.id}`} className="btn">
              Recalculate landed cost
            </Link>
            <Link href={importHref(item)} className="btn-secondary">
              Import this car
            </Link>
            {item.source_url && (
              <a href={item.source_url} target="_blank" rel="noreferrer" className="btn-secondary">
                Open listing
              </a>
            )}
          </div>
          {item.source_url && (
            <p className="break-all text-xs text-slate-500">
              Will use: <span className="text-teal-700">{item.source_url}</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
