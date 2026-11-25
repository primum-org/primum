// The time by this device's clock (`performance.now()`), as a value a component can follow
// while it is on screen: what a countdown counts with.

import { onScopeDispose, readonly, ref, type Ref } from "vue";

const STEP_MS = 250;

export function useNow(): Readonly<Ref<number>> {
  const now = ref(performance.now());
  const ticking = setInterval(() => {
    now.value = performance.now();
  }, STEP_MS);
  onScopeDispose(() => clearInterval(ticking));
  return readonly(now);
}
