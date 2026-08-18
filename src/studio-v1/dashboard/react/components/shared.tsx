export function LoadState({ label }: { label: string }) {
  return <div className="sf-load" role="status">{label}</div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="sf-error" role="alert"><b>Couldn’t load this area.</b><span>{message}</span><button onClick={onRetry}>Try again</button></div>;
}
