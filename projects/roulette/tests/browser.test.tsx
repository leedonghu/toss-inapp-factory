import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import App from '../src/App';
import { AppProvider } from '../src/Provider';
import { platform } from '../src/platform';
it('renders with the real SDK package but no native bridge and no console errors', async () => {
  const errors = vi.spyOn(console, 'error');
  render(<AppProvider><App /></AppProvider>);
  expect(platform.environment()).toBe('browser');
  expect(screen.getByRole('button', { name: '돌리기' })).toBeInTheDocument();
  expect((await platform.haptic()).ok).toBe(false);
  expect((await platform.copy('메뉴')).ok).toBe(false);
  expect((await platform.share('메뉴')).ok).toBe(false);
  expect(errors).not.toHaveBeenCalled();
});
