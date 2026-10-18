import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import App from '../src/App';
import { AppProvider } from '../src/Provider';
import { DEFAULT_ITEMS, STORAGE_KEY } from '../src/domain/items';
import { platform } from '../src/platform';
vi.mock('../src/platform', () => ({ platform: { haptic: vi.fn().mockResolvedValue({ ok: true, via: 'browser' }), copy: vi.fn(), share: vi.fn() } }));
const mount = () => render(<AppProvider><App /></AppProvider>);
beforeEach(() => { vi.clearAllMocks(); });
it('adds via Enter submission, rejects duplicates, removes and resets menus', () => {
  mount(); const input = screen.getByLabelText('추가할 메뉴');
  fireEvent.change(input, { target: { value: ' 피자 ' } }); fireEvent.submit(input.closest('form')!);
  expect(screen.getByRole('button', { name: '피자 삭제' })).toBeInTheDocument();
  fireEvent.change(input, { target: { value: '피 자' } }); fireEvent.click(screen.getByRole('button', { name: '추가' }));
  expect(screen.getByText(/이미 있는 메뉴/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '피자 삭제' })); expect(screen.queryByRole('button', { name: '피자 삭제' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '제육볶음 삭제' })); fireEvent.click(screen.getByRole('button', { name: '기본값으로 초기화' }));
  expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual(DEFAULT_ITEMS);
});
it('disables input at twelve and spinning below two menus', () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from({ length: 12 }, (_, i) => `메뉴${i}`))); mount();
  expect(screen.getByLabelText('추가할 메뉴')).toBeDisabled(); expect(screen.getByRole('button', { name: '추가' })).toBeDisabled();
  for (let i = 0; i < 11; i++) fireEvent.click(screen.getByRole('button', { name: `메뉴${i} 삭제` }));
  expect(screen.getByRole('button', { name: '돌리기' })).toBeDisabled(); expect(screen.getByText('메뉴를 2개 이상 넣어 주세요.')).toBeInTheDocument();
});
it('locks edits, ignores repeated spins and shows exactly one result and haptic', () => {
  vi.useFakeTimers(); mount(); const spin = screen.getByRole('button', { name: '돌리기' });
  fireEvent.click(spin); fireEvent.click(spin); expect(spin).toBeDisabled(); expect(screen.getByLabelText('추가할 메뉴')).toBeDisabled(); expect(screen.getByRole('button', { name: '제육볶음 삭제' })).toBeDisabled();
  act(() => vi.advanceTimersByTime(3599)); expect(screen.queryByRole('dialog')).toBeNull();
  act(() => vi.advanceTimersByTime(1)); expect(screen.getByRole('dialog')).toBeInTheDocument(); expect(platform.haptic).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: '다시 돌리기' })); expect(screen.queryByRole('dialog')).toBeNull(); act(() => vi.advanceTimersByTime(3600)); expect(platform.haptic).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole('button', { name: '닫기' })); expect(screen.queryByRole('dialog')).toBeNull();
});
it.each(['copy', 'share'] as const)('shows %s success and failure feedback', async kind => {
  vi.useFakeTimers(); mount(); fireEvent.click(screen.getByRole('button', { name: '돌리기' })); act(() => vi.advanceTimersByTime(3600));
  const button = screen.getByRole('button', { name: kind === 'copy' ? '결과 복사' : '공유하기' });
  vi.mocked(platform[kind]).mockResolvedValueOnce({ ok: true, via: 'clipboard' });
  await act(async () => fireEvent.click(button)); expect(within(screen.getByRole('dialog')).getByRole('status')).toHaveTextContent('결과를 복사했어요.');
  vi.mocked(platform[kind]).mockResolvedValueOnce({ ok: false, via: 'none' });
  await act(async () => fireEvent.click(button)); expect(within(screen.getByRole('dialog')).getByRole('status')).toHaveTextContent('사용할 수 없어요');
});
it('honors reduced motion and cancels spin completion after unmount', () => {
  vi.useFakeTimers(); vi.mocked(window.matchMedia).mockImplementation(query => ({ matches: query.includes('prefers-reduced-motion'), addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, media: query, onchange: null, dispatchEvent: () => true }));
  const app = mount(); fireEvent.click(screen.getByRole('button', { name: '돌리기' })); act(() => vi.advanceTimersByTime(120)); expect(screen.getByRole('dialog')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '다시 돌리기' })); app.unmount(); act(() => vi.advanceTimersByTime(3600)); expect(platform.haptic).toHaveBeenCalledTimes(1);
});
it.each([['/privacy', '개인정보처리방침'], ['/terms', '이용약관']])('renders %s and returns home', (path, title) => {
  history.replaceState(null, '', path); mount(); expect(screen.getByRole('heading', { level: 1, name: title })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '룰렛으로 이동' })); expect(screen.getByRole('button', { name: '돌리기' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: title })); expect(location.pathname).toBe(path);
});
it('falls back to home on unknown routes', () => { history.replaceState(null, '', '/missing'); mount(); expect(screen.getByRole('button', { name: '돌리기' })).toBeInTheDocument(); });
