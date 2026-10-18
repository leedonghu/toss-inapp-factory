// PRD-compatible metadata. SDK 3.x reads apps-in-toss.config.ts instead.
export default {
  appName: 'today-lunch-roulette',
  brand: { displayName: '오늘의 선택 룰렛', primaryColor: '#3182F6', icon: '/icon.svg' },
  web: { host: 'localhost', port: 5173, commands: { dev: 'vite --host 0.0.0.0', build: 'npm run build' } },
  permissions: [{ name: 'clipboard', access: 'write' }],
  outdir: 'dist',
};
