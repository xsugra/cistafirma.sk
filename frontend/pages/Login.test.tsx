import {beforeEach, describe, expect, it, vi} from 'vitest';
import {screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {Login} from './Login';
import {renderWithProviders} from '../test/testUtils';

const mocks = vi.hoisted(() => ({
    api: {
        login: vi.fn(),
        // `AuthProvider` asks for the profile on mount when a token is in
        // storage. Every case here starts signed out, so it is not called --
        // but it has to exist on the object the module mock returns.
        getProfile: vi.fn(),
    },
}));

vi.mock('../api', () => ({api: mocks.api}));

const CREDENTIALS = {
    token: 'access-1',
    refresh: 'refresh-1',
    user: {
        id: 'u1',
        email: 'jozef@firma.sk',
        username: 'jmrkvicka',
        firstName: 'Jozef',
        lastName: 'Mrkvička',
        plan: 'plus',
        apiCallsUsed: 0,
        apiCallsLimit: 50,
        isStaff: false,
        isSuperuser: false,
    },
};

const signIn = async () => {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Email alebo používateľské meno'), 'jozef@firma.sk');
    await user.type(screen.getByLabelText('Heslo'), 'tajne-heslo');
    await user.click(screen.getByRole('button', {name: /Prihlásiť sa/}));
};

describe('Login page', () => {
    beforeEach(() => {
        mocks.api.login.mockReset();
        mocks.api.login.mockResolvedValue(CREDENTIALS);
    });

    it('names every field, so the browser will autofill the form', async () => {
        // Chrome says "A form field element has neither an id nor a name
        // attribute" and skips the field; `aria-label` and `placeholder` answer
        // neither half of it.
        renderWithProviders(<Login/>);

        const identifier = screen.getByLabelText('Email alebo používateľské meno');
        const password = screen.getByLabelText('Heslo');
        const remember = screen.getByLabelText('Zapamätať prihlásenie');

        for (const field of [identifier, password, remember]) {
            expect(field).toHaveAttribute('id');
            expect(field).toHaveAttribute('name');
            expect(field.id).not.toBe('');
        }
        expect(identifier).toHaveAttribute('autocomplete', 'username');
        expect(password).toHaveAttribute('autocomplete', 'current-password');
    });

    it('stores a remembered session where closing the browser cannot reach it', async () => {
        // The box is ticked by default, and the default has to be the one that
        // answers "I have to sign in again every time".
        renderWithProviders(<Login/>);

        expect(screen.getByLabelText('Zapamätať prihlásenie')).toBeChecked();

        await signIn();

        await waitFor(() => expect(localStorage.getItem('token')).toBe('access-1'));
        expect(localStorage.getItem('refresh_token')).toBe('refresh-1');
        expect(sessionStorage.getItem('token')).toBeNull();
    });

    it('keeps an unticked session to the tab it was made in', async () => {
        // The other direction: unticking is a real choice, and it has to reach
        // `sessionStorage` rather than being ignored the way it used to be.
        renderWithProviders(<Login/>);

        const user = userEvent.setup();
        await user.click(screen.getByLabelText('Zapamätať prihlásenie'));
        expect(screen.getByLabelText('Zapamätať prihlásenie')).not.toBeChecked();

        await signIn();

        await waitFor(() => expect(sessionStorage.getItem('token')).toBe('access-1'));
        expect(localStorage.getItem('token')).toBeNull();
        expect(sessionStorage.getItem('refresh_token')).toBe('refresh-1');
    });

    it('keeps the refresh token the backend sent', async () => {
        // It used to be read past. Without it there is no way back from an
        // expired access token, which is the whole complaint.
        renderWithProviders(<Login/>);

        await signIn();

        await waitFor(() => expect(mocks.api.login).toHaveBeenCalledWith('jozef@firma.sk', 'tajne-heslo'));
        await waitFor(() => expect(localStorage.getItem('refresh_token')).toBe('refresh-1'));
    });
});
