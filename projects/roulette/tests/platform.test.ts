import { expect, it, vi } from 'vitest';
import { createPlatform, type Browser, type Sdk } from '../src/platform/adapter';
const sdk = (): Sdk => ({ environment: () => 'toss', haptic: vi.fn().mockResolvedValue(undefined), share: vi.fn().mockResolvedValue(undefined), copy: vi.fn().mockResolvedValue(undefined) });
const browser = (): Browser => ({ vibrate: vi.fn().mockReturnValue(true), share: vi.fn().mockResolvedValue(undefined), clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
it('uses each supported SDK API without browser calls', async () => {
  const native = sdk(); const web = browser(); const p = createPlatform(native, () => web);
  expect(p.environment()).toBe('toss');
  expect(await p.haptic('success')).toEqual({ ok: true, via: 'sdk' }); expect(native.haptic).toHaveBeenCalledWith('success');
  expect(await p.share('menu')).toEqual({ ok: true, via: 'sdk' }); expect(native.share).toHaveBeenCalledWith('menu');
  expect(await p.copy('menu')).toEqual({ ok: true, via: 'sdk' }); expect(native.copy).toHaveBeenCalledWith('menu');
  expect(web.share).not.toHaveBeenCalled(); expect(web.vibrate).not.toHaveBeenCalled(); expect(web.clipboard!.writeText).not.toHaveBeenCalled();
});
it.each(['absent', 'throws', 'bad environment'])('falls back for all methods when SDK is %s', async mode => {
  const native = mode === 'absent' ? undefined : sdk();
  if (native && mode === 'throws') { native.haptic = native.copy = native.share = async () => { throw Error('host'); }; }
  if (native && mode === 'bad environment') native.environment = () => { throw Error('detection'); };
  const web = browser(); const p = createPlatform(native, () => web);
  expect((await p.haptic()).via).toBe('browser'); expect((await p.copy('menu')).via).toBe('clipboard'); expect((await p.share('menu')).via).toBe('browser');
  expect(web.vibrate).toHaveBeenCalledWith(35); expect(web.share).toHaveBeenCalledWith({ text: 'menu' }); expect(web.clipboard!.writeText).toHaveBeenCalledWith('menu');
});
it('falls back from Web Share to clipboard and reports clipboard as the outcome', async () => {
  const web = browser(); web.share = async () => { throw Error('denied'); };
  expect(await createPlatform(undefined, () => web).share('menu')).toEqual({ ok: true, via: 'clipboard' });
  delete web.share; expect((await createPlatform(undefined, () => web).share('menu')).ok).toBe(true);
});
it('copies with the selection fallback when the Clipboard API is missing or denied', async () => {
  const legacyCopy = vi.fn().mockReturnValue(true);
  expect(await createPlatform(undefined, () => ({ legacyCopy })).copy('menu')).toEqual({ ok: true, via: 'clipboard' });
  const denied: Browser = { clipboard: { writeText: async () => { throw Error('NotAllowedError'); } }, legacyCopy };
  expect(await createPlatform(undefined, () => denied).share('menu')).toEqual({ ok: true, via: 'clipboard' });
  expect(legacyCopy).toHaveBeenCalledWith('menu');
});
it('treats a cancelled share sheet as cancelled without copying', async () => {
  const web = browser(); web.share = async () => { throw new DOMException('cancelled', 'AbortError'); };
  expect(await createPlatform(undefined, () => web).share('menu')).toEqual({ ok: false, via: 'cancelled' });
  expect(web.clipboard!.writeText).not.toHaveBeenCalled();
});
it.each(['missing', 'throwing', 'inaccessible'])('never throws with %s browser APIs', async mode => {
  const web: Browser = mode === 'missing' ? {} : { vibrate() { throw Error(); }, share: async () => { throw Error(); }, clipboard: { writeText: async () => { throw Error(); } } };
  const p = createPlatform(undefined, () => { if (mode === 'inaccessible') throw Error(); return web; });
  expect(p.environment()).toBe('browser');
  for (const result of [await p.haptic(), await p.copy('a'), await p.share('a')]) expect(result).toEqual({ ok: false, via: 'none' });
});
