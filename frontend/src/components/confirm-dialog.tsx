"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export interface ConfirmDialogState {
  title: string;
  description: string;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
}

/** In-app replacement for window.confirm() so confirmations match the rest of
 * the UI (themeable, consistent styling) instead of the browser's native
 * dialog. Render once per page; drive it with a single `ConfirmDialogState | null`
 * piece of state. */
export function ConfirmDialog({
  state,
  onOpenChange,
}: {
  state: ConfirmDialogState | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={!!state} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{state?.title}</DialogTitle>
          <DialogDescription>{state?.description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant={state?.destructive ? "destructive" : "default"}
            onClick={() => {
              state?.onConfirm();
              onOpenChange(false);
            }}
          >
            {state?.confirmLabel ?? "Confirm"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
