import {describe, expect, it, vi} from 'vitest';
import {render, screen} from '@testing-library/react';
import {GraphControls} from './GraphControls';

const renderControls = () =>
    render(
        <GraphControls
            onZoomIn={vi.fn()}
            onZoomOut={vi.fn()}
            onReset={vi.fn()}
            onExportPng={vi.fn()}
            onToggleFullscreen={vi.fn()}
            isFullscreen={false}
            nodeCount={37}
            truncated={false}
        />,
    );

/**
 * Measured before this: the text buttons were 28-30 x 32 and the two SVG ones
 * 34 x 26. The height difference is the visible half of the bug -- the icon
 * buttons were shorter than the pill they sit in, so their hover background
 * stopped short of its edges -- and 26 px is roughly half of a thumb.
 *
 * jsdom has no layout engine, so this asserts the class list that produces the
 * box rather than the box itself; the sizes those classes resolve to were
 * measured in Chromium against the built CSS.
 */
describe('GraphControls — veľkosť terčov (#176, krok 4)', () => {
    it('každé tlačidlo má 44 px terč pod `md` a 32 px od `md` vyššie', () => {
        renderControls();
        const buttons = screen.getAllByRole('button');
        expect(buttons).toHaveLength(5);
        for (const b of buttons) {
            expect(b).toHaveClass('min-h-11', 'min-w-11', 'md:min-h-8', 'md:min-w-8');
            // Without centring, a 44 px box around a 14 px glyph leaves the
            // glyph in the top-left corner instead of in the middle of it.
            expect(b).toHaveClass('items-center', 'justify-center');
        }
    });

    it('ikony aj textové glyfy sedia v rovnako veľkom boxe', () => {
        // The defect was that the two kinds of button disagreed; a fix that
        // sized only one kind would leave it in place with this test passing.
        renderControls();
        const buttons = screen.getAllByRole('button');
        const svgButtons = buttons.filter(b => b.querySelector('svg'));
        const glyphButtons = buttons.filter(b => !b.querySelector('svg'));
        expect(svgButtons).toHaveLength(2);
        expect(glyphButtons).toHaveLength(3);
        for (const b of [...svgButtons, ...glyphButtons]) {
            expect(b.className).toContain('min-h-11');
        }
    });
});
