export type Source =
  | "la_bonne_alternance"
  | "indeed"
  | "wttj"
  | "hellowork"
  | "apec"
  | "linkedin"
  | "linkedin_manual";

export interface Offer {
  id: number;
  source: Source;
  url: string;
  title: string;
  company?: string | null;
  location?: string | null;
  contract?: string | null;
  salary?: string | null;
  description: string;
  skills: string[];
  score: number;
  reasoning: string;
  red_flags: string[];
  is_favorite: boolean;
  is_hidden: boolean;
  first_run_id?: number | null;
  is_new?: boolean;
  scraped_at?: string | null;
  scored_at?: string | null;
}

export interface GeneratedDocLite {
  id: number;
  offer_id: number;
  cv_id: number;
  adapted_cv_path: string;
  letter_path: string;
  generated_at?: string | null;
}

export interface OfferDetail {
  offer: Offer;
  docs: GeneratedDocLite | null;
}

export interface CV {
  id: number;
  filename: string;
  html_content?: string;
  uploaded_at?: string | null;
  is_default: boolean;
  size?: number;
}

export type LetterStyle = "natural" | "factual" | "story" | "direct";

export const LETTER_STYLES: { value: LetterStyle; label: string; hint: string }[] = [
  { value: "natural", label: "Naturel", hint: "Pro mais conversationnel (défaut)" },
  { value: "factual", label: "Factuel", hint: "Direct, chiffré, sans rhétorique" },
  { value: "story", label: "Story", hint: "Anecdote concrète en accroche" },
  { value: "direct", label: "Très direct", hint: "Sans politesses, percutant" },
];

export interface Profile {
  name: string;
  email?: string;
  phone?: string;
  linkedin?: string;
  location: string;
  contract_types: string[];
  tagline?: string;
  signature_achievements?: string[];
  letter_style?: LetterStyle;
  forbidden_phrases?: string[];
  keywords: Record<string, string[]>;
  sources_enabled: Record<Source, boolean>;
  score_threshold_generate: number;
  max_offers_per_source: number;
}

export type ProgressStage =
  | "idle"
  | "scraping"
  | "scoring"
  | "generating"
  | "done"
  | "error";

export interface SourceProgress {
  source: string;
  state: "pending" | "running" | "done" | "error" | "skipped";
  count: number;
  duration_s?: number | null;
  error?: string | null;
  last_title?: string | null;
}

export interface Progress {
  stage: ProgressStage;
  source?: string | null;
  current: number;
  total: number;
  message: string;
  offer_id?: number | null;
  per_source?: SourceProgress[] | null;
}

export interface CVStyle {
  accent_color: string;
  density: number;
  photo_enabled: boolean;
  font: "Poppins" | "Inter" | "Manrope";
  template?: string;  // "modern_2col" | "minimal_1col" | "bold_header" | (futur)
}

export interface CVTemplateInfo {
  key: string;
  label: string;
  description: string;
}

export interface CVContact {
  email: string | null;
  phone: string | null;
  linkedin: string | null;
  location: string | null;
}

export interface CVExperience {
  company: string;
  role: string;
  period: string;
  bullets: string[];
}

export interface CVFormation {
  degree: string;
  school: string;
  period: string;
}

export interface CVProject {
  name: string;
  summary: string;
}

export interface CVLanguage {
  name: string;
  level: string | null;
}

export interface CVStructured {
  name: string | null;
  role: string | null;
  contact: CVContact;
  intro: string | null;
  hard_skills: string[];
  soft_skills: string[];
  tools: string[];
  languages: CVLanguage[];
  formations: CVFormation[];
  experiences: CVExperience[];
  projects_pedagogical: CVProject[];
  projects_personal: CVProject[];
}

export interface CVEditable {
  structured: CVStructured;
  style: CVStyle;
}

export type ViewKey = "offers" | "favorites" | "cvs" | "settings";

export const SOURCES: { key: Source; label: string }[] = [
  { key: "la_bonne_alternance", label: "La Bonne Alternance" },
  { key: "indeed", label: "Indeed" },
  { key: "wttj", label: "Welcome to the Jungle" },
  { key: "hellowork", label: "HelloWork" },
  { key: "apec", label: "Apec" },
  { key: "linkedin", label: "LinkedIn" },
  { key: "linkedin_manual", label: "LinkedIn (manuel)" },
];

export const SOURCE_LABEL: Record<Source, string> = Object.fromEntries(
  SOURCES.map((s) => [s.key, s.label])
) as Record<Source, string>;
