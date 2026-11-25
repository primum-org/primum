// What can go wrong when the board is asked for something, as a screen shows it: an error
// the board reported, no answer to a question that is being asked again ("offline"), or an
// order that never got to it and that nobody will send again ("unsent").

import { ApiError, OfflineError } from "@/api/client";
import type { ErrorLike } from "@/i18n";

export type Problem = ErrorLike | "offline" | "unsent";

/** The problem behind a failed request. Anything else is a bug of ours, and is raised. */
export function problemOf(failure: unknown): ErrorLike | "offline" {
  if (failure instanceof ApiError) return failure;
  if (failure instanceof OfflineError) return "offline";
  throw failure;
}
