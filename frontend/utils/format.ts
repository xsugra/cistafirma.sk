export const formatCurrency = (value: number): string => {
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M €`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(0)}k €`;
    return `${value.toLocaleString('sk-SK')} €`;
};

export const formatFullCurrency = (value: number): string =>
    value.toLocaleString('sk-SK', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
