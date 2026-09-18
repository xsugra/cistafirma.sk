interface GraphControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onExportPng: () => void;
  onToggleFullscreen: () => void;
  isFullscreen: boolean;
  nodeCount: number;
  truncated: boolean;
}

export function GraphControls({
  onZoomIn,
  onZoomOut,
  onReset,
  onExportPng,
  onToggleFullscreen,
  isFullscreen,
  nodeCount,
  truncated,
}: GraphControlsProps) {
  // Measured before this: the text buttons were 28-30 x 32 and the two SVG ones
  // 34 x 26 -- so the icon buttons did not fill the 32 px pill they sit in (their
  // hover background stopped short of its edges) and nothing here was close to a
  // thumb-sized target on a phone. `items-center justify-center` plus a minimum
  // box makes all five the same square, and the box is the tap target rather than
  // the glyph. 44 px below `md` is Apple's minimum; at `md` and up a pointer is
  // precise and the control strip keeps the compact size it had.
  const btnBase =
    'flex items-center justify-center min-h-11 min-w-11 md:min-h-8 md:min-w-8 px-2.5 py-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors';

  return (
    <div className="flex items-center gap-2 text-sm pointer-events-auto">
      <div className="flex items-center rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
        <button onClick={onZoomIn} className={`${btnBase} rounded-l-lg`} title="Priblížiť">
          +
        </button>
        <button onClick={onZoomOut} className={btnBase} title="Oddialiť">
          −
        </button>
        <button onClick={onReset} className={btnBase} title="Reset pohľadu">
          ⟲
        </button>
        <button onClick={onExportPng} className={btnBase} title="Exportovať PNG">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M8 2v8M5 7l3 3 3-3M3 12h10M3 14h10" />
          </svg>
        </button>
        <button
          onClick={onToggleFullscreen}
          className={`${btnBase} rounded-r-lg ${
            isFullscreen
              ? 'bg-red-50 hover:bg-red-100 text-red-600 dark:bg-red-900/30 dark:hover:bg-red-900/50 dark:text-red-400'
              : ''
          }`}
          title={isFullscreen ? 'Zavrieť (Esc)' : 'Celá obrazovka'}
        >
          {isFullscreen ? (
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M3 3l10 10M13 3L3 13" />
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M2 5V2h3M11 2h3v3M14 11v3h-3M5 14H2v-3" />
            </svg>
          )}
        </button>
      </div>
      <span className="text-gray-500 dark:text-gray-400 ml-2">
        {nodeCount} uzlov
      </span>
      {truncated && (
        <span className="text-amber-600 dark:text-amber-400 text-xs">
          (graf orezaný)
        </span>
      )}
    </div>
  );
}
