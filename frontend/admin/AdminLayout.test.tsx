import {afterEach, describe, expect, it, vi} from 'vitest';
import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {AdminLayout} from './AdminLayout';

/**
 * `window.innerWidth` is read to choose the sidebar's starting state, and jsdom
 * fixes it at 1024 for the whole file -- so a spec that wants a phone has to
 * move it before the render and put it back after, or it silently decides what
 * the next spec sees.
 */
const originalWidth = window.innerWidth;

function setViewport(width: number) {
    Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: width,
    });
}

function renderLayout() {
    const onNavigate = vi.fn();
    const onExit = vi.fn();
    const utils = render(
        <AdminLayout activePage="dashboard" onNavigate={onNavigate} onExit={onExit}>
            <p>obsah stránky</p>
        </AdminLayout>,
    );
    const sidebar = utils.container.querySelector('aside');
    if (!sidebar) throw new Error('AdminLayout nezrenderoval <aside>');
    return {...utils, onNavigate, onExit, sidebar};
}

describe('AdminLayout — sidebar na úzkom displeji', () => {
    afterEach(() => {
        Object.defineProperty(window, 'innerWidth', {
            writable: true,
            configurable: true,
            value: originalWidth,
        });
    });

    it('začína zbalený na telefóne, aby nezobral obsah', () => {
        setViewport(393);
        const {sidebar} = renderLayout();
        // 240 px `w-60` beside 393 px left the page 153 px wide; collapsed the
        // content keeps all 393.
        expect(sidebar).toHaveClass('w-16');
        expect(sidebar).not.toHaveClass('w-60');
    });

    it('zbalený na telefóne zmizne úplne, nezostane ako 64 px koľajnica', () => {
        setViewport(393);
        const {sidebar} = renderLayout();
        // Measured at 393 px: an absolute 64 px rail covers x 0..64 while the
        // content starts at x 0, so the first 40 px of every line sat behind it.
        // `hidden md:flex` and not `max-md:hidden` beside a plain `flex` --
        // both are display utilities, `flex` is emitted last, and the hidden
        // one lost. Variant versus plain utility is the ordering that holds.
        expect(sidebar).toHaveClass('hidden', 'md:flex');
        expect(sidebar).not.toHaveClass('flex');
    });

    it('otvorený na telefóne prekrýva obsah, nestláča ho', async () => {
        setViewport(393);
        const {sidebar} = renderLayout();
        // It starts collapsed, so "open" here has to be reached the way a
        // reader reaches it.
        await userEvent.click(screen.getByRole('button', {name: 'Rozbaliť menu'}));
        expect(sidebar).toHaveClass('w-60', 'flex', 'max-md:absolute');
        expect(sidebar).not.toHaveClass('hidden');
    });

    it('začína otvorený na širokej obrazovke, kde je naň miesto', () => {
        setViewport(1280);
        const {sidebar} = renderLayout();
        expect(sidebar).toHaveClass('w-60');
    });

    it('pod `md` vystúpi z toku a prekryje obsah namiesto toho, aby ho stlačil', () => {
        setViewport(393);
        const {sidebar} = renderLayout();
        expect(sidebar).toHaveClass('max-md:absolute', 'max-md:z-30');
    });

    it('prepínač je pomenovaný a dosť veľký na prst', async () => {
        setViewport(393);
        const {sidebar} = renderLayout();
        // Collapsed, so the label is the one that opens it.
        const toggle = screen.getByRole('button', {name: 'Rozbaliť menu'});
        expect(toggle).toHaveClass('min-h-11', 'min-w-11');
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        await userEvent.click(toggle);
        expect(sidebar).toHaveClass('w-60');
        expect(screen.getByRole('button', {name: 'Zbaliť menu'})).toHaveAttribute(
            'aria-expanded',
            'true',
        );
    });

    it('sa za čitateľom zbali, keď na telefóne klikne na položku', async () => {
        setViewport(393);
        const {sidebar, onNavigate} = renderLayout();
        await userEvent.click(screen.getByRole('button', {name: 'Rozbaliť menu'}));
        expect(sidebar).toHaveClass('w-60');

        // Otherwise the overlay stays over the page it just opened and every
        // navigation costs a second tap to dismiss it.
        await userEvent.click(screen.getByRole('button', {name: 'Dashboard'}));
        expect(onNavigate).toHaveBeenCalledWith('dashboard');
        expect(sidebar).toHaveClass('w-16');
    });

    it('na širokej obrazovke po kliknutí na položku zostane otvorený', async () => {
        setViewport(1280);
        const {sidebar} = renderLayout();
        // Beside the content rather than over it, so there is nothing to
        // dismiss -- and collapsing here would overrule a deliberate toggle.
        await userEvent.click(screen.getByRole('button', {name: 'Dashboard'}));
        expect(sidebar).toHaveClass('w-60');
    });
});
