import { readdirSync, readFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { expect, it } from 'vitest';
it('keeps application source free of external URLs, purchase prompts and personal-data inputs', () => {
  const files = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap(entry => entry.isDirectory() ? files(join(dir, entry.name)) : [join(dir, entry.name)]);
  for (const file of files(resolve('src'))) {
    const text = readFileSync(file, 'utf8');
    expect(text, file).not.toMatch(/https?:\/\//i);
    expect(text, file).not.toMatch(/결제하기|구매하기|카드번호|계좌번호|지금\s*결제/);
    expect(text, file).not.toMatch(/<input[^>]*(?:type\s*=\s*["'](?:email|tel)|(?:name|id|autoComplete)\s*=\s*["'](?:name|phone|email|tel|given-name|family-name))["']/i);
  }
});
