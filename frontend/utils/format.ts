const NBSP = '\u00A0'

export const formatNumber = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '';
    try {
        // Use Intl.NumberFormat for locale-aware grouping, then replace normal spaces with NBSP
        const s = new Intl.NumberFormat('sk-SK', { maximumFractionDigits: 0 }).format(Math.round(value));
        return s.replace(/\u00A0| /g, NBSP);
    } catch (e) {
        return String(value);
    }
};

export const formatCurrency = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return '';
    return `${formatNumber(value)}${NBSP}€`;
};

export const formatFullCurrency = (value: number | null | undefined): string => {
    return formatCurrency(value);
};
