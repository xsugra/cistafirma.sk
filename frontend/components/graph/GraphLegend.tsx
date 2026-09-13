const LEGEND_ITEMS = [
  { label: 'Firma', color: 'bg-blue-600', icon: 'fa-building', shape: 'rounded-full' },
  { label: 'Osoba', color: 'bg-slate-600 dark:bg-slate-500', icon: 'fa-user', shape: 'rounded-full' },
];

const ROLE_COLORS: [string, string][] = [
  ['Konateľ', 'bg-blue-500'],
  ['Spoločník', 'bg-sky-500'],
  ['Prokurista', 'bg-blue-400'],
  ['Predst.', 'bg-slate-500'],
  ['Doz. rada', 'bg-gray-400'],
];

export function GraphLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-gray-600 dark:text-gray-400 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm rounded-lg px-3 py-2 border border-gray-200/50 dark:border-gray-700/50">
      {LEGEND_ITEMS.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <div className={`w-5 h-5 ${item.shape} ${item.color} flex items-center justify-center`}>
            <i className={`fas ${item.icon} text-white text-[8px]`} />
          </div>
          <span>{item.label}</span>
        </div>
      ))}
      <div className="w-px h-4 bg-gray-300 dark:bg-gray-600 mx-1" />
      {ROLE_COLORS.map(([label, color]) => (
        <div key={label} className="flex items-center gap-1.5">
          <div className={`w-3.5 h-0.5 ${color} rounded-full`} />
          <span>{label}</span>
        </div>
      ))}
      <div className="flex items-center gap-1.5">
        <div className="w-3.5 h-0.5 border-t border-dashed border-gray-400" />
        <span>Ukončené</span>
      </div>
      <div className="flex items-center gap-1.5">
        <div className="w-3.5 h-0.5 border-t border-dotted border-gray-400 dark:border-gray-500" />
        <span title="Funkciu sme pre túto firmu ešte neoverili v registri">
          Neznáme
        </span>
      </div>
    </div>
  );
}
