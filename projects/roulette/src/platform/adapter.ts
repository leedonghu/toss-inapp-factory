export type HapticType = 'success' | 'tap';
export type Outcome = { ok: boolean; via: 'sdk' | 'browser' | 'clipboard' | 'none' | 'cancelled' };
export interface Sdk {
  environment(): string;
  haptic(type: HapticType): Promise<void>;
  share(message: string): Promise<void>;
  copy(text: string): Promise<void>;
}
export interface Browser {
  vibrate?(duration: number): boolean;
  share?(data: { text: string }): Promise<void>;
  clipboard?: { writeText(text: string): Promise<void> };
  // Selection-based copy for pages without the async Clipboard API (e.g. plain HTTP on a LAN IP).
  legacyCopy?(text: string): boolean;
}
export function legacyCopy(text: string): boolean {
  const area = document.createElement('textarea');
  area.value = text; area.setAttribute('readonly', '');
  area.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
  // Content outside an open modal dialog is inert and cannot be selected.
  const host = document.querySelector('dialog[open]') ?? document.body;
  const focused = document.activeElement as HTMLElement | null;
  host.appendChild(area); area.select();
  try { return document.execCommand('copy'); }
  finally { area.remove(); focused?.focus(); }
}
const defaultBrowser = (): Browser => ({
  vibrate: navigator.vibrate?.bind(navigator),
  share: navigator.share?.bind(navigator),
  clipboard: navigator.clipboard,
  legacyCopy,
});
// Dependency injection keeps host errors and browser fallback paths independently testable.
export function createPlatform(sdk: Sdk | undefined, browser: () => Browser = defaultBrowser) {
  function environment() {
    try { const value = sdk?.environment(); return value === 'toss' || value === 'sandbox' ? value : 'browser'; }
    catch { return 'browser'; }
  }
  async function native(action: (api: Sdk) => Promise<void>): Promise<boolean> {
    try { if (sdk && environment() !== 'browser') { await action(sdk); return true; } }
    catch { /* Host unavailable or permission denied: use browser fallback. */ }
    return false;
  }
  async function copy(text: string): Promise<Outcome> {
    if (await native(api => api.copy(text))) return { ok: true, via: 'sdk' };
    let api: Browser;
    try { api = browser(); } catch { return { ok: false, via: 'none' }; }
    try { if (api.clipboard) { await api.clipboard.writeText(text); return { ok: true, via: 'clipboard' }; } }
    catch { /* Denied or no user activation: try the selection-based copy. */ }
    try { if (api.legacyCopy?.(text)) return { ok: true, via: 'clipboard' }; }
    catch { /* A denied clipboard must not interrupt the result screen. */ }
    return { ok: false, via: 'none' };
  }
  return {
    environment,
    copy,
    async haptic(type: HapticType = 'success'): Promise<Outcome> {
      if (await native(api => api.haptic(type))) return { ok: true, via: 'sdk' };
      try { if (browser().vibrate?.(35)) return { ok: true, via: 'browser' }; } catch { /* no-op */ }
      return { ok: false, via: 'none' };
    },
    async share(message: string): Promise<Outcome> {
      if (await native(api => api.share(message))) return { ok: true, via: 'sdk' };
      try { const api = browser(); if (api.share) { await api.share({ text: message }); return { ok: true, via: 'browser' }; } }
      catch (error) {
        // The user closed the share sheet on purpose; copying now would also fail without a fresh tap.
        if (error instanceof DOMException && error.name === 'AbortError') return { ok: false, via: 'cancelled' };
        /* Unsupported or denied: offer the copy fallback. */
      }
      return copy(message);
    },
  };
}
