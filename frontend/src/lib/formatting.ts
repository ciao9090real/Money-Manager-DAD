export const formatMoney = (value: number | string | null | undefined, currency = "EUR") =>
  new Intl.NumberFormat(
    typeof document !== "undefined" ? document.documentElement.lang || "en" : "en",
    { style: "currency", currency }
  ).format(Number(value || 0));

export function parseDateValue(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function formatDateValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
