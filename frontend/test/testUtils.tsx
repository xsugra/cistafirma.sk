import {render} from '@testing-library/react';
import type {ReactElement} from 'react';
import {MemoryRouter} from 'react-router-dom';
import {ThemeProvider} from '../context/ThemeContext';
import type {User} from '../types';

export const DEFAULT_USER: User = {
    id: 'u-test',
    email: 'test@example.com',
    username: 'testuser',
    firstName: 'Test',
    lastName: 'User',
    plan: 'plus',
    apiCallsUsed: 34,
    apiCallsLimit: 50,
    isStaff: false,
    isSuperuser: false,
};

export const makeUser = (overrides: Partial<User> = {}): User => ({...DEFAULT_USER, ...overrides});

/** Router + ThemeProvider wrapper. Auth is supplied per-spec via vi.mock of AuthContext. */
export const renderWithProviders = (ui: ReactElement, {route = '/'}: {route?: string} = {}) =>
    render(
        <MemoryRouter initialEntries={[route]}>
            <ThemeProvider>{ui}</ThemeProvider>
        </MemoryRouter>
    );
