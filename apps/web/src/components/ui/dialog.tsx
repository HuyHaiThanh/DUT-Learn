import * as DialogPrimitive from '@radix-ui/react-dialog';
import { useRef, type ReactNode } from 'react';
import { Button } from './button';

export function Dialog({ title, description, trigger, open, onOpenChange, pending, focusCancel, children }: {
  title: string; description: string; trigger: ReactNode; open: boolean; onOpenChange: (open: boolean) => void; pending: boolean;
  /** Destructive confirmations start on "Hủy" so Enter cannot confirm by accident. */
  focusCancel?: boolean; children: ReactNode;
}) {
  const cancel = useRef<HTMLButtonElement>(null);
  return <DialogPrimitive.Root open={open} onOpenChange={next => { if (!pending) onOpenChange(next); }}>
    <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
    <DialogPrimitive.Portal><DialogPrimitive.Overlay className="admin-dialog-overlay" />
      <DialogPrimitive.Content className="admin-dialog" aria-busy={pending} onOpenAutoFocus={e => { if (focusCancel) { e.preventDefault(); cancel.current?.focus(); } }} onEscapeKeyDown={e => { if (pending) e.preventDefault(); }} onInteractOutside={e => { if (pending) e.preventDefault(); }}>
        <DialogPrimitive.Title className="row-title">{title}</DialogPrimitive.Title>
        <DialogPrimitive.Description className="metadata">{description}</DialogPrimitive.Description>
        {children}
        <DialogPrimitive.Close asChild><Button ref={cancel} type="button" variant="outline" disabled={pending}>Hủy</Button></DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  </DialogPrimitive.Root>;
}
