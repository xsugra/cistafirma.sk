interface GraphControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  nodeCount: number;
  truncated: boolean;
}

export function GraphControls({ onZoomIn, onZoomOut, onReset, nodeCount, truncated }: GraphControlsProps) {
  return (
    <div className="flex items-center gap-2 text-sm pointer-events-auto">
      <div className="flex items-center gap-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm">
        <button
          onClick={onZoomIn}
          className="px-2.5 py-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-l-lg transition-colors"
          title="Priblížiť"
        >
          +
        </button>
        <button
          onClick={onZoomOut}
          className="px-2.5 py-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          title="Oddialiť"
        >
          −
        </button>
        <button
          onClick={onReset}
          className="px-2.5 py-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-r-lg transition-colors"
          title="Reset pohľadu"
        >
          ⟲
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
