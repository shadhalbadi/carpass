/** Format numbers with thousand commas (groups of 3). */

export function formatNumber(
  value: number | string | null | undefined,
  fractionDigits?: number,
): string {
  if (value == null || value === "") return "—";
  const n = typeof value === "number" ? value : Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(n)) return String(value);

  const opts: Intl.NumberFormatOptions = {
    useGrouping: true,
    maximumFractionDigits: fractionDigits ?? (Number.isInteger(n) ? 0 : 3),
  };
  if (fractionDigits != null) {
    opts.minimumFractionDigits = fractionDigits;
    opts.maximumFractionDigits = fractionDigits;
  }
  return new Intl.NumberFormat("en-US", opts).format(n);
}

/** OMR amounts — always 3 decimal places with thousand commas. */
export function formatOmr(value: number | string | null | undefined): string {
  return formatNumber(value, 3);
}

/** Asking / currency amounts — commas; keep sensible decimals. */
export function formatMoney(
  value: number | string | null | undefined,
  currency?: string | null,
): string {
  if (value == null || value === "") return "—";
  const n = typeof value === "number" ? value : Number(String(value).replace(/,/g, ""));
  if (!Number.isFinite(n)) return String(value);
  const digits = Number.isInteger(n) ? 0 : 2;
  const formatted = formatNumber(n, digits);
  return currency ? `${formatted} ${currency}` : formatted;
}
