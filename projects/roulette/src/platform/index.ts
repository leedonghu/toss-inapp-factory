import { Clipboard, Device, Environment, Share } from '@apps-in-toss/web-framework';
import { createPlatform } from './adapter';
// SDK 3.x domain APIs replace the deprecated functional names in the PRD.
export const platform = createPlatform({
  environment: () => Environment.environment,
  haptic: type => Device.triggerHaptic({ type }),
  share: message => Share.sendMessage({ message }),
  copy: text => Clipboard.setText(text),
});
