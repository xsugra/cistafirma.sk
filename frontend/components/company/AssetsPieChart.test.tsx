import {describe, expect, it} from 'vitest';
import {screen} from '@testing-library/react';
import {AssetsPieChart} from './AssetsPieChart';
import {makeFinancials, renderWithProviders} from '../../test/testUtils';

/** One statement row with every line absent — the shape the cases below vary. */
const base = makeFinancials();

describe('AssetsPieChart', () => {
    it('states the total it does have when the composition could not be read', () => {
        // Exactly what a non-profit's šablóna 1164 produces: `Majetok celkom`
        // is filed and readable, the individual lines beneath it are not. An
        // absent card would read as "this company filed nothing".
        renderWithProviders(<AssetsPieChart data={{...base, assetsTotal: 328, equity: 328}} />);

        expect(screen.getByText('Aktíva 2023')).toBeInTheDocument();
        expect(screen.getByText('328 €')).toBeInTheDocument();
        expect(
            screen.getByText('Rozpis na jednotlivé položky sa z tejto závierky nepodarilo prečítať.')
        ).toBeInTheDocument();
    });

    it('renders the breakdown, without that sentence, when there is one', () => {
        renderWithProviders(
            <AssetsPieChart data={{...base, assetsTotal: 1000, assetsTangible: 600, assetsInventory: 400}} />
        );

        expect(screen.getByText('Hmotný majetok')).toBeInTheDocument();
        expect(screen.getByText('Zásoby')).toBeInTheDocument();
        expect(
            screen.queryByText('Rozpis na jednotlivé položky sa z tejto závierky nepodarilo prečítať.')
        ).toBeNull();
    });

    it('says nothing at all when the statement carried no balance sheet', () => {
        const {container} = renderWithProviders(<AssetsPieChart data={base} />);
        expect(container).toBeEmptyDOMElement();
    });
});
