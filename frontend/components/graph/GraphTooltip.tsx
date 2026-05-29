import type { GraphNode } from './graphTypes';

interface GraphTooltipProps {
  node: GraphNode | null;
  position: { x: number; y: number };
}

export function GraphTooltip({ node, position }: GraphTooltipProps) {
  if (!node) return null;

  const isCompany = node.type === 'company';

  return (
    <div
      className="absolute pointer-events-none z-50 rounded-xl shadow-xl border
        bg-white/95 dark:bg-gray-800/95 border-gray-200 dark:border-gray-700
        backdrop-blur-sm text-sm max-w-xs overflow-hidden"
      style={{
        left: position.x + 14,
        top: position.y - 14,
      }}
    >
      <div className={`px-3 py-2 flex items-center gap-2.5 ${
        isCompany
          ? 'bg-blue-50 dark:bg-blue-900/30 border-b border-blue-100 dark:border-blue-800/40'
          : 'bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700/40'
      }`}>
        <div className={`w-6 h-6 rounded-full flex items-center justify-center ${
          isCompany ? 'bg-blue-600' : 'bg-slate-600 dark:bg-slate-500'
        }`}>
          <i className={`fas ${isCompany ? 'fa-building' : 'fa-user'} text-white text-[9px]`} />
        </div>
        <span className="font-semibold text-gray-900 dark:text-gray-100">
          {node.label}
        </span>
      </div>
      <div className="px-3 py-1.5">
        {isCompany && (
          <div className="text-gray-500 dark:text-gray-400 text-xs space-y-0.5">
            <div>IČO: <span className="font-mono font-medium text-gray-700 dark:text-gray-300">{node.ico}</span></div>
            <div>Status: <span className="font-medium text-gray-700 dark:text-gray-300">{node.status}</span></div>
            <div className="text-blue-600 dark:text-blue-400 pt-1 font-medium">
              <i className="fas fa-expand-alt mr-1 text-[9px]" />Klikni pre rozbalenie
            </div>
          </div>
        )}
        {node.type === 'person' && (
          <div className="text-gray-500 dark:text-gray-400 text-xs space-y-0.5">
            {node.rolesCount && node.rolesCount > 1 && (
              <div>
                <i className="fas fa-briefcase mr-1 text-[9px]" />
                Pôsobí v {node.rolesCount} {node.rolesCount < 5 ? 'firmách' : 'firmách'}
              </div>
            )}
            <div className="text-blue-600 dark:text-blue-400 pt-0.5 font-medium">
              <i className="fas fa-expand-alt mr-1 text-[9px]" />Klikni pre zobrazenie firiem
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
