import {describe, expect, it} from 'vitest';
import {render, screen} from '@testing-library/react';
import {Terms} from './Terms';

describe('Terms (one-time-licence regression)', () => {
    it('describes a one-time licence with no Cenník link and no auto-renewal', () => {
        render(<Terms/>);
        expect(screen.getByRole('heading', {name: /4\. Licencia a API/i})).toBeInTheDocument();
        expect(screen.getByText(/jednorazovej licencie/i)).toBeInTheDocument();
        expect(screen.getByText(/neobnovuje automaticky/i)).toBeInTheDocument();
        expect(screen.queryAllByText(/cenník/i)).toHaveLength(0);
        expect(screen.queryByRole('link', {name: /cenník/i})).not.toBeInTheDocument();
    });
});
