import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function formatBytes(bytes: number | undefined): string {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function relativeDays(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const days = Math.floor((Date.now() - d.getTime()) / 86_400_000);
  if (days <= 0) return "aujourd'hui";
  if (days === 1) return "hier";
  if (days < 7) return `il y a ${days} j`;
  if (days < 30) return `il y a ${Math.floor(days / 7)} sem`;
  return `il y a ${Math.floor(days / 30)} mois`;
}

export function scoreColor(score: number): {
  bg: string;
  text: string;
  ring: string;
} {
  // Palette DESIGN.md : vert = succès (fort), bleu = info (moyen), slate = neutre.
  if (score >= 80)
    return {
      bg: "bg-secondary-container",
      text: "text-on-secondary-container",
      ring: "ring-secondary",
    };
  if (score >= 60)
    return {
      bg: "bg-tertiary-container",
      text: "text-on-tertiary-container",
      ring: "ring-tertiary",
    };
  return {
    bg: "bg-surface-highest",
    text: "text-on-surface-variant",
    ring: "ring-outline-variant",
  };
}

export function debounce<A extends unknown[]>(
  fn: (...args: A) => void,
  delay: number
): (...args: A) => void {
  let t: number | null = null;
  return (...args: A) => {
    if (t !== null) window.clearTimeout(t);
    t = window.setTimeout(() => fn(...args), delay);
  };
}
