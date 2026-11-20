import React from 'react';

// A small visible label on every modal / section so a problem can be reported by name
// ("M3-D looks wrong"). The full list is in docs/ui-map.md.
export function UiTag({ id, name }) {
  return (
    <span className="ui-tag" data-ui={id} dir="ltr" title={`نام این بخش: ${id} (${name}) — برای گزارش مشکل از این نام استفاده کنید`}>
      {id} · {name}
    </span>
  );
}
