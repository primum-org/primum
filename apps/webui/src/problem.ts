// What can go wrong when the board is asked for something, as a screen shows it: an error
// the board reported, or no answer at all.

import { ApiError, OfflineError } from "@/api/client";
import type { ErrorLike } from "@/i18n";

export type Problem = ErrorLike | "offline";

/** The problem behind a failed request. Anything else is a bug of ours, and is raised. */
export function problemOf(failure: unknown): Problem {
  if (failure instanceof ApiError) return failure;
  if (failure instanceof OfflineError) return "offline";
  throw failure;
}
