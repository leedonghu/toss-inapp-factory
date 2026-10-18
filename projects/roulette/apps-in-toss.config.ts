import { defineConfig } from '@apps-in-toss/web-framework/config';
export default defineConfig({
  appName: 'today-lunch-roulette',
  brand: { primaryColor: '#3182F6' },
  permissions: [{ name: 'clipboard', access: 'write' }],
  webView: { bounces: false, overScrollMode: 'never', pullToRefreshEnabled: false },
  webBundleDir: 'dist',
});
