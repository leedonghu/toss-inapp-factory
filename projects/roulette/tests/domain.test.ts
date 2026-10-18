import { describe, expect, it } from 'vitest';
import { addItem, DEFAULT_ITEMS, loadItems, removeItem, resetItems, saveItems, STORAGE_KEY } from '../src/domain/items';
import { planSpin, resultMessage, sectorAtPointer } from '../src/domain/spin';
describe('menus and device storage', () => {
  it('validates each rule and trims accepted labels', () => {
    expect(addItem([], '  ').error).toBe('empty');
    expect(addItem([], '가'.repeat(21)).error).toBe('length');
    expect(addItem(['Hot Pot'], ' hotpot ').error).toBe('duplicate');
    expect(addItem(Array.from({ length: 12 }, (_, i) => `${i}`), '새 메뉴').error).toBe('full');
    expect(addItem([], ' 김밥 ').items).toEqual(['김밥']);
    expect(addItem([], '🍽'.repeat(20)).error).toBeUndefined();
    expect(removeItem(['a', 'b'], 0)).toEqual(['b']);
    expect(resetItems()).toEqual(DEFAULT_ITEMS);
    expect(resetItems()).not.toBe(DEFAULT_ITEMS);
  });
  it('round trips including an intentionally empty list', () => {
    for (const items of [['김밥', '피자'], [], ['하나']]) { expect(saveItems(items)).toBe(true); expect(loadItems()).toEqual(items); }
  });
  it.each(['null', '{}', 'broken', '[1]', '[" "]', '["a"," A "]', JSON.stringify(['가'.repeat(21)]), JSON.stringify(Array.from({ length: 13 }, (_, i) => `${i}`))])('rejects corrupt stored data %s', value => {
    localStorage.setItem(STORAGE_KEY, value); expect(loadItems()).toEqual(DEFAULT_ITEMS);
  });
  it('handles missing and inaccessible storage', () => {
    expect(loadItems()).toEqual(DEFAULT_ITEMS);
    const broken = { getItem() { throw Error(); }, setItem() { throw Error(); } };
    expect(loadItems(broken)).toEqual(DEFAULT_ITEMS); expect(saveItems([], broken)).toBe(false);
  });
});
describe('spin geometry and fairness', () => {
  it('aligns the pointer for all counts, winners, offsets and existing rotations', () => {
    for (let n = 2; n <= 12; n++) for (let i = 0; i < n; i++) for (const offset of [0, .1, .5, .999999]) for (const previous of [0, 123.4, 5749.3]) {
      const samples = [(i + .5) / n, offset];
      const spin = planSpin(n, previous, () => samples.shift()!);
      expect(spin.winner).toBe(i); expect(sectorAtPointer(spin.angle, n)).toBe(i); expect(spin.angle - previous).toBeGreaterThanOrEqual(1440);
    }
  });
  it('is uniformly distributed with a reproducible large sample', () => {
    let seed = 1234567;
    const random = () => { seed = (Math.imul(1664525, seed) + 1013904223) >>> 0; return seed / 2 ** 32; };
    for (let n = 2; n <= 12; n++) {
      const counts = Array<number>(n).fill(0);
      for (let i = 0; i < 60000; i++) counts[planSpin(n, 0, random).winner]++;
      for (const count of counts) expect(Math.abs(count - 60000 / n) / (60000 / n)).toBeLessThan(.06);
    }
  });
  it('rejects invalid inputs and builds the exact share message', () => {
    expect(() => planSpin(1)).toThrow(); expect(() => planSpin(13)).toThrow(); expect(() => planSpin(2, 0, () => 1)).toThrow();
    expect(resultMessage('김치찌개')).toBe('오늘 점심은 "김치찌개"! 🍽️ - 오늘의 선택 룰렛');
  });
});
