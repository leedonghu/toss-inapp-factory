export const DEFAULT_ITEMS = ['제육볶음', '김치찌개', '돈까스', '샐러드', '짜장면', '국밥', '초밥', '햄버거'];
export const STORAGE_KEY = 'today-lunch-roulette:items:v1';
export const MAX_ITEMS = 12;
export const errors = {
  empty: '메뉴 이름을 입력해 주세요.',
  length: '메뉴 이름은 20자까지 입력할 수 있어요.',
  duplicate: '이미 있는 메뉴예요. 다른 메뉴를 넣어 주세요.',
  full: '메뉴는 최대 12개까지 넣을 수 있어요.',
};
const key = (text: string) => text.replace(/\s/gu, '').toLocaleLowerCase('ko');
export function addItem(items: string[], input: string): { items: string[]; error?: keyof typeof errors } {
  const value = input.trim();
  if (!value) return { items, error: 'empty' };
  if (Array.from(value).length > 20) return { items, error: 'length' };
  if (items.some(item => key(item) === key(value))) return { items, error: 'duplicate' };
  if (items.length >= MAX_ITEMS) return { items, error: 'full' };
  return { items: [...items, value] };
}
export function removeItem(items: string[], index: number) { return items.filter((_, i) => i !== index); }
export function resetItems() { return [...DEFAULT_ITEMS]; }
type Store = Pick<Storage, 'getItem' | 'setItem'>;
export function loadItems(storage?: Store): string[] {
  try {
    const parsed: unknown = JSON.parse((storage ?? window.localStorage).getItem(STORAGE_KEY) ?? 'null');
    if (!Array.isArray(parsed) || parsed.length > MAX_ITEMS) return resetItems();
    let items: string[] = [];
    for (const item of parsed) {
      if (typeof item !== 'string') return resetItems();
      const next = addItem(items, item);
      if (next.error) return resetItems();
      items = next.items;
    }
    return items;
  } catch { return resetItems(); }
}
export function saveItems(items: string[], storage?: Store): boolean {
  try { (storage ?? window.localStorage).setItem(STORAGE_KEY, JSON.stringify(items)); return true; }
  catch { return false; }
}
