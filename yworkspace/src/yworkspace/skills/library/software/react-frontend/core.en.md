- Every screen has four states: loading, empty, error, and content. Build all four.
- Forms: visible labels, inline validation messages in plain words, disabled submit while sending,
  success feedback, keyboard submit with Enter.
- Accessibility: semantic HTML (button, nav, main, label), alt text, focus visible, contrast ≥ 4.5:1,
  tap targets ≥ 44px on mobile, `lang` attribute.
- Responsive: design mobile first; check 375px, 768px and 1280px widths; no horizontal scroll.
- Consistency: one spacing scale, one type scale, one primary color; reuse components.
- Turkish text: check that long words (e.g. "Kullanıcılarımızdan") do not break layouts; support İ/ı casing
  correctly (`toLocaleUpperCase('tr-TR')`).
- Verify by opening the page with screen_open and using it, not only by reading the code.
