import {describe, expect, it, vi} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {GraphPeriodChips} from './GraphPeriodChips';

interface ChipProps {
    periods?: number[];
    value?: string | null;
    busy?: boolean;
}

const renderChips = (overrides: ChipProps = {}) => {
    const onChange = vi.fn();
    const result = render(
        <GraphPeriodChips
            periods={[2015, 2010]}
            value={null}
            onChange={onChange}
            {...overrides}
        />,
    );
    return {...result, onChange};
};

/**
 * The control that asks the period question, and the two things it must not
 * get wrong.
 *
 * The years come from the backend, newest first, and the order is the backend's
 * -- re-sorting them here would be a second opinion about when this company
 * changed. A chip sends 31 December of its year (`asOfForYear`), not the bare
 * number, because that day is the one the backend filters on.
 */
describe('GraphPeriodChips', () => {
    it('nevykreslí nič, keď firma nemá čo ponúknuť', () => {
        // No periods means no year changed anything, and a lone `Dnes` button
        // would be a control that offers one option. Asserted on the container
        // rather than on the text: the component returns `null`, so there is no
        // element to query for.
        const {container} = renderChips({periods: []});

        expect(container).toBeEmptyDOMElement();
    });

    it('ponúkne Dnes a po jednom čipe za rok, v poradí od backendu', () => {
        renderChips({periods: [2015, 2010]});

        const labels = screen.getAllByRole('button').map((b) => b.textContent);
        expect(labels).toEqual(['Dnes', '2015', '2010']);
    });

    it('označí ako stlačený práve jeden čip — dnešok, keď nie je zvolený rok', () => {
        // `aria-pressed` is the whole state of this control: a reader who
        // cannot see which chip is filled still has to know which day the
        // picture is about.
        renderChips({value: null});

        const pressed = screen
            .getAllByRole('button')
            .filter((b) => b.getAttribute('aria-pressed') === 'true');
        expect(pressed).toHaveLength(1);
        expect(pressed[0]).toHaveTextContent('Dnes');
    });

    it('označí ako stlačený rok, ktorý je naozaj zvolený', () => {
        renderChips({value: '2010-12-31'});

        const pressed = screen
            .getAllByRole('button')
            .filter((b) => b.getAttribute('aria-pressed') === 'true');
        expect(pressed).toHaveLength(1);
        expect(pressed[0]).toHaveTextContent('2010');
        // The value is a full day, not a year: a control that compared against
        // the bare `2010` would leave every chip unpressed.
        expect(screen.getByRole('button', {name: '2015'})).toHaveAttribute(
            'aria-pressed',
            'false',
        );
    });

    it('pošle posledný deň zvoleného roka, nie jeho číslo', async () => {
        const {onChange} = renderChips();

        await userEvent.setup().click(screen.getByRole('button', {name: '2015'}));

        expect(onChange).toHaveBeenCalledWith('2015-12-31');
    });

    it('pošle `null`, keď čitateľ zvolí Dnes', async () => {
        // `null` and not a date: no period is the absence of the parameter, and
        // a request carrying today's date would ask a different question.
        const {onChange} = renderChips({value: '2015-12-31'});

        await userEvent.setup().click(screen.getByRole('button', {name: 'Dnes'}));

        expect(onChange).toHaveBeenCalledWith(null);
    });

    it('nedovolí klikať na čipy, kým beží načítavanie', async () => {
        // A second click while the first answer is in flight is how two
        // requests for one reader end up racing; the row is inert instead, and
        // this is why `busy` is a prop and not a local state.
        const {onChange} = renderChips({busy: true});

        for (const button of screen.getAllByRole('button')) {
            expect(button).toBeDisabled();
        }

        await userEvent.setup().click(screen.getByRole('button', {name: '2015'}));
        expect(onChange).not.toHaveBeenCalled();
    });

    it('pomenuje skupinu, aby sa dala nájsť podľa roly', () => {
        renderChips();

        expect(screen.getByRole('group', {name: 'Obdobie'})).toBeInTheDocument();
    });
});
