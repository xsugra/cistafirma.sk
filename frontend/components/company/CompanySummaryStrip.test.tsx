import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {CompanySummaryStrip} from './CompanySummaryStrip';
import {makeCompany, renderWithProviders} from '../../test/testUtils';
import type {Company, VatStatus} from '../../types';

/**
 * The DPH card, over the states the register actually produces.
 *
 * The card used to have two outputs for four states: `isVatPayer ? 'Platiteľ
 * DPH' : 'Neplatiteľ DPH'` over a nullable column, and a reliability string
 * compared against a value the register has never contained.
 */

const withVat = (vat: Partial<VatStatus>): Company =>
    makeCompany({
        vatStatus: {
            icDph: 'SK1234567890',
            isVatPayer: true,
            taxReliabilityIndex: 'spoľahlivý',
            registeredOn: '2010-01-01',
            deregisteredOn: null,
            reasonForDeregistration: null,
            lastCheckedAt: '2026-01-01T00:00:00Z',
            ...vat,
        },
    });

describe('CompanySummaryStrip — DPH status', () => {
    it('shows a current payer as one, with the date it entered the register', () => {
        renderWithProviders(<CompanySummaryStrip company={withVat({})} />);

        expect(screen.getByText('Platiteľ DPH')).toBeInTheDocument();
        expect(screen.getByText(/od 01\.01\.2010/)).toBeInTheDocument();
    });

    it('shows a deregistration as a deregistration, with the date and the reason', () => {
        // 32 050 rows. The reason was typed in `types.ts`, mapped in `api.ts`,
        // set in the mocks -- and rendered nowhere, so the page said only
        // "Neplatiteľ DPH" and the violation that caused it never reached a
        // reader. `vat_deleted_date` was not even mapped.
        renderWithProviders(
            <CompanySummaryStrip
                company={withVat({
                    isVatPayer: null,
                    deregisteredOn: '2019-03-12',
                    reasonForDeregistration: 'Rok porušenia: 2018',
                })}
            />
        );

        expect(screen.getByText('Vymazaný z registra DPH')).toBeInTheDocument();
        expect(screen.getByText(/12\.03\.2019/)).toBeInTheDocument();
        expect(screen.getByText(/porušenie v roku 2018/)).toBeInTheDocument();
        expect(screen.queryByText('Neplatiteľ DPH')).not.toBeInTheDocument();
    });

    it('says it does not know rather than calling an unrated company a non-payer', () => {
        // The 302 713 rows where Finančná správa published no `Platiteľ DPH`.
        // "Neplatiteľ DPH" is a claim about them that no source made.
        renderWithProviders(
            <CompanySummaryStrip
                company={withVat({
                    isVatPayer: null,
                    registeredOn: null,
                    taxReliabilityIndex: null,
                })}
            />
        );

        expect(screen.getByText('Nezistené')).toBeInTheDocument();
        expect(screen.queryByText('Neplatiteľ DPH')).not.toBeInTheDocument();
        expect(screen.queryByText('Platiteľ DPH')).not.toBeInTheDocument();
        expect(screen.getByText(/bez indexu spoľahlivosti/)).toBeInTheDocument();
        // Neither the registration date nor a removal date is invented for a
        // company whose register entry we never read. "K dátumu" stays, because
        // that one is the date *we* last read the tax office -- a fact about
        // our own copy, not a claim about the company.
        expect(screen.queryByText(/^od /)).not.toBeInTheDocument();
        expect(screen.getByText(/K dátumu/)).toBeInTheDocument();
    });

    it('draws the worst reliability band differently from the best', () => {
        // The regression this pins: the warning branch compared against
        // 'Nespoľahlivý', a value no row of the column contains, so a company
        // the tax office rated `menej spoľahlivý` was drawn exactly like one it
        // rated `vysoko spoľahlivý`.
        const worst = renderWithProviders(
            <CompanySummaryStrip company={withVat({taxReliabilityIndex: 'menej spoľahlivý'})} />
        );
        const worstClass = screen.getByText('Menej spoľahlivý').className;
        worst.unmount();

        renderWithProviders(
            <CompanySummaryStrip company={withVat({taxReliabilityIndex: 'vysoko spoľahlivý'})} />
        );

        expect(screen.getByText('Vysoko spoľahlivý')).toBeInTheDocument();
        expect(worstClass).not.toBe(screen.getByText('Vysoko spoľahlivý').className);
        expect(worstClass).toMatch(/amber/);
    });
});
