// What can go wrong when the board is asked for something, as a screen shows it: an error
// the board reported, no answer to a question that is being asked again ("offline"), and
// three ways an order is left undone that nobody will send again: it never got to the board
// ("unsent"), the board did not answer in time and nobody knows whether it did it
// ("unanswered"), or the board no longer knows this device ("forgotten").

import { ApiError, OfflineError, UnansweredError } from "@/api/client";
import type { ErrorLike } from "@/i18n";

export type Undone = "unsent" | "unanswered" | "forgotten";
export type Problem = ErrorLike | "offline" | Undone;

/** The problem behind a failed request. Anything else is a bug of ours, and is raised. */
export function problemOf(failure: unknown): ErrorLike | "offline" | "unanswered" {
  if (failure instanceof ApiError) return failure;
  if (failure instanceof UnansweredError) return "unanswered";
  if (failure instanceof OfflineError) return "offline";
  throw failure;
}
