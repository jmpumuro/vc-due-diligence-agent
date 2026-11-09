/** Shared brand mark + stroke icons for Research/Console shells. */

export function ThesisMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
      <rect width="28" height="28" rx="10" fill="var(--brand)" />
      <path
        d="M8 9.5h12M14 9.5v10"
        stroke="#FFFFFF"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Icon({ d }: { d: string }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={d} />
    </svg>
  );
}
