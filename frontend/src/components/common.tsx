import type { ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { AlertCircle, X, LoaderCircle, ArrowUpRight } from "lucide-react";
import { Button } from "./ui/button";
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-symbol">
        <svg
          width="64"
          height="56"
          viewBox="0 0 64 56"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M32 9v12M32 21C32 28 12 26 12 35v7M32 21c0 7 20 5 20 14v7"
            stroke="currentColor"
          />
          <circle cx="32" cy="8" r="5" stroke="currentColor" />
          <circle cx="12" cy="46" r="5" stroke="currentColor" />
          <circle cx="52" cy="46" r="5" stroke="currentColor" />
        </svg>
      </div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function ErrorNotice({
  message,
  retry,
}: {
  message?: string;
  retry?: () => void;
}) {
  return message ? (
    <div className="notice error" role="alert">
      <AlertCircle size={17} />
      <span>{message}</span>
      {retry && (
        <Button size="sm" onClick={retry}>
          Retry
        </Button>
      )}
    </div>
  ) : null;
}
export function Loading({ label = "Loading workspace" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <LoaderCircle size={18} className="spin" />
      {label}…
    </div>
  );
}
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className="modal">
          <div className="modal-head">
            <Dialog.Title>{title}</Dialog.Title>
            <Dialog.Close asChild>
              <Button size="icon" variant="ghost" aria-label="Close dialog">
                <X size={18} />
              </Button>
            </Dialog.Close>
          </div>
          <Dialog.Description>{description}</Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function Disclosure({
  title,
  children,
  open = false,
}: {
  title: string;
  children: ReactNode;
  open?: boolean;
}) {
  return (
    <details className="disclosure" open={open || undefined}>
      <summary>
        {title}
        <ArrowUpRight size={14} />
      </summary>
      <div>{children}</div>
    </details>
  );
}
export function Status({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: string;
}) {
  return (
    <span className={`status ${tone}`}>
      <i />
      {label}
    </span>
  );
}
