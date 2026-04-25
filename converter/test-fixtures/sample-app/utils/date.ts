import { format, formatDistance, parseISO } from "date-fns";

export function formatDate(dateString: string): string {
  return format(parseISO(dateString), "MMM d, yyyy");
}

export function formatRelative(dateString: string): string {
  return formatDistance(parseISO(dateString), new Date(), { addSuffix: true });
}

export function isRecent(dateString: string, days = 7): boolean {
  const date = parseISO(dateString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  return diff < days * 24 * 60 * 60 * 1000;
}
