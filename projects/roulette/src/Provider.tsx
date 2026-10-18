import type { ReactNode } from 'react';
import { TDSMobileProvider } from '@toss/tds-mobile';
// The AIT-specific provider logs SDK safe-area errors in standalone browsers.
// Use the base TDS provider and CSS safe-area insets in both environments.
export function AppProvider({ children }: { children: ReactNode }) {
  return <TDSMobileProvider userAgent={{ isAndroid: /Android/.test(navigator.userAgent), isIOS: /iPhone|iPad/.test(navigator.userAgent), fontScale: 100, fontA11y: undefined }} token={{ color: { primary: '#3182f6' } }}>{children}</TDSMobileProvider>;
}
