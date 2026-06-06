import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ArrowDownToLine,
  ArrowUpToLine,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  Eye,
  EyeOff,
  GripVertical,
  Image as ImageIcon,
  Layout,
  Loader2,
  Maximize2,
  Plus,
  Redo2,
  Save,
  Sparkles,
  Trash2,
  Type,
  Undo2,
  Wand2,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import {
  aiRewriteBlock,
  aiRewriteBullet,
  aiRewriteGlobal,
  cloneStyleFromImage,
  downloadCVPdfUrl,
  getCVEditable,
  listCVInspirations,
  listCVTemplates,
  putCVEditable,
  renderCVPreview,
  type CVInspiration,
} from "../api";
import type {
  CVEditable,
  CVExperience,
  CVFormation,
  CVLanguage,
  CVProject,
  CVStructured,
  CVStyle,
  CVTemplateInfo,
} from "../types";
import { cn } from "../lib/utils";

// ----------------------------------------------------------------------
// Constantes
// ----------------------------------------------------------------------

const ACCENT_PRESETS = [
  "#2d52c4", "#0f766e", "#7c3aed", "#db2777", "#e0479a", "#e2680f", "#16a34a", "#0ea5e9",
];
const FONT_OPTIONS: CVStyle["font"][] = ["Poppins", "Inter", "Manrope"];

// #13 — Bibliothèque de gabarits de style CV (persistés en localStorage)
function StylePresets({
  style,
  onApply,
}: {
  style: CVStyle;
  onApply: (st: CVStyle) => void;
}) {
  const [presets, setPresets] = useState<Record<string, CVStyle>>(() => {
    try {
      return JSON.parse(localStorage.getItem("cv_style_presets") || "{}");
    } catch {
      return {};
    }
  });
  const names = Object.keys(presets);
  const save = () => {
    const name = prompt("Nom du gabarit ?")?.trim();
    if (!name) return;
    const next = { ...presets, [name]: style };
    setPresets(next);
    localStorage.setItem("cv_style_presets", JSON.stringify(next));
  };
  return (
    <span className="inline-flex items-center gap-1" title="Gabarits de style enregistrés">
      <select
        value=""
        onChange={(e) => {
          const p = presets[e.target.value];
          if (p) onApply(p);
        }}
        className="text-xs border border-outline-variant rounded px-1.5 py-1 max-w-[120px]"
      >
        <option value="">Gabarits…</option>
        {names.map((n) => (
          <option key={n} value={n}>{n}</option>
        ))}
      </select>
      <button
        onClick={save}
        title="Enregistrer le style actuel comme gabarit"
        className="inline-flex items-center text-xs px-1.5 py-1 rounded border border-outline-variant text-on-surface hover:border-outline hover:bg-surface-c"
      >
        <Save size={12} />
      </button>
    </span>
  );
}

const A4_W = 794;   // 210mm @ 96dpi
const A4_H = 1123;  // 297mm

const ZOOM_PRESETS = [0.5, 0.75, 1.0, 1.25, 1.5];

// ----------------------------------------------------------------------
// Helpers path-based
// ----------------------------------------------------------------------

function getAtPath(obj: any, path: string): any {
  if (!path) return obj;
  const segs = path.split(".");
  let cur: any = obj;
  for (const s of segs) {
    if (cur == null) return undefined;
    const idx = /^\d+$/.test(s) ? Number(s) : s;
    cur = cur[idx as any];
  }
  return cur;
}

function setAtPath<T>(obj: T, path: string, value: any): T {
  if (!path) return value as T;
  const segs = path.split(".");
  const clone = Array.isArray(obj) ? [...(obj as any)] : { ...(obj as any) };
  let cur: any = clone;
  for (let i = 0; i < segs.length - 1; i++) {
    const s = segs[i];
    const idx = /^\d+$/.test(s) ? Number(s) : s;
    const child = cur[idx as any];
    const next = Array.isArray(child) ? [...child] : { ...(child ?? {}) };
    cur[idx as any] = next;
    cur = next;
  }
  const last = segs[segs.length - 1];
  cur[/^\d+$/.test(last) ? Number(last) : last] = value;
  return clone as T;
}

function isListPath(path: string): boolean {
  // Détecte un index final (ex: "experiences.0.bullets.2", "hard_skills.3")
  return /\.\d+$/.test(path);
}

function parentPathAndIndex(path: string): [string, number] {
  const m = path.match(/^(.+)\.(\d+)$/);
  if (!m) return [path, -1];
  return [m[1], Number(m[2])];
}

// ----------------------------------------------------------------------
// Composant principal
// ----------------------------------------------------------------------

interface Props {
  offerId: number;
}

export function CVVisualEditor({ offerId }: Props) {
  const [data, setData] = useState<CVEditable | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedRect, setSelectedRect] = useState<DOMRectLike | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<"saved" | "dirty" | null>(null);
  const [zoom, setZoom] = useState(0.85);
  const [previewMode, setPreviewMode] = useState(false);
  const [globalAIOpen, setGlobalAIOpen] = useState(false);
  const [globalAIBusy, setGlobalAIBusy] = useState(false);
  const [globalAIError, setGlobalAIError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<CVTemplateInfo[]>([]);
  const [inspirationsOpen, setInspirationsOpen] = useState(false);

  useEffect(() => {
    listCVTemplates().then(setTemplates).catch(() => setTemplates([]));
  }, []);

  // history stack — chaque modif locale est pushée (debounced)
  const historyRef = useRef<CVEditable[]>([]);
  const historyIdxRef = useRef<number>(-1);
  const lastPushedSig = useRef<string>("");
  const [historyVersion, setHistoryVersion] = useState(0);  // pour re-render
  const canUndo = historyIdxRef.current > 0;
  const canRedo = historyIdxRef.current < historyRef.current.length - 1;

  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const saveTimerRef = useRef<number | null>(null);
  const previewTimerRef = useRef<number | null>(null);

  // --- Initial load ---
  useEffect(() => {
    getCVEditable(offerId).then((d) => {
      setData(d);
      historyRef.current = [d];
      historyIdxRef.current = 0;
      lastPushedSig.current = JSON.stringify(d);
    });
  }, [offerId]);

  // --- Bridge iframe ---
  useEffect(() => {
    const onMessage = (ev: MessageEvent) => {
      const m = ev.data || {};
      if (m.type === "cv-ready") {
        iframeRef.current?.contentWindow?.postMessage(
          { type: "cv-editor-mode", on: !previewMode },
          "*"
        );
      } else if (m.type === "cv-select") {
        setSelected(typeof m.path === "string" ? m.path : null);
        setSelectedRect(m.rect ?? null);
      } else if (m.type === "cv-edit-commit") {
        applyEdit(m.path, m.value);
      } else if (m.type === "cv-edit-cancel") {
        // rien à faire : la valeur en mémoire n'a pas changé
      } else if (m.type === "cv-edit-start") {
        // optionnel : pourrait afficher un indicateur
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewMode]);

  // Push iframe sync on preview update + on previewMode change
  useEffect(() => {
    iframeRef.current?.contentWindow?.postMessage(
      { type: "cv-editor-mode", on: !previewMode },
      "*"
    );
  }, [previewMode, previewHtml]);

  // --- Preview re-render (debounce 250ms) ---
  useEffect(() => {
    if (!data) return;
    if (previewTimerRef.current) window.clearTimeout(previewTimerRef.current);
    previewTimerRef.current = window.setTimeout(async () => {
      try {
        const r = await renderCVPreview(offerId, data.structured, data.style);
        setPreviewHtml(r.html);
      } catch (e) {
        console.error("preview render failed", e);
      }
    }, 250);
    return () => {
      if (previewTimerRef.current) window.clearTimeout(previewTimerRef.current);
    };
  }, [data, offerId]);

  // Refocus selection in iframe after each re-render
  useEffect(() => {
    if (!previewHtml || !selected) return;
    const t = window.setTimeout(() => {
      iframeRef.current?.contentWindow?.postMessage(
        { type: "cv-select", path: selected },
        "*"
      );
    }, 80);
    return () => window.clearTimeout(t);
  }, [previewHtml, selected]);

  // --- Autosave (debounce 1.2s) + history push ---
  useEffect(() => {
    if (!data) return;
    const sig = JSON.stringify(data);
    setSaved("dirty");
    // Push to history if sig changed
    if (sig !== lastPushedSig.current) {
      // truncate forward history
      const hist = historyRef.current.slice(0, historyIdxRef.current + 1);
      hist.push(data);
      // cap history size at 60 entries
      if (hist.length > 60) hist.shift();
      historyRef.current = hist;
      historyIdxRef.current = hist.length - 1;
      lastPushedSig.current = sig;
      setHistoryVersion((v) => v + 1);
    }
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(async () => {
      setSaving(true);
      try {
        await putCVEditable(offerId, data.structured, data.style);
        setSaved("saved");
      } catch {
        setSaved("dirty");
      } finally {
        setSaving(false);
      }
    }, 1200);
    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    };
  }, [data, offerId]);

  // Télécharge le PDF en garantissant que le cv.html persisté reflète l'état
  // courant (densité comprise) : on flush la sauvegarde en attente avant d'ouvrir.
  const handleDownloadPdf = useCallback(async () => {
    if (!data) return;
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    setSaving(true);
    try {
      await putCVEditable(offerId, data.structured, data.style);
      setSaved("saved");
    } catch {
      setSaved("dirty");
    } finally {
      setSaving(false);
    }
    window.open(downloadCVPdfUrl(offerId), "_blank", "noopener");
  }, [data, offerId]);

  // --- Mutations ---
  const updateStructured = useCallback((mut: (s: CVStructured) => CVStructured) => {
    setData((d) => (d ? { ...d, structured: mut(d.structured) } : d));
  }, []);
  const updateStyle = useCallback((mut: (s: CVStyle) => CVStyle) => {
    setData((d) => (d ? { ...d, style: mut(d.style) } : d));
  }, []);
  const setValueAtPath = useCallback((path: string, value: any) => {
    setData((d) => (d ? { ...d, structured: setAtPath(d.structured, path, value) } : d));
  }, []);
  const applyEdit = useCallback((path: string, value: string) => {
    setValueAtPath(path, value);
  }, [setValueAtPath]);

  // --- Undo / redo ---
  const undo = useCallback(() => {
    if (historyIdxRef.current <= 0) return;
    historyIdxRef.current -= 1;
    const prev = historyRef.current[historyIdxRef.current];
    lastPushedSig.current = JSON.stringify(prev);
    setData(prev);
    setHistoryVersion((v) => v + 1);
  }, []);
  const redo = useCallback(() => {
    if (historyIdxRef.current >= historyRef.current.length - 1) return;
    historyIdxRef.current += 1;
    const next = historyRef.current[historyIdxRef.current];
    lastPushedSig.current = JSON.stringify(next);
    setData(next);
    setHistoryVersion((v) => v + 1);
  }, []);

  // --- Keyboard shortcuts ---
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (meta && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
        e.preventDefault();
        redo();
      } else if (e.key === "Escape") {
        setSelected(null);
        setSelectedRect(null);
      } else if (meta && e.key === "+") {
        e.preventDefault();
        setZoom((z) => Math.min(1.5, +(z + 0.1).toFixed(2)));
      } else if (meta && e.key === "-") {
        e.preventDefault();
        setZoom((z) => Math.max(0.5, +(z - 0.1).toFixed(2)));
      } else if (meta && e.key === "0") {
        e.preventDefault();
        setZoom(1.0);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo]);

  // --- Floating actions on selected block ---
  const floatingActions = useMemo(
    () => buildFloatingActions(selected, data?.structured ?? null),
    [selected, data?.structured]
  );

  const handleFloatingAction = (a: FloatingAction) => {
    if (!data || !selected) return;
    const struct = data.structured;
    if (a === "edit-inline") {
      iframeRef.current?.contentWindow?.postMessage(
        { type: "cv-focus-edit", path: selected },
        "*"
      );
      return;
    }
    if (a === "delete") {
      const [parent, idx] = parentPathAndIndex(selected);
      if (idx < 0) return;
      const list = getAtPath(struct, parent) as any[];
      if (!Array.isArray(list)) return;
      const next = list.filter((_, i) => i !== idx);
      setValueAtPath(parent, next);
      setSelected(null);
      return;
    }
    if (a === "move-up" || a === "move-down") {
      const [parent, idx] = parentPathAndIndex(selected);
      if (idx < 0) return;
      const list = getAtPath(struct, parent) as any[];
      if (!Array.isArray(list)) return;
      const newIdx = a === "move-up" ? idx - 1 : idx + 1;
      if (newIdx < 0 || newIdx >= list.length) return;
      const next = arrayMove(list, idx, newIdx);
      setValueAtPath(parent, next);
      setSelected(`${parent}.${newIdx}`);
      return;
    }
    if (a === "duplicate") {
      const [parent, idx] = parentPathAndIndex(selected);
      if (idx < 0) return;
      const list = getAtPath(struct, parent) as any[];
      if (!Array.isArray(list)) return;
      const dup = JSON.parse(JSON.stringify(list[idx]));
      const next = [...list.slice(0, idx + 1), dup, ...list.slice(idx + 1)];
      setValueAtPath(parent, next);
      setSelected(`${parent}.${idx + 1}`);
      return;
    }
  };

  const applyGlobalAI = useCallback(
    async (instruction: string) => {
      if (!data || !instruction.trim()) return;
      setGlobalAIBusy(true);
      setGlobalAIError(null);
      try {
        const r = await aiRewriteGlobal(offerId, data.structured, instruction.trim());
        if (r.structured && typeof r.structured === "object") {
          setData((d) => (d ? { ...d, structured: r.structured } : d));
          setGlobalAIOpen(false);
        }
      } catch (e) {
        setGlobalAIError(e instanceof Error ? e.message : String(e));
      } finally {
        setGlobalAIBusy(false);
      }
    },
    [data, offerId]
  );

  if (!data) {
    return <div className="p-6 text-sm text-on-surface-variant">Chargement de l'éditeur…</div>;
  }

  return (
    <div className="flex flex-col h-full">
      <Toolbar
        style={data.style}
        onChangeStyle={updateStyle}
        zoom={zoom}
        onZoom={setZoom}
        previewMode={previewMode}
        onTogglePreview={() => setPreviewMode((p) => !p)}
        saved={saved}
        saving={saving}
        canUndo={canUndo}
        canRedo={canRedo}
        onUndo={undo}
        onRedo={redo}
        historyTick={historyVersion}
        onOpenGlobalAI={() => setGlobalAIOpen(true)}
        onOpenInspirations={() => setInspirationsOpen(true)}
        onDownloadPdf={handleDownloadPdf}
        templates={templates}
      />
      {globalAIOpen && (
        <GlobalAIBar
          busy={globalAIBusy}
          error={globalAIError}
          onApply={applyGlobalAI}
          onClose={() => setGlobalAIOpen(false)}
        />
      )}
      {inspirationsOpen && data && (
        <InspirationsModal
          currentStyle={data.style}
          onApply={(newStyle) => {
            setData((d) => (d ? { ...d, style: { ...d.style, ...newStyle } } : d));
            setInspirationsOpen(false);
          }}
          onClose={() => setInspirationsOpen(false)}
        />
      )}
      <div className="flex flex-1 min-h-0">
        <Canvas
          iframeRef={iframeRef}
          previewHtml={previewHtml}
          zoom={zoom}
          selectedRect={selectedRect}
          actions={floatingActions}
          onAction={handleFloatingAction}
          previewMode={previewMode}
        />
        {!previewMode && (
          <aside className="w-[400px] shrink-0 border-l border-outline-variant bg-surface-lowest flex flex-col overflow-hidden">
            <BlockPanel
              offerId={offerId}
              data={data}
              selected={selected}
              onSelect={setSelected}
              onUpdate={updateStructured}
              onUpdateStructured={(s) => setData({ ...data, structured: s })}
            />
          </aside>
        )}
      </div>
    </div>
  );
}

type DOMRectLike = { top: number; left: number; width: number; height: number };

// ----------------------------------------------------------------------
// Toolbar
// ----------------------------------------------------------------------

function Toolbar({
  style,
  onChangeStyle,
  zoom,
  onZoom,
  previewMode,
  onTogglePreview,
  saved,
  saving,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
  onOpenGlobalAI,
  onOpenInspirations,
  onDownloadPdf,
  templates,
}: {
  style: CVStyle;
  onChangeStyle: (mut: (s: CVStyle) => CVStyle) => void;
  zoom: number;
  onZoom: (z: number) => void;
  previewMode: boolean;
  onTogglePreview: () => void;
  saved: "saved" | "dirty" | null;
  saving: boolean;
  canUndo: boolean;
  canRedo: boolean;
  onOpenInspirations: () => void;
  onUndo: () => void;
  onRedo: () => void;
  historyTick: number;
  onOpenGlobalAI: () => void;
  onDownloadPdf: () => void;
  templates: CVTemplateInfo[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-2 px-4 py-2 border-b border-outline-variant bg-surface-lowest text-sm">
      {/* Undo/Redo */}
      <IconBtn onClick={onUndo} disabled={!canUndo} title="Annuler (⌘Z)">
        <Undo2 size={14} />
      </IconBtn>
      <IconBtn onClick={onRedo} disabled={!canRedo} title="Rétablir (⇧⌘Z)">
        <Redo2 size={14} />
      </IconBtn>
      <Sep />

      {/* Global AI */}
      <button
        onClick={onOpenGlobalAI}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium bg-gradient-to-br from-tertiary to-fuchsia-600 text-white hover:brightness-110 hover:to-fuchsia-700 shadow-sm"
        title="IA globale — retravaille tout le CV"
      >
        <Wand2 size={12} /> IA globale
      </button>

      <Sep />

      {/* Accent */}
      <span className="text-[11px] text-on-surface-variant ml-1">Accent</span>
      <div className="flex gap-1">
        {ACCENT_PRESETS.map((c) => (
          <button
            key={c}
            onClick={() => onChangeStyle((s) => ({ ...s, accent_color: c }))}
            style={{ background: c }}
            className={cn(
              "w-4 h-4 rounded-full border",
              style.accent_color.toLowerCase() === c.toLowerCase()
                ? "ring-2 ring-offset-1 ring-tertiary border-white"
                : "border-outline-variant"
            )}
            aria-label={`Accent ${c}`}
          />
        ))}
      </div>
      <input
        type="color"
        value={style.accent_color}
        onChange={(e) => onChangeStyle((s) => ({ ...s, accent_color: e.target.value }))}
        className="w-6 h-6 rounded border border-outline-variant cursor-pointer"
        aria-label="Custom"
      />

      <Sep />

      {/* Density */}
      <span className="text-[11px] text-on-surface-variant">Densité</span>
      <input
        type="range"
        min={0.7}
        max={1.5}
        step={0.05}
        value={style.density}
        onChange={(e) => onChangeStyle((s) => ({ ...s, density: Number(e.target.value) }))}
        className="w-20 accent-[var(--tertiary)]"
      />
      <span className="text-[11px] text-on-surface-variant w-6 tabular-nums">{style.density.toFixed(2)}</span>

      <Sep />

      {/* Template */}
      {templates.length > 0 && (
        <label className="inline-flex items-center gap-1.5" title="Template visuel">
          <Layout size={12} className="text-on-surface-variant" />
          <select
            value={style.template ?? "modern_2col"}
            onChange={(e) => onChangeStyle((s) => ({ ...s, template: e.target.value }))}
            className="text-xs border border-outline-variant rounded px-1.5 py-1 max-w-[160px]"
          >
            {templates.map((t) => (
              <option key={t.key} value={t.key} title={t.description}>{t.label}</option>
            ))}
          </select>
        </label>
      )}
      <StylePresets style={style} onApply={(st) => onChangeStyle((s) => ({ ...s, ...st }))} />
      <button
        onClick={onOpenInspirations}
        title="Galerie d'inspirations CV (scraped) — clone le style avec l'IA"
        className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-outline-variant text-on-surface hover:border-outline hover:bg-surface-c"
      >
        <ImageIcon size={12} /> Inspirations
      </button>

      <Sep />

      {/* Police */}
      <select
        value={style.font}
        onChange={(e) => onChangeStyle((s) => ({ ...s, font: e.target.value as CVStyle["font"] }))}
        className="text-xs border border-outline-variant rounded px-1.5 py-1"
        title="Police"
      >
        {FONT_OPTIONS.map((f) => (
          <option key={f} value={f}>{f}</option>
        ))}
      </select>

      {/* Photo */}
      <label className="flex items-center gap-1 cursor-pointer ml-1" title="Afficher la photo">
        <input
          type="checkbox"
          checked={style.photo_enabled}
          onChange={(e) => onChangeStyle((s) => ({ ...s, photo_enabled: e.target.checked }))}
          className="accent-[var(--tertiary)]"
        />
        <span className="text-[11px] text-on-surface">Photo</span>
      </label>

      <div className="ml-auto flex items-center gap-1.5">
        {/* Zoom */}
        <IconBtn onClick={() => onZoom(Math.max(0.5, +(zoom - 0.1).toFixed(2)))} title="Zoom − (⌘−)">
          <ZoomOut size={14} />
        </IconBtn>
        <select
          value={ZOOM_PRESETS.includes(zoom) ? zoom : 1.0}
          onChange={(e) => onZoom(Number(e.target.value))}
          className="text-xs border border-outline-variant rounded px-1.5 py-1"
          title="Zoom"
        >
          {ZOOM_PRESETS.map((z) => (
            <option key={z} value={z}>{Math.round(z * 100)}%</option>
          ))}
        </select>
        <IconBtn onClick={() => onZoom(Math.min(1.5, +(zoom + 0.1).toFixed(2)))} title="Zoom + (⌘+)">
          <ZoomIn size={14} />
        </IconBtn>
        <IconBtn onClick={() => onZoom(1.0)} title="100% (⌘0)">
          <Maximize2 size={14} />
        </IconBtn>

        <Sep />

        <IconBtn onClick={onTogglePreview} title={previewMode ? "Quitter aperçu" : "Aperçu final"}>
          {previewMode ? <EyeOff size={14} /> : <Eye size={14} />}
        </IconBtn>

        <span className="text-xs text-on-surface-variant min-w-[80px] text-right">
          {saving ? (
            <span className="inline-flex items-center gap-1"><Loader2 size={11} className="animate-spin" /> …</span>
          ) : saved === "saved" ? (
            <span className="text-secondary inline-flex items-center gap-1"><Save size={11} /> Sauvé</span>
          ) : saved === "dirty" ? (
            <span className="text-on-surface-variant">Modifs…</span>
          ) : null}
        </span>

        <button
          onClick={onDownloadPdf}
          disabled={saving}
          title="Sauvegarde l'état courant puis télécharge le PDF (identique à l'aperçu)"
          className="btn-primary btn-sm"
        >
          {saving ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Download size={12} />
          )}
          Télécharger PDF
        </button>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------
// Barre IA globale — modifie tout le structured d'un coup
// ----------------------------------------------------------------------

const GLOBAL_PRESETS: { label: string; instruction: string; tone: "fill" | "fit" | "tighten" | "boost" }[] = [
  {
    label: "Préremplir depuis mon CV source",
    instruction:
      "Pré-remplis le CV adapté à partir du profil source : sélectionne 2-4 expériences les plus pertinentes pour l'offre, 3-5 bullets par expérience reformulés pour matcher les compétences clés, 6-8 hard skills triés par pertinence, intro italique adaptée à l'offre, role court en français. N'invente AUCUN fait.",
    tone: "fill",
  },
  {
    label: "Adapter à fond à l'offre",
    instruction:
      "Refonds le CV pour qu'il colle au maximum à l'offre cible : réordonne expériences et bullets par pertinence, reformule les verbes d'action pour matcher le langage de l'offre, ajuste hard_skills et tools selon ce que demande le poste.",
    tone: "fit",
  },
  {
    label: "Raccourcir tout",
    instruction:
      "Compacte le CV : maximum 3 bullets par expérience, garde uniquement les plus impactants, raccourcis l'intro à 1 phrase, vire les expériences les moins pertinentes pour ce poste.",
    tone: "tighten",
  },
  {
    label: "Plus d'impact business",
    instruction:
      "Réécris tous les bullets en orientation impact : verbe d'action en premier, chiffre ou résultat mesurable quand disponible dans la source, vocabulaire growth/produit/résultat plutôt que technique pur.",
    tone: "boost",
  },
];

function GlobalAIBar({
  busy,
  error,
  onApply,
  onClose,
}: {
  busy: boolean;
  error: string | null;
  onApply: (instruction: string) => void;
  onClose: () => void;
}) {
  const [text, setText] = useState("");
  return (
    <div className="border-b border-tertiary bg-gradient-to-r from-tertiary-container via-fuchsia-50 to-tertiary-container">
      <div className="px-4 py-3 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Wand2 size={14} className="text-tertiary" />
          <div className="text-xs font-semibold text-on-tertiary-container">IA globale — réécris le CV entier</div>
          <button onClick={onClose} className="ml-auto text-on-surface-variant hover:text-on-surface" title="Fermer (Esc)">
            <X size={14} />
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {GLOBAL_PRESETS.map((p) => (
            <button
              key={p.label}
              onClick={() => onApply(p.instruction)}
              disabled={busy}
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors",
                busy
                  ? "bg-surface-container text-on-surface-variant border-outline-variant cursor-not-allowed"
                  : "bg-surface-lowest text-on-tertiary-container border-tertiary hover:bg-tertiary-container hover:border-tertiary"
              )}
            >
              <Sparkles size={11} />
              {p.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                if (text.trim()) onApply(text);
              }
              if (e.key === "Escape") onClose();
            }}
            placeholder="Ou décris ce que tu veux changer sur tout le CV… (⌘+Enter pour appliquer)"
            rows={2}
            disabled={busy}
            className="flex-1 text-sm border border-tertiary rounded-md px-3 py-2 bg-surface-lowest focus:border-tertiary focus:outline-none resize-none"
          />
          <button
            onClick={() => text.trim() && onApply(text)}
            disabled={busy || !text.trim()}
            className={cn(
              "shrink-0 px-3 rounded-md text-xs font-semibold inline-flex items-center gap-1.5",
              busy || !text.trim()
                ? "bg-surface-highest text-on-surface-variant cursor-not-allowed"
                : "bg-tertiary text-white hover:brightness-110"
            )}
          >
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
            {busy ? "Réécriture…" : "Appliquer"}
          </button>
        </div>
        {error && <div className="text-xs text-on-error-container">{error}</div>}
        {busy && (
          <div className="text-[11px] text-tertiary">
            Sonnet retravaille le CV (≈8-15s, ~0.02€). Tu peux annuler avec ⌘Z après.
          </div>
        )}
      </div>
    </div>
  );
}

function IconBtn({
  onClick,
  children,
  disabled,
  title,
  active,
}: {
  onClick?: () => void;
  children: ReactNode;
  disabled?: boolean;
  title?: string;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        "p-1.5 rounded-md border border-transparent",
        disabled
          ? "text-on-surface-variant cursor-not-allowed"
          : active
            ? "bg-navy text-white"
            : "text-on-surface hover:bg-surface-container hover:border-outline-variant"
      )}
    >
      {children}
    </button>
  );
}

function Sep() {
  return <span className="w-px h-5 bg-surface-highest mx-1" />;
}

// ----------------------------------------------------------------------
// Canvas — iframe centrée avec zoom + floating action bar
// ----------------------------------------------------------------------

type FloatingAction =
  | "edit-inline"
  | "delete"
  | "move-up"
  | "move-down"
  | "duplicate";

function buildFloatingActions(path: string | null, struct: CVStructured | null): FloatingAction[] {
  if (!path || !struct) return [];
  const acts: FloatingAction[] = ["edit-inline"];
  if (isListPath(path)) {
    const [parent, idx] = parentPathAndIndex(path);
    const list = getAtPath(struct, parent) as any[];
    if (Array.isArray(list)) {
      if (idx > 0) acts.push("move-up");
      if (idx < list.length - 1) acts.push("move-down");
      // duplicate uniquement sur les listes d'objets, pas sur strings
      if (typeof list[idx] === "object" && list[idx] !== null) acts.push("duplicate");
      acts.push("delete");
    }
  }
  return acts;
}

function Canvas({
  iframeRef,
  previewHtml,
  zoom,
  selectedRect,
  actions,
  onAction,
  previewMode,
}: {
  iframeRef: React.RefObject<HTMLIFrameElement>;
  previewHtml: string;
  zoom: number;
  selectedRect: DOMRectLike | null;
  actions: FloatingAction[];
  onAction: (a: FloatingAction) => void;
  previewMode: boolean;
}) {
  const wrapperW = Math.ceil(A4_W * zoom);
  const wrapperH = Math.ceil(A4_H * zoom);

  return (
    <div className="flex-1 min-w-0 bg-surface-container overflow-auto relative">
      <div className="mx-auto py-8 flex justify-center">
        <div className="relative" style={{ width: wrapperW, height: wrapperH }}>
          <div
            className="bg-surface-lowest shadow-lg origin-top-left"
            style={{
              width: A4_W,
              height: A4_H,
              transform: `scale(${zoom})`,
              transformOrigin: "top left",
            }}
          >
            <iframe
              ref={iframeRef}
              title="CV preview"
              srcDoc={previewHtml}
              sandbox="allow-scripts allow-same-origin"
              className="w-full h-full border-0"
            />
          </div>
          {!previewMode && selectedRect && actions.length > 0 && (
            <FloatingActions
              rect={selectedRect}
              zoom={zoom}
              actions={actions}
              onAction={onAction}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function FloatingActions({
  rect,
  zoom,
  actions,
  onAction,
}: {
  rect: DOMRectLike;
  zoom: number;
  actions: FloatingAction[];
  onAction: (a: FloatingAction) => void;
}) {
  // rect = position dans la viewport de l'iframe (coords iframe)
  // L'iframe est scalée → on multiplie par zoom pour obtenir les coords parent
  const top = Math.max(0, rect.top * zoom - 36);
  const left = rect.left * zoom;
  return (
    <div
      className="absolute z-10 flex gap-0.5 bg-surface-lowest border border-outline-variant rounded-md shadow-lg p-0.5"
      style={{ top, left }}
    >
      {actions.includes("edit-inline") && (
        <ActBtn onClick={() => onAction("edit-inline")} title="Éditer (double-clic)">
          <Type size={12} />
        </ActBtn>
      )}
      {actions.includes("move-up") && (
        <ActBtn onClick={() => onAction("move-up")} title="Monter">
          <ArrowUpToLine size={12} />
        </ActBtn>
      )}
      {actions.includes("move-down") && (
        <ActBtn onClick={() => onAction("move-down")} title="Descendre">
          <ArrowDownToLine size={12} />
        </ActBtn>
      )}
      {actions.includes("duplicate") && (
        <ActBtn onClick={() => onAction("duplicate")} title="Dupliquer">
          <Copy size={12} />
        </ActBtn>
      )}
      {actions.includes("delete") && (
        <ActBtn onClick={() => onAction("delete")} title="Supprimer" danger>
          <Trash2 size={12} />
        </ActBtn>
      )}
    </div>
  );
}

function ActBtn({
  onClick,
  children,
  title,
  danger,
}: {
  onClick: () => void;
  children: ReactNode;
  title: string;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className={cn(
        "p-1.5 rounded text-on-surface-variant hover:bg-surface-container",
        danger && "hover:bg-error-container hover:text-on-error-container"
      )}
    >
      {children}
    </button>
  );
}

// ----------------------------------------------------------------------
// Panel droite — édition contextualisée
// ----------------------------------------------------------------------

function BlockPanel({
  offerId,
  data,
  selected,
  onSelect,
  onUpdate,
  onUpdateStructured,
}: {
  offerId: number;
  data: CVEditable;
  selected: string | null;
  onSelect: (p: string | null) => void;
  onUpdate: (mut: (s: CVStructured) => CVStructured) => void;
  onUpdateStructured: (s: CVStructured) => void;
}) {
  const struct = data.structured;
  const segs = selected ? selected.split(".") : [];
  const root = segs[0] ?? "";
  const inExpDetail = root === "experiences" && segs.length >= 2;

  return (
    <>
      <PanelHeader selected={selected} onClear={() => onSelect(null)} />
      <div className="flex-1 overflow-auto">
        {!selected && <Overview structured={struct} onSelect={onSelect} />}

        {selected === "name" && (
          <Section title="Nom complet" path="name" offerId={offerId} value={struct.name ?? ""} onChange={(v) => onUpdate((s) => ({ ...s, name: v }))}>
            <FieldInput value={struct.name ?? ""} onChange={(v) => onUpdate((s) => ({ ...s, name: v }))} placeholder="Prénom Nom" />
          </Section>
        )}
        {selected === "role" && (
          <Section title="Titre adapté à l'offre" path="role" offerId={offerId} value={struct.role ?? ""} onChange={(v) => onUpdate((s) => ({ ...s, role: v }))}>
            <FieldInput value={struct.role ?? ""} onChange={(v) => onUpdate((s) => ({ ...s, role: v }))} placeholder="Alternance Growth & Automatisation" />
            <QualityHint value={struct.role ?? ""} target={{ min: 3, max: 10, unit: "mots" }} />
          </Section>
        )}
        {selected === "intro" && (
          <Section title="Phrase d'intro" path="intro" offerId={offerId} value={struct.intro ?? ""} onChange={(v) => onUpdate((s) => ({ ...s, intro: v }))}>
            <FieldTextarea value={struct.intro ?? ""} onChange={(v) => onUpdate((s) => ({ ...s, intro: v }))} rows={3} placeholder="Phrase d'auto-présentation adaptée à l'offre" />
            <QualityHint value={struct.intro ?? ""} target={{ min: 15, max: 35, unit: "mots" }} />
          </Section>
        )}
        {selected === "contact" && (
          <ContactEditor struct={struct} onUpdate={onUpdate} />
        )}
        {selected === "hard_skills" && (
          <SortableStringList label="Hard Skills" values={struct.hard_skills} onChange={(v) => onUpdate((s) => ({ ...s, hard_skills: v }))} max={8} id="hs" placeholder="ex: Python, n8n…" />
        )}
        {selected === "soft_skills" && (
          <SortableStringList label="Soft Skills" values={struct.soft_skills} onChange={(v) => onUpdate((s) => ({ ...s, soft_skills: v }))} max={5} id="ss" placeholder="ex: Rigueur produit…" />
        )}
        {selected === "tools" && (
          <SortableStringList label="Stack & Outils" values={struct.tools} onChange={(v) => onUpdate((s) => ({ ...s, tools: v }))} max={12} id="tools" placeholder="ex: Notion, Linear…" />
        )}
        {selected === "languages" && (
          <LanguageEditor values={struct.languages} onChange={(v) => onUpdate((s) => ({ ...s, languages: v }))} />
        )}
        {selected === "formations" && (
          <FormationListEditor values={struct.formations} onChange={(v) => onUpdate((s) => ({ ...s, formations: v }))} />
        )}
        {root === "formations" && segs.length === 2 && (
          <FormationEditor index={Number(segs[1])} values={struct.formations} onChange={(v) => onUpdate((s) => ({ ...s, formations: v }))} />
        )}
        {selected === "experiences" && (
          <ExperienceListEditor values={struct.experiences} onChange={(v) => onUpdate((s) => ({ ...s, experiences: v }))} onSelect={onSelect} />
        )}
        {inExpDetail && (
          <ExperienceEditor segs={segs} values={struct.experiences} onChange={(v) => onUpdate((s) => ({ ...s, experiences: v }))} offerId={offerId} onSelect={onSelect} />
        )}
        {(selected === "projects_pedagogical" || selected === "projects_personal") && (
          <ProjectListEditor
            label={selected === "projects_pedagogical" ? "Projets pédagogiques" : "Projets personnels"}
            values={selected === "projects_pedagogical" ? struct.projects_pedagogical : struct.projects_personal}
            onChange={(v) =>
              onUpdate((s) => selected === "projects_pedagogical" ? { ...s, projects_pedagogical: v } : { ...s, projects_personal: v })
            }
          />
        )}
        {(root === "projects_pedagogical" || root === "projects_personal") && segs.length === 2 && (
          <ProjectEditor index={Number(segs[1])} values={root === "projects_pedagogical" ? struct.projects_pedagogical : struct.projects_personal}
            onChange={(v) => onUpdate((s) => root === "projects_pedagogical" ? { ...s, projects_pedagogical: v } : { ...s, projects_personal: v })}
          />
        )}

        {/* Outline (always visible at bottom) */}
        <SectionsOutline structured={struct} onSelect={onSelect} onUpdateStructured={onUpdateStructured} />
      </div>
    </>
  );
}

function PanelHeader({ selected, onClear }: { selected: string | null; onClear: () => void }) {
  if (!selected) {
    return (
      <div className="px-4 py-2.5 border-b border-outline-variant bg-gradient-to-b from-surface-container-low to-surface-lowest text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">
        Survol — clique un bloc du CV pour l'éditer
      </div>
    );
  }
  const segs = selected.split(".");
  return (
    <div className="px-4 py-2 border-b border-outline-variant bg-gradient-to-b from-surface-container-low to-surface-lowest flex items-center gap-2">
      <button onClick={onClear} className="text-on-surface-variant hover:text-on-surface text-xs">←</button>
      <div className="flex items-center gap-1 text-[11px] text-on-surface-variant truncate">
        {segs.map((s, i) => (
          <span key={i} className="inline-flex items-center gap-1">
            {i > 0 && <span className="text-on-surface-variant">/</span>}
            <span className={cn(i === segs.length - 1 && "text-on-surface font-medium")}>{s}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------
// Section wrapper (avec prompt IA libre intégré)
// ----------------------------------------------------------------------

function Section({
  title,
  path,
  offerId,
  value,
  onChange,
  children,
}: {
  title: string;
  path: string;
  offerId: number;
  value: string;
  onChange: (v: string) => void;
  children: ReactNode;
}) {
  return (
    <div className="p-4 border-b border-outline-variant space-y-3">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">{title}</div>
      {children}
      <AIBlockInput
        path={path}
        value={value}
        offerId={offerId}
        onApplied={(v) => onChange(v)}
      />
    </div>
  );
}

function AIBlockInput({
  path,
  value,
  offerId,
  onApplied,
  small,
}: {
  path: string;
  value: string;
  offerId: number;
  onApplied: (v: string) => void;
  small?: boolean;
}) {
  const [instr, setInstr] = useState("");
  const [busy, setBusy] = useState(false);
  const apply = async () => {
    if (!instr.trim()) return;
    setBusy(true);
    try {
      const r = await aiRewriteBlock(offerId, path, value, instr.trim());
      onApplied(r.value);
      setInstr("");
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={cn("flex gap-1.5", small && "mt-1")}>
      <input
        value={instr}
        onChange={(e) => setInstr(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") apply(); }}
        placeholder="✨ Demander à l'IA…"
        className={cn(
          "flex-1 text-xs border border-outline-variant rounded-md px-2.5 focus:border-tertiary outline-none",
          small ? "py-1" : "py-1.5"
        )}
      />
      <button
        onClick={apply}
        disabled={busy || !instr.trim()}
        className={cn(
          "px-2.5 rounded-md text-xs font-medium inline-flex items-center gap-1",
          busy || !instr.trim()
            ? "bg-surface-container text-on-surface-variant cursor-not-allowed"
            : "bg-navy text-white hover:bg-[#1d2841]"
        )}
      >
        {busy ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
      </button>
    </div>
  );
}

// ----------------------------------------------------------------------
// Overview (when nothing selected) + Sections Outline
// ----------------------------------------------------------------------

function Overview({
  structured,
  onSelect,
}: {
  structured: CVStructured;
  onSelect: (p: string) => void;
}) {
  const items: { label: string; path: string; sub: string }[] = [
    { label: "En-tête", path: "name", sub: structured.name ?? "—" },
    { label: "Titre adapté", path: "role", sub: structured.role ?? "—" },
    { label: "Intro", path: "intro", sub: structured.intro ? short(structured.intro, 60) : "—" },
    { label: "Contact", path: "contact", sub: contactSummary(structured) },
  ];
  return (
    <div className="p-4 space-y-2">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">Édition rapide</div>
      <div className="grid grid-cols-2 gap-1.5">
        {items.map((it) => (
          <button
            key={it.path}
            onClick={() => onSelect(it.path)}
            className="text-left px-3 py-2 rounded-md border border-outline-variant hover:border-outline hover:bg-surface-c group"
          >
            <div className="text-[11px] font-medium text-on-surface">{it.label}</div>
            <div className="text-[11px] text-on-surface-variant truncate group-hover:text-on-surface">{it.sub}</div>
          </button>
        ))}
      </div>
    </div>
  );
}

function SectionsOutline({
  structured,
  onSelect,
  onUpdateStructured,
}: {
  structured: CVStructured;
  onSelect: (p: string) => void;
  onUpdateStructured: (s: CVStructured) => void;
}) {
  const sections: { key: keyof CVStructured; label: string; count: number; emptyAllowed?: boolean }[] = [
    { key: "hard_skills", label: "Hard Skills", count: structured.hard_skills.length },
    { key: "soft_skills", label: "Soft Skills", count: structured.soft_skills.length },
    { key: "tools", label: "Stack & Outils", count: structured.tools.length },
    { key: "languages", label: "Langues", count: structured.languages.length },
    { key: "formations", label: "Formations", count: structured.formations.length },
    { key: "experiences", label: "Expériences", count: structured.experiences.length },
    { key: "projects_pedagogical", label: "Projets pédago.", count: structured.projects_pedagogical.length },
    { key: "projects_personal", label: "Projets perso.", count: structured.projects_personal.length },
  ];
  const toggleHide = (key: keyof CVStructured) => {
    const v = (structured as any)[key];
    if (Array.isArray(v) && v.length > 0) {
      // Préfixe avec _hidden_<key> dans un champ caché (pas implémenté pour l'instant)
      // → on vide la liste mais on stocke ailleurs ? Trop complexe pour ce sprint.
      // Pour l'instant : on ne supporte pas vraiment le masquage transparent.
      // Stub : on rien fait pour le moment, à raffiner.
    }
  };
  void toggleHide;
  return (
    <div className="p-4 border-t border-outline-variant bg-surface-container-low">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium mb-2">Sections</div>
      <div className="space-y-0.5">
        {sections.map((s) => (
          <button
            key={s.key as string}
            onClick={() => onSelect(s.key as string)}
            className="w-full flex items-center justify-between px-2 py-1.5 rounded text-xs hover:bg-surface-highest"
          >
            <span className="text-on-surface">{s.label}</span>
            <span className="text-on-surface-variant tabular-nums">{s.count}</span>
          </button>
        ))}
      </div>
      <button
        onClick={() => {
          // Réordonne : on inverse projets_pedagogical et projects_personal (toggle simple)
          const next = { ...structured };
          const a = next.projects_pedagogical;
          next.projects_pedagogical = next.projects_personal;
          next.projects_personal = a;
          onUpdateStructured(next);
        }}
        className="mt-2 w-full text-[11px] text-on-surface-variant hover:text-on-surface inline-flex items-center justify-center gap-1 py-1"
        title="Inverser l'ordre des deux blocs de projets"
      >
        <ChevronUp size={10} /><ChevronDown size={10} /> Inverser pédago / perso
      </button>
    </div>
  );
}

function contactSummary(s: CVStructured): string {
  const bits = [s.contact.email, s.contact.phone, s.contact.linkedin, s.contact.location].filter(Boolean);
  return bits.join(" · ") || "—";
}

function short(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

// ----------------------------------------------------------------------
// Champs primitifs
// ----------------------------------------------------------------------

function FieldInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full text-sm border border-outline-variant rounded-md px-2.5 py-1.5 focus:border-tertiary outline-none"
    />
  );
}

function FieldTextarea({
  value,
  onChange,
  rows = 3,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  placeholder?: string;
}) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={rows}
      placeholder={placeholder}
      className="w-full text-sm border border-outline-variant rounded-md px-2.5 py-1.5 leading-snug resize-y focus:border-tertiary outline-none"
    />
  );
}

function QualityHint({
  value,
  target,
}: {
  value: string;
  target: { min: number; max: number; unit: "mots" | "chars" };
}) {
  const count =
    target.unit === "mots"
      ? value.trim().split(/\s+/).filter(Boolean).length
      : value.length;
  const ok = count >= target.min && count <= target.max;
  const short = count < target.min;
  const tone = ok ? "text-secondary" : short ? "text-secondary" : "text-on-error-container";
  const label = ok
    ? "longueur OK"
    : short
      ? `un peu court (cible ${target.min}-${target.max})`
      : `trop long (cible ${target.min}-${target.max})`;
  return (
    <div className={cn("text-[11px] flex items-center gap-1.5", tone)}>
      <span className="tabular-nums">{count}</span>
      <span>{target.unit}</span>
      <span className="opacity-70">·</span>
      <span>{label}</span>
    </div>
  );
}

// ----------------------------------------------------------------------
// Contact
// ----------------------------------------------------------------------

function ContactEditor({
  struct,
  onUpdate,
}: {
  struct: CVStructured;
  onUpdate: (mut: (s: CVStructured) => CVStructured) => void;
}) {
  const setField = (key: keyof CVStructured["contact"]) => (v: string) =>
    onUpdate((s) => ({ ...s, contact: { ...s.contact, [key]: v || null } }));
  return (
    <div className="p-4 space-y-2.5 border-b border-outline-variant">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">Contact</div>
      <div className="grid grid-cols-2 gap-2">
        <FieldInput value={struct.contact.email ?? ""} onChange={setField("email")} placeholder="Email" />
        <FieldInput value={struct.contact.phone ?? ""} onChange={setField("phone")} placeholder="Téléphone" />
      </div>
      <FieldInput value={struct.contact.linkedin ?? ""} onChange={setField("linkedin")} placeholder="LinkedIn" />
      <FieldInput value={struct.contact.location ?? ""} onChange={setField("location")} placeholder="Localisation" />
    </div>
  );
}

// ----------------------------------------------------------------------
// Listes triables — strings
// ----------------------------------------------------------------------

function SortableStringList({
  label,
  values,
  onChange,
  max,
  id,
  placeholder,
}: {
  label: string;
  values: string[];
  onChange: (v: string[]) => void;
  max?: number;
  id: string;
  placeholder?: string;
}) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));
  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIdx = Number(String(active.id).split(":")[1]);
    const newIdx = Number(String(over.id).split(":")[1]);
    onChange(arrayMove(values, oldIdx, newIdx));
  };
  const items = values.map((_, i) => `${id}:${i}`);
  const canAdd = !max || values.length < max;
  return (
    <div className="p-4 space-y-2 border-b border-outline-variant">
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">{label}</div>
        {max && <span className="text-[10px] text-on-surface-variant">{values.length}/{max}</span>}
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items} strategy={verticalListSortingStrategy}>
          <div className="space-y-1">
            {values.map((v, i) => (
              <SortableStringRow
                key={items[i]}
                id={items[i]}
                value={v}
                onChange={(x) => onChange(values.map((vv, j) => (j === i ? x : vv)))}
                onRemove={() => onChange(values.filter((_, j) => j !== i))}
                placeholder={placeholder}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      {canAdd && (
        <button
          onClick={() => onChange([...values, ""])}
          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-dashed border-outline-variant hover:border-outline text-on-surface-variant"
        >
          <Plus size={11} /> Ajouter
        </button>
      )}
    </div>
  );
}

function SortableStringRow({
  id,
  value,
  onChange,
  onRemove,
  placeholder,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  onRemove: () => void;
  placeholder?: string;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  return (
    <div ref={setNodeRef} style={style} className="flex items-center gap-1.5 group">
      <button {...attributes} {...listeners} className="text-on-surface-variant group-hover:text-on-surface-variant cursor-grab touch-none">
        <GripVertical size={13} />
      </button>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="flex-1 text-sm border border-outline-variant rounded-md px-2 py-1 focus:border-tertiary outline-none"
      />
      <button onClick={onRemove} className="text-on-surface-variant group-hover:text-on-error-container">
        <Trash2 size={13} />
      </button>
    </div>
  );
}

// ----------------------------------------------------------------------
// Langues / formations / projets — réutilisés du précédent
// ----------------------------------------------------------------------

function LanguageEditor({ values, onChange }: { values: CVLanguage[]; onChange: (v: CVLanguage[]) => void }) {
  return (
    <div className="p-4 space-y-2 border-b border-outline-variant">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">Langues</div>
      {values.map((l, i) => (
        <div key={i} className="flex gap-1.5 group">
          <input type="text" value={l.name} onChange={(e) => onChange(values.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
            placeholder="Français" className="flex-1 text-sm border border-outline-variant rounded-md px-2 py-1" />
          <input type="text" value={l.level ?? ""} onChange={(e) => onChange(values.map((x, j) => (j === i ? { ...x, level: e.target.value || null } : x)))}
            placeholder="C1" className="w-20 text-sm border border-outline-variant rounded-md px-2 py-1" />
          <button onClick={() => onChange(values.filter((_, j) => j !== i))} className="text-on-surface-variant group-hover:text-on-error-container"><Trash2 size={13} /></button>
        </div>
      ))}
      <button onClick={() => onChange([...values, { name: "", level: null }])} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-dashed border-outline-variant hover:border-outline text-on-surface-variant">
        <Plus size={11} /> Ajouter
      </button>
    </div>
  );
}

function FormationListEditor({ values, onChange }: { values: CVFormation[]; onChange: (v: CVFormation[]) => void }) {
  return (
    <div className="p-4 space-y-2 border-b border-outline-variant">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">Formations</div>
      {values.map((f, i) => (
        <div key={i} className="border border-outline-variant rounded-md p-2 space-y-1 group">
          <input type="text" value={f.degree} onChange={(e) => onChange(values.map((x, j) => (j === i ? { ...x, degree: e.target.value } : x)))}
            placeholder="Diplôme" className="w-full text-sm font-medium border-none focus:outline-none bg-transparent" />
          <input type="text" value={f.school} onChange={(e) => onChange(values.map((x, j) => (j === i ? { ...x, school: e.target.value } : x)))}
            placeholder="École" className="w-full text-sm border-none focus:outline-none bg-transparent" />
          <div className="flex items-center justify-between">
            <input type="text" value={f.period} onChange={(e) => onChange(values.map((x, j) => (j === i ? { ...x, period: e.target.value } : x)))}
              placeholder="2023 — 2026" className="flex-1 text-xs text-on-surface-variant italic border-none focus:outline-none bg-transparent" />
            <button onClick={() => onChange(values.filter((_, j) => j !== i))} className="text-on-surface-variant group-hover:text-on-error-container"><Trash2 size={13} /></button>
          </div>
        </div>
      ))}
      <button onClick={() => onChange([...values, { degree: "", school: "", period: "" }])} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-dashed border-outline-variant hover:border-outline text-on-surface-variant">
        <Plus size={11} /> Ajouter
      </button>
    </div>
  );
}

function FormationEditor({ index, values, onChange }: { index: number; values: CVFormation[]; onChange: (v: CVFormation[]) => void }) {
  const f = values[index];
  if (!f) return <div className="p-4 text-xs text-on-surface-variant">Formation introuvable</div>;
  const setAt = (patch: Partial<CVFormation>) => onChange(values.map((x, j) => (j === index ? { ...x, ...patch } : x)));
  return (
    <div className="p-4 space-y-2 border-b border-outline-variant">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">Formation</div>
      <FieldInput value={f.degree} onChange={(v) => setAt({ degree: v })} placeholder="Diplôme" />
      <FieldInput value={f.school} onChange={(v) => setAt({ school: v })} placeholder="École" />
      <FieldInput value={f.period} onChange={(v) => setAt({ period: v })} placeholder="2023 — 2026" />
    </div>
  );
}

// ----------------------------------------------------------------------
// Expériences
// ----------------------------------------------------------------------

function ExperienceListEditor({
  values,
  onChange,
  onSelect,
}: {
  values: CVExperience[];
  onChange: (v: CVExperience[]) => void;
  onSelect: (p: string) => void;
}) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));
  const items = values.map((_, i) => `exp:${i}`);
  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const a = Number(String(active.id).split(":")[1]);
    const b = Number(String(over.id).split(":")[1]);
    onChange(arrayMove(values, a, b));
  };
  return (
    <div className="p-4 space-y-2 border-b border-outline-variant">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">Expériences pro</div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items} strategy={verticalListSortingStrategy}>
          <div className="space-y-1.5">
            {values.map((e, i) => (
              <SortableExpRow key={items[i]} id={items[i]} exp={e}
                onClick={() => onSelect(`experiences.${i}`)}
                onRemove={() => onChange(values.filter((_, j) => j !== i))}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      <button onClick={() => onChange([...values, { company: "", role: "", period: "", bullets: [] }])}
        className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-dashed border-outline-variant hover:border-outline text-on-surface-variant">
        <Plus size={11} /> Ajouter une expérience
      </button>
    </div>
  );
}

function SortableExpRow({ id, exp, onClick, onRemove }: { id: string; exp: CVExperience; onClick: () => void; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  return (
    <div ref={setNodeRef} style={style} className="flex items-center gap-1.5 group">
      <button {...attributes} {...listeners} className="text-on-surface-variant group-hover:text-on-surface-variant cursor-grab touch-none">
        <GripVertical size={13} />
      </button>
      <button onClick={onClick} className="flex-1 text-left px-2 py-1.5 rounded-md border border-outline-variant hover:border-outline hover:bg-surface-c">
        <div className="text-xs font-medium truncate">{exp.role || "Poste"} · {exp.company || "—"}</div>
        <div className="text-[10px] text-on-surface-variant truncate">{exp.period || "—"} · {exp.bullets.length} bullets</div>
      </button>
      <button onClick={onRemove} className="text-on-surface-variant group-hover:text-on-error-container"><Trash2 size={13} /></button>
    </div>
  );
}

function ExperienceEditor({
  segs,
  values,
  onChange,
  offerId,
  onSelect,
}: {
  segs: string[];
  values: CVExperience[];
  onChange: (v: CVExperience[]) => void;
  offerId: number;
  onSelect: (p: string) => void;
}) {
  const expIdx = Number(segs[1]);
  const exp = values[expIdx];
  if (!exp) return <div className="p-4 text-xs text-on-surface-variant">Expérience introuvable</div>;
  const setExp = (patch: Partial<CVExperience>) =>
    onChange(values.map((x, j) => (j === expIdx ? { ...x, ...patch } : x)));
  const bulletIdx = segs[2] === "bullets" && segs[3] != null ? Number(segs[3]) : null;
  return (
    <div className="p-4 space-y-3 border-b border-outline-variant">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">Expérience</div>
      <FieldInput value={exp.company} onChange={(v) => setExp({ company: v })} placeholder="Entreprise" />
      <FieldInput value={exp.role} onChange={(v) => setExp({ role: v })} placeholder="Poste" />
      <FieldInput value={exp.period} onChange={(v) => setExp({ period: v })} placeholder="Période" />
      <BulletsEditor
        bullets={exp.bullets}
        onChange={(v) => setExp({ bullets: v })}
        offerId={offerId}
        expIdx={expIdx}
        focusIndex={bulletIdx}
        onFocusBullet={(j) => onSelect(`experiences.${expIdx}.bullets.${j}`)}
        onClearBulletFocus={() => onSelect(`experiences.${expIdx}`)}
      />
    </div>
  );
}

function BulletsEditor({
  bullets,
  onChange,
  offerId,
  expIdx,
  focusIndex,
  onFocusBullet,
  onClearBulletFocus,
}: {
  bullets: string[];
  onChange: (v: string[]) => void;
  offerId: number;
  expIdx: number;
  focusIndex: number | null;
  onFocusBullet: (i: number) => void;
  onClearBulletFocus: () => void;
}) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));
  const items = bullets.map((_, i) => `b:${i}`);
  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const a = Number(String(active.id).split(":")[1]);
    const b = Number(String(over.id).split(":")[1]);
    onChange(arrayMove(bullets, a, b));
  };
  const [aiBusy, setAiBusy] = useState<number | null>(null);
  const apply = async (i: number, instruction: string) => {
    setAiBusy(i);
    try {
      const r = await aiRewriteBullet(offerId, bullets[i], instruction);
      onChange(bullets.map((b, j) => (j === i ? r.bullet : b)));
    } catch (e) { console.error(e); }
    finally { setAiBusy(null); }
  };
  return (
    <div>
      <div className="text-[11px] text-on-surface-variant mb-1.5 flex items-center justify-between">
        <span>Bullets</span>
        {focusIndex !== null && (
          <button onClick={onClearBulletFocus} className="text-[10px] text-on-surface-variant hover:text-on-surface">← retour expérience</button>
        )}
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items} strategy={verticalListSortingStrategy}>
          <div className="space-y-1.5">
            {bullets.map((b, i) => (
              <SortableBulletRow
                key={items[i]}
                id={items[i]}
                value={b}
                focused={focusIndex === i}
                onChange={(v) => onChange(bullets.map((x, j) => (j === i ? v : x)))}
                onRemove={() => onChange(bullets.filter((_, j) => j !== i))}
                onFocus={() => onFocusBullet(i)}
                onAI={(instr) => apply(i, instr)}
                aiBusy={aiBusy === i}
                offerId={offerId}
                path={`experiences.${expIdx}.bullets.${i}`}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      <button onClick={() => onChange([...bullets, ""])}
        className="mt-1.5 inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-dashed border-outline-variant hover:border-outline text-on-surface-variant">
        <Plus size={11} /> Ajouter
      </button>
    </div>
  );
}

function SortableBulletRow({
  id,
  value,
  focused,
  onChange,
  onRemove,
  onFocus,
  onAI,
  aiBusy,
  offerId,
  path,
}: {
  id: string;
  value: string;
  focused: boolean;
  onChange: (v: string) => void;
  onRemove: () => void;
  onFocus: () => void;
  onAI: (instr: string) => void;
  aiBusy: boolean;
  offerId: number;
  path: string;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  const wordCount = value.trim().split(/\s+/).filter(Boolean).length;
  const tooLong = wordCount > 22;
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn("border rounded-md p-1.5 group", focused ? "border-navy" : "border-outline-variant")}
    >
      <div className="flex items-start gap-1.5">
        <button {...attributes} {...listeners} className="text-on-surface-variant group-hover:text-on-surface-variant cursor-grab touch-none mt-1">
          <GripVertical size={13} />
        </button>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={onFocus}
          rows={2}
          className="flex-1 text-sm border-none focus:outline-none resize-y leading-snug bg-transparent"
        />
        <button onClick={onRemove} className="text-on-surface-variant group-hover:text-on-error-container mt-1"><Trash2 size={13} /></button>
      </div>
      <div className="flex items-center justify-between pl-5 mt-0.5">
        <div className="flex gap-1">
          <AIChip busy={aiBusy} onClick={() => onAI("Reformule pour mieux coller à l'offre.")}>Offre</AIChip>
          <AIChip busy={aiBusy} onClick={() => onAI("Rends-le plus court (≤ 14 mots).")}>Court</AIChip>
          <AIChip busy={aiBusy} onClick={() => onAI("Renforce l'impact : verbe d'action en premier, résultat mesurable.")}>Impact</AIChip>
        </div>
        <span className={cn("text-[10px] tabular-nums", tooLong ? "text-secondary" : "text-on-surface-variant")}>
          {wordCount}m
        </span>
      </div>
      {focused && (
        <div className="mt-1.5 pl-5">
          <AIBlockInput path={path} value={value} offerId={offerId} onApplied={(v) => onChange(v)} small />
        </div>
      )}
    </div>
  );
}

function AIChip({ busy, onClick, children }: { busy: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className={cn(
        "inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border",
        busy ? "bg-surface-container text-on-surface-variant border-outline-variant" : "bg-surface-container-low text-on-surface border-outline-variant hover:border-outline"
      )}
    >
      {busy ? <Loader2 size={9} className="animate-spin" /> : <Sparkles size={9} />}
      {children}
    </button>
  );
}

// ----------------------------------------------------------------------
// Projets
// ----------------------------------------------------------------------

function ProjectListEditor({
  label,
  values,
  onChange,
}: {
  label: string;
  values: CVProject[];
  onChange: (v: CVProject[]) => void;
}) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));
  const items = values.map((_, i) => `proj:${i}`);
  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const a = Number(String(active.id).split(":")[1]);
    const b = Number(String(over.id).split(":")[1]);
    onChange(arrayMove(values, a, b));
  };
  return (
    <div className="p-4 space-y-2 border-b border-outline-variant">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">{label}</div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items} strategy={verticalListSortingStrategy}>
          <div className="space-y-1.5">
            {values.map((p, i) => (
              <SortableProjectRow key={items[i]} id={items[i]} project={p}
                onChange={(np) => onChange(values.map((x, j) => (j === i ? np : x)))}
                onRemove={() => onChange(values.filter((_, j) => j !== i))}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
      <button onClick={() => onChange([...values, { name: "", summary: "" }])}
        className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md border border-dashed border-outline-variant hover:border-outline text-on-surface-variant">
        <Plus size={11} /> Ajouter
      </button>
    </div>
  );
}

function SortableProjectRow({ id, project, onChange, onRemove }: { id: string; project: CVProject; onChange: (p: CVProject) => void; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  return (
    <div ref={setNodeRef} style={style} className="border border-outline-variant rounded-md p-2 space-y-1.5 group">
      <div className="flex items-center gap-1.5">
        <button {...attributes} {...listeners} className="text-on-surface-variant group-hover:text-on-surface-variant cursor-grab touch-none"><GripVertical size={13} /></button>
        <input type="text" value={project.name} onChange={(e) => onChange({ ...project, name: e.target.value })}
          placeholder="Nom" className="flex-1 text-sm font-medium border-none focus:outline-none bg-transparent" />
        <button onClick={onRemove} className="text-on-surface-variant group-hover:text-on-error-container"><Trash2 size={13} /></button>
      </div>
      <textarea value={project.summary} onChange={(e) => onChange({ ...project, summary: e.target.value })}
        rows={2} placeholder="Description courte"
        className="w-full text-sm border-none focus:outline-none resize-y bg-transparent leading-snug" />
    </div>
  );
}

function ProjectEditor({ index, values, onChange }: { index: number; values: CVProject[]; onChange: (v: CVProject[]) => void }) {
  const p = values[index];
  if (!p) return <div className="p-4 text-xs text-on-surface-variant">Projet introuvable</div>;
  const setAt = (patch: Partial<CVProject>) => onChange(values.map((x, j) => (j === index ? { ...x, ...patch } : x)));
  return (
    <div className="p-4 space-y-2 border-b border-outline-variant">
      <div className="text-[11px] uppercase tracking-wide text-on-surface-variant font-medium">Projet</div>
      <FieldInput value={p.name} onChange={(v) => setAt({ name: v })} placeholder="Nom" />
      <FieldTextarea value={p.summary} onChange={(v) => setAt({ summary: v })} rows={3} placeholder="Description" />
    </div>
  );
}


// ----------------------------------------------------------------------
// Inspirations modal — galerie scraped + clone Vision
// ----------------------------------------------------------------------

function InspirationsModal({
  onApply,
  onClose,
}: {
  currentStyle: CVStyle;
  onApply: (style: Partial<CVStyle>) => void;
  onClose: () => void;
}) {
  const [items, setItems] = useState<CVInspiration[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewStyle, setPreviewStyle] = useState<(Partial<CVStyle> & { notes?: string }) | null>(null);

  useEffect(() => {
    listCVInspirations(72)
      .then((r) => setItems(r.items))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const handleClone = async (url: string) => {
    setBusy(url);
    setError(null);
    try {
      const r = await cloneStyleFromImage(url);
      setPreviewStyle(r.style);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-stretch justify-end" onClick={onClose}>
      <div
        className="bg-surface-lowest w-[680px] max-w-full h-full overflow-hidden flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-3 border-b border-outline-variant flex items-center gap-2">
          <ImageIcon size={16} className="text-on-surface-variant" />
          <div className="font-semibold text-sm">Inspirations de design</div>
          <span className="text-[11px] text-on-surface-variant">scraped depuis enhancv & novoresume · clone via Vision</span>
          <button onClick={onClose} className="ml-auto text-on-surface-variant hover:text-on-surface" title="Fermer (Esc)">
            <X size={16} />
          </button>
        </div>

        {previewStyle && (
          <div className="px-5 py-3 border-b border-tertiary bg-tertiary-container flex items-center gap-3">
            <Wand2 size={14} className="text-tertiary shrink-0" />
            <div className="flex-1 text-xs text-on-tertiary-container">
              <div className="font-semibold">Style détecté</div>
              <div>
                Template <strong>{previewStyle.template}</strong> · Accent
                <span
                  className="inline-block w-2.5 h-2.5 rounded-full mx-1 align-middle border border-tertiary"
                  style={{ background: previewStyle.accent_color }}
                />
                {previewStyle.accent_color} · Police {previewStyle.font} · Densité {previewStyle.density?.toFixed(2)}
                {previewStyle.notes && (
                  <span className="block text-tertiary mt-0.5">{previewStyle.notes}</span>
                )}
              </div>
            </div>
            <button
              onClick={() => onApply({
                template: previewStyle.template,
                accent_color: previewStyle.accent_color,
                font: previewStyle.font,
                density: previewStyle.density,
                photo_enabled: previewStyle.photo_enabled,
              } as Partial<CVStyle>)}
              className="px-3 py-1.5 rounded-md bg-tertiary text-white text-xs font-semibold hover:brightness-110"
            >
              Appliquer
            </button>
            <button
              onClick={() => setPreviewStyle(null)}
              className="px-2 py-1.5 rounded-md border border-tertiary text-on-tertiary-container text-xs hover:bg-tertiary-container"
            >
              Reset
            </button>
          </div>
        )}

        <div className="flex-1 overflow-auto p-4">
          {error && <div className="text-xs text-on-error-container mb-2">{error}</div>}
          {items === null ? (
            <div className="flex items-center justify-center gap-2 text-sm text-on-surface-variant py-12">
              <Loader2 size={14} className="animate-spin" /> Chargement de la galerie…
            </div>
          ) : items.length === 0 ? (
            <div className="text-sm text-on-surface-variant text-center py-12">Pas d'inspirations disponibles.</div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {items.map((it) => {
                const isBusy = busy === it.url;
                return (
                  <div
                    key={it.url}
                    className="relative group rounded-md overflow-hidden border border-outline-variant bg-surface-container-low"
                  >
                    <img
                      src={it.url}
                      alt={it.title || "inspiration CV"}
                      className="w-full h-auto block"
                      loading="lazy"
                    />
                    <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-between gap-2">
                      <span className="text-[10px] text-white/80 uppercase tracking-wide">{it.source}</span>
                      <button
                        onClick={() => handleClone(it.url)}
                        disabled={isBusy}
                        className={cn(
                          "text-[11px] font-medium px-2 py-1 rounded inline-flex items-center gap-1",
                          isBusy
                            ? "bg-surface-lowest text-white cursor-not-allowed"
                            : "bg-surface-lowest text-on-surface hover:bg-surface-container"
                        )}
                      >
                        {isBusy ? <Loader2 size={11} className="animate-spin" /> : <Wand2 size={11} />}
                        Cloner
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
        <div className="px-5 py-2 border-t border-outline-variant text-[11px] text-on-surface-variant">
          Le clone n'extrait que le style (template, couleur, police, densité). Le contenu de ton CV reste intact.
        </div>
      </div>
    </div>
  );
}
