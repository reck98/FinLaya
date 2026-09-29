export function formatCurrency(amount: number, showSign: boolean = true): string {
  const isPositive = amount > 0;
  const isNegative = amount < 0;
  const formatted = Math.abs(amount).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  if (showSign) {
    if (isPositive) return `+₹${formatted}`;
    if (isNegative) return `-₹${formatted}`;
    return `₹${formatted}`;
  }
  return `₹${formatted}`;
}

export function formatPrice(price: number): string {
  return (price || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatTime(isoOrTimeStr: string | null): string {
  if (!isoOrTimeStr) return "--:--:--";
  try {
    if (isoOrTimeStr.includes("T")) {
      const parts = isoOrTimeStr.split("T")[1];
      return parts.split("+")[0].split(".")[0];
    }
    return isoOrTimeStr;
  } catch {
    return isoOrTimeStr;
  }
}

export function formatMilliseconds(isoStr: string | null): string {
  if (!isoStr) return "";
  try {
    if (isoStr.includes(".")) {
      const ms = isoStr.split(".")[1]?.substring(0, 3);
      return ms ? `.${ms}` : "";
    }
    return "";
  } catch {
    return "";
  }
}
