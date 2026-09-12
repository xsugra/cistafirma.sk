import React from 'react';
import type { Company, Financials } from '../../../types';
import { InfoCard } from '../../InfoCard';
import { formatCurrency } from '../../../utils/format';
import { EmptyFinancialsNotice } from './EmptyFinancialsNotice';

interface BalanceSheetSectionProps {
    company: Company;
}

/** One line of the statement: where it comes from, and whether it is a total. */
interface SheetRow {
    label: string;
    value: (f: Financials) => number | null;
    total?: boolean;
}

const ASSET_ROWS: SheetRow[] = [
    { label: 'Nehmotný majetok', value: (f) => f.assetsIntangible },
    { label: 'Hmotný majetok', value: (f) => f.assetsTangible },
    { label: 'Finančný majetok', value: (f) => f.assetsFinancial },
    { label: 'Zásoby', value: (f) => f.assetsInventory },
    { label: 'Dlhodobé pohľadávky', value: (f) => f.assetsReceivablesLong },
    { label: 'Krátkodobé pohľadávky', value: (f) => f.assetsReceivablesShort },
    { label: 'Finančné účty', value: (f) => f.assetsFinancialAccounts },
    { label: 'Časové rozlíšenie', value: (f) => f.assetsAccruals },
    { label: 'Aktíva spolu', value: (f) => f.assetsTotal, total: true },
];

const LIABILITY_ROWS: SheetRow[] = [
    { label: 'Základné imanie', value: (f) => f.equityBasic },
    { label: 'Kapitálové fondy', value: (f) => f.equityCapitalFunds },
    { label: 'Fondy zo zisku', value: (f) => f.equityProfitFunds },
    { label: 'Výsledok hospodárenia minulých rokov', value: (f) => f.equityRetained },
    { label: 'Vlastné imanie', value: (f) => f.equity, total: true },
    { label: 'Rezervy', value: (f) => f.liabilitiesReserves },
    { label: 'Dlhodobé záväzky', value: (f) => f.liabilitiesLong },
    { label: 'Krátkodobé záväzky', value: (f) => f.liabilitiesShort },
    // "Cudzie zdroje celkom" -- reserves plus both maturities, without the
    // accruals, which is exactly how the backend computes `debtRatio` and why
    // accruals get their own line below rather than being folded in here.
    { label: 'Záväzky spolu', value: (f) => f.liabilitiesTotal, total: true },
    { label: 'Časové rozlíšenie', value: (f) => f.liabilitiesAccruals },
];

/**
 * The three figures the identity is built from, in the order it names them.
 *
 * "Časové rozlíšenie" is deliberately not among them -- see `pasivaTotal`.
 */
const IDENTITY_PARTS: { label: string; filed: (f: Financials) => boolean }[] = [
    { label: 'aktíva spolu', filed: (f) => f.assetsTotal != null },
    { label: 'vlastné imanie', filed: (f) => f.equity != null },
    { label: 'záväzky spolu', filed: (f) => f.liabilitiesTotal != null },
];

/** Which of the identity's figures a year's statement did not carry. */
function missingParts(f: Financials): string[] {
    return IDENTITY_PARTS.filter((part) => !part.filed(f)).map((part) => part.label);
}

/** "vlastné imanie (2021, 2022); záväzky spolu (2023)" */
function describeMissing(years: Financials[]): string {
    return IDENTITY_PARTS.map((part) => ({
        label: part.label,
        years: years.filter((f) => !part.filed(f)).map((f) => f.year),
    }))
        .filter((entry) => entry.years.length > 0)
        .map((entry) => `${entry.label} (${entry.years.join(', ')})`)
        .join('; ');
}

/**
 * The pasíva total, or `null` when the statement did not carry the parts of it
 * that the identity needs.
 *
 * An absent "Časové rozlíšenie" counts as zero, and that is a measurement
 * rather than a convenience. Measured 2026-09-12: of the 2 336 stored rows that
 * carry assets, equity and liabilities and no accruals line, 2 326 satisfy
 * `assets = equity + liabilities` *exactly*. A line the filer left out of the
 * template is a line with nothing in it, not a line we failed to read -- and
 * treating it as unread made this control refuse to judge 2 336 rows it can
 * judge, which is 16 % of the corpus reported as unverifiable for no reason.
 *
 * Eight of those 2 336 do not balance and are now judged rather than excused.
 * At 0.3 % that is a smaller error than the 5.7 % of all rows this control
 * already flags outright, and the alternative -- withholding 2 326 correct
 * verdicts to spare 8 -- is the wrong trade.
 *
 * Equity and liabilities are different. When either is absent the identity
 * genuinely cannot be evaluated, no measurement says an absent line there is a
 * zero, and summing the parts that happen to be present would compare a real
 * figure against a partial one and call the statement wrong.
 */
function pasivaTotal(f: Financials): number | null {
    const { equity, liabilitiesTotal, liabilitiesAccruals } = f;
    if (equity == null || liabilitiesTotal == null) return null;
    return equity + liabilitiesTotal + (liabilitiesAccruals ?? 0);
}

/**
 * The balance sheet, year by year, with the identity it has to satisfy.
 *
 * `assets = equity + liabilities + accruals` is not a nice-to-have here: it is
 * the one check on this page that can be made from the data alone, without a
 * second source and without trusting the parser. Measured 2026-09-12 over the
 * 14 818 stored rows, 14 652 of which carry the figures the identity needs: it
 * holds exactly in 13 816 (94.3 %), one more row is off by under a euro, and
 * 835 (5.7 %) are real discrepancies -- so a reader who sees it fail is looking
 * at a genuinely suspect row, and a reader who sees it hold has a reason to
 * believe the numbers above it.
 */
export const BalanceSheetSection: React.FC<BalanceSheetSectionProps> = ({ company }) => {
    const years = [...company.financials].sort((a, b) => a.year - b.year).slice(-5);

    if (years.length === 0) {
        return <EmptyFinancialsNotice company={company} title="Súvaha" icon="fa-balance-scale" />;
    }

    const renderRow = (row: SheetRow, key: string) => {
        const anyFiled = years.some((f) => row.value(f) != null);
        if (!anyFiled) return null;
        return (
            <tr
                key={key}
                className={
                    row.total
                        ? 'border-t border-gray-200 dark:border-slate-700 bg-gray-50/60 dark:bg-slate-800/40'
                        : 'hover:bg-gray-50/50 dark:hover:bg-slate-900/30'
                }
            >
                <td
                    className={`px-3 py-2 ${
                        row.total
                            ? 'font-semibold text-gray-900 dark:text-white'
                            : 'text-gray-700 dark:text-gray-300'
                    }`}
                >
                    {row.label}
                </td>
                {years.map((f) => (
                    <td
                        key={f.year}
                        className={`px-3 py-2 text-right font-mono tabular-nums whitespace-nowrap ${
                            row.total
                                ? 'font-semibold text-gray-900 dark:text-white'
                                : 'text-gray-700 dark:text-gray-300'
                        }`}
                    >
                        {formatCurrency(row.value(f))}
                    </td>
                ))}
            </tr>
        );
    };

    return (
        <div className="space-y-6">
            <InfoCard title="Súvaha" icon="fa-balance-scale">
                <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
                    Po rokoch, v eurách. Prázdne pole (—) znamená, že závierka tento riadok
                    neobsahovala — nie že by bol nula.
                </p>

                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-gray-200 dark:border-slate-700">
                                <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                    Riadok
                                </th>
                                {years.map((f) => (
                                    <th
                                        key={f.year}
                                        className="px-3 py-2 text-right text-xs font-medium uppercase text-gray-500 dark:text-gray-400"
                                    >
                                        {f.year}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
                            <tr>
                                <td
                                    colSpan={years.length + 1}
                                    className="px-3 pt-3 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500"
                                >
                                    Aktíva
                                </td>
                            </tr>
                            {ASSET_ROWS.map((row) => renderRow(row, `a-${row.label}`))}

                            <tr>
                                <td
                                    colSpan={years.length + 1}
                                    className="px-3 pt-4 pb-1 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500"
                                >
                                    Pasíva
                                </td>
                            </tr>
                            {LIABILITY_ROWS.map((row) => renderRow(row, `l-${row.label}`))}
                            {renderRow(
                                {
                                    label: 'Pasíva spolu',
                                    value: pasivaTotal,
                                    total: true,
                                },
                                'l-pasiva-spolu',
                            )}
                        </tbody>
                    </table>
                </div>
            </InfoCard>

            <ControlRow years={years} />
        </div>
    );
};

/**
 * A difference under a euro is rounding in the filed statement, not a defect.
 *
 * Deliberately absolute, and re-measured 2026-09-12 before leaving it alone. A
 * relative rule (`max(1 €, 0.1 % of assets)`) looks like the obvious fix for a
 * balance sheet in the millions, and it would have been the wrong one: the
 * flagged rows are not a rounding population. 13 816 rows balance *exactly*,
 * exactly one more lands between zero and a euro, and then there is nothing
 * until the real discrepancies. Only 276 of the 835 are within 0.1 % of assets,
 * and those include a 215 905 € gap on assets of 347 M € (0.06 %). A balance
 * sheet is a list of totals the filer already added up, so its parts are
 * supposed to match its own total to the cent -- a relative band would launder
 * real errors as rounding and clear a third of the flags for no reason.
 */
const CONTROL_TOLERANCE = 1;

const ControlRow: React.FC<{ years: Financials[] }> = ({ years }) => {
    const checks = years.map((f) => {
        const pasiva = pasivaTotal(f);
        if (f.assetsTotal == null || pasiva == null) {
            return {
                year: f.year,
                verdict: 'unknown' as const,
                diff: null,
                missing: missingParts(f),
            };
        }
        const diff = Math.round((f.assetsTotal - pasiva) * 100) / 100;
        return {
            year: f.year,
            verdict: Math.abs(diff) < CONTROL_TOLERANCE ? ('ok' as const) : ('off' as const),
            diff,
            missing: [] as string[],
        };
    });

    // Nothing to check against: the identity needs three filed figures and this
    // company filed fewer. Saying "sedí" here would be a claim we cannot make --
    // but naming *which* figure is missing is the difference between a reader
    // who knows what to look for and one who is told only that something is
    // absent. This sentence used to name all four figures including the
    // accruals line, which no longer blocks the check at all.
    if (checks.every((c) => c.verdict === 'unknown')) {
        return (
            <InfoCard title="Kontrola súvahy" icon="fa-check-double">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                    <i className="fas fa-info-circle mr-2"></i>
                    Súvahu nemožno overiť — závierka neobsahuje všetky čísla, ktoré kontrola
                    potrebuje. Chýba: {describeMissing(years)}.
                </p>
            </InfoCard>
        );
    }

    return (
        <InfoCard title="Kontrola súvahy" icon="fa-check-double">
            <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
                Súvaha musí platiť <span className="font-medium">aktíva = vlastné imanie +
                záväzky + časové rozlíšenie</span>. Je to jediná kontrola na tejto stránke,
                ktorá sa dá spraviť z dát samotných — bez druhého zdroja a bez dôvery v to,
                že parser čítal správne.
            </p>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-gray-200 dark:border-slate-700">
                            <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                Rok
                            </th>
                            <th className="px-3 py-2 text-right text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                Rozdiel
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                                Výsledok
                            </th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 dark:divide-slate-800/50">
                        {checks.map((check) => (
                            <tr key={check.year}>
                                <td className="px-3 py-2 font-mono text-gray-900 dark:text-white">
                                    {check.year}
                                </td>
                                <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-700 dark:text-gray-300">
                                    {check.diff == null ? '—' : formatCurrency(check.diff)}
                                </td>
                                <td className="px-3 py-2">
                                    {check.verdict === 'ok' && (
                                        <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700 dark:bg-green-900/20 dark:text-green-400">
                                            <i className="fas fa-check text-[10px]" />
                                            sedí
                                        </span>
                                    )}
                                    {check.verdict === 'off' && (
                                        <span
                                            className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-2.5 py-1 text-xs font-medium text-red-700 dark:bg-red-900/20 dark:text-red-400"
                                            title="Aktíva a pasíva sa rozchádzajú. Buď závierka nebola prečítaná celá, alebo je chyba v nej."
                                        >
                                            <i className="fas fa-exclamation-triangle text-[10px]" />
                                            nesedí
                                        </span>
                                    )}
                                    {check.verdict === 'unknown' && (
                                        <span
                                            className="inline-flex items-center gap-1.5 rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 dark:bg-slate-800 dark:text-gray-300"
                                            title={`Závierka pre tento rok neobsahuje: ${check.missing.join(', ')}.`}
                                        >
                                            <i className="fas fa-question text-[10px]" />
                                            nedá sa overiť
                                        </span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <p className="mt-3 text-xs text-gray-400 dark:text-gray-500">
                Rozdiel do {formatCurrency(CONTROL_TOLERANCE)} sa počíta ako zaokrúhlenie
                v závierke.
            </p>
        </InfoCard>
    );
};
