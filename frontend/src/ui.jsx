import React, {useEffect, useRef, useState} from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {AlertDialog, Button, TextField} from '@radix-ui/themes';

// Radix portals must render inside the Theme root, otherwise the design tokens (colours, radius) do not apply.
const themeRoot = () => (typeof document === 'undefined' ? undefined : document.querySelector('.radix-themes') || undefined);

/**
 * Accessible modal: focus is trapped and restored, Esc and outside-click close it, the page behind does not scroll,
 * and screen readers get a dialog with a label. The visual frame is whatever single element is passed as children.
 */
export function ModalShell({onClose, label, children}) {
  return (
    <Dialog.Root open onOpenChange={open => { if (!open) onClose(); }}>
      <Dialog.Portal container={themeRoot()}>
        <Dialog.Overlay className="sdlc-modal-overlay">
          <Dialog.Title className="sr-only">{label}</Dialog.Title>
          <Dialog.Description className="sr-only">{label}</Dialog.Description>
          <Dialog.Content asChild onOpenAutoFocus={event => {
            // focus the first field when there is one, otherwise the dialog itself
            const field = event.currentTarget?.querySelector?.('input:not([type=hidden]),textarea,select');
            if (field) { event.preventDefault(); field.focus(); }
          }}>
            {children}
          </Dialog.Content>
        </Dialog.Overlay>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ------------------------------------------------------------------------- confirm / prompt (promise based)
let request = null;
let handler = null;

function ask(options) {
  return new Promise(resolve => {
    const entry = {...options, resolve};
    if (handler) handler(entry); else request = entry;  // before the host mounted: it picks the request up
  });
}

/** `if (!await confirmDialog('Delete?', {danger: true})) return;` — replaces window.confirm. */
export const confirmDialog = (message, {title = 'تأیید', confirmText = 'تأیید', cancelText = 'انصراف', danger = false} = {}) =>
  ask({kind: 'confirm', message, title, confirmText, cancelText, danger});

/** `const name = await promptDialog('Name?', 'default')` — replaces window.prompt; null when cancelled. */
export const promptDialog = (message, value = '', {title = 'ورود اطلاعات', confirmText = 'ثبت', cancelText = 'انصراف'} = {}) =>
  ask({kind: 'prompt', message, value, title, confirmText, cancelText});

/** Mount once inside <Theme>. */
export function DialogHost() {
  const [current, setCurrent] = useState(null);
  const [text, setText] = useState('');
  const inputRef = useRef(null);

  useEffect(() => {
    handler = entry => { setText(entry.value || ''); setCurrent(entry); };
    if (request) { handler(request); request = null; }
    return () => { handler = null; };
  }, []);

  function finish(result) {
    const entry = current;
    setCurrent(null);
    if (entry) entry.resolve(result);
  }

  const prompt = current?.kind === 'prompt';
  return (
    <AlertDialog.Root open={!!current} onOpenChange={open => { if (!open) finish(prompt ? null : false); }}>
      <AlertDialog.Content maxWidth="440px" dir="rtl" onOpenAutoFocus={event => { if (prompt && inputRef.current) { event.preventDefault(); inputRef.current.focus(); inputRef.current.select(); } }}>
        <AlertDialog.Title>{current?.title}</AlertDialog.Title>
        <AlertDialog.Description size="2" style={{whiteSpace: 'pre-line'}}>{current?.message}</AlertDialog.Description>
        {prompt && (
          <TextField.Root mt="3" ref={inputRef} value={text} onChange={event => setText(event.target.value)}
            onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); finish(text); } }} />
        )}
        <div className="ui-dialog-actions">
          <AlertDialog.Cancel><Button variant="soft" color="gray" onClick={() => finish(prompt ? null : false)}>{current?.cancelText}</Button></AlertDialog.Cancel>
          <AlertDialog.Action><Button color={current?.danger ? 'red' : undefined} onClick={() => finish(prompt ? text : true)}>{current?.confirmText}</Button></AlertDialog.Action>
        </div>
      </AlertDialog.Content>
    </AlertDialog.Root>
  );
}
