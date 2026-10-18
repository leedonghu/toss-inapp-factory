export const normalize = (angle: number) => ((angle % 360) + 360) % 360;
// Sector zero starts at twelve o'clock and sectors proceed clockwise.
export function sectorAtPointer(angle: number, count: number) {
  return Math.min(count - 1, Math.floor(normalize(-angle) / (360 / count)));
}
export function planSpin(count: number, current = 0, rng: () => number = Math.random) {
  if (!Number.isInteger(count) || count < 2 || count > 12) throw new RangeError('2–12 items required');
  const sample = () => {
    const value = rng();
    if (!Number.isFinite(value) || value < 0 || value >= 1) throw new RangeError('RNG must return [0, 1)');
    return value;
  };
  const winner = Math.floor(sample() * count);
  const width = 360 / count;
  const position = (winner + 0.5 + (sample() - 0.5) * 0.6) * width;
  const angle = current + 360 * 4 + normalize(-position - normalize(current));
  return { winner, angle };
}
export const resultMessage = (menu: string) => `오늘 점심은 "${menu}"! 🍽️ - 오늘의 선택 룰렛`;
