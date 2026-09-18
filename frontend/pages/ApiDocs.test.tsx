import {describe, expect, it} from 'vitest';
import {render, screen} from '@testing-library/react';
import {ApiDocs} from './ApiDocs';

// The endpoint card is `overflow-hidden` and nothing in its ancestor chain
// offers `overflow-x-auto`, so anything that does not fit is not merely off
// screen -- it is unreachable, because there is nothing to scroll.
//
// That is what happened to long endpoint paths on a phone. The path sits in a
// `<code>` marked `flex-1`, and a flex item defaults to `min-width: auto`, so it
// refuses to shrink below its min-content width. A URL path is a single
// unbreakable token, so it kept its full width, pushed the JWT badge and the
// expand chevron past the card's clipped edge, and the reader could neither see
// the whole path nor scroll to it.
//
// jsdom does no layout, so this cannot assert the rendered width. It asserts the
// two declarations that make shrinking possible at all -- which is the part that
// silently disappears if someone tidies the className later, and the part that
// no visual review on a wide screen would catch.
describe('ApiDocs -- dlhé cesty endpointov sa musia dať zmenšiť', () => {
    it('cesta endpointu má `min-w-0`, takže sa flex položka zmestí do karty', () => {
        render(<ApiDocs />);

        const path = screen.getByText('/api/auth/change-password/');
        expect(path.tagName).toBe('CODE');

        // `flex-1` alone is what caused the bug: it lets the item grow but not
        // shrink. Both have to be present for the row to fit.
        expect(path.className).toContain('flex-1');
        expect(path.className).toContain('min-w-0');
    });

    it('cesta sa zalomí, namiesto aby ju karta odstrihla', () => {
        render(<ApiDocs />);

        const path = screen.getByText('/api/auth/change-password/');
        expect(path.className).toContain('break-words');
    });

    it('karta je naozaj `overflow-hidden` -- to je dôvod, prečo na `min-w-0` záleží', () => {
        render(<ApiDocs />);

        // Ak by karta raz scrollovala, tento test padne a je správne, aby padol:
        // potom sa dá oprava prehodnotiť, nie dediť naslepo.
        const card = screen.getByText('/api/auth/change-password/').closest('button')?.parentElement;
        expect(card).not.toBeNull();
        expect(card!.className).toContain('overflow-hidden');
    });
});
