export function LoadingSpinner({ size = 'md', label = 'Processing...' }) {
  const sizes = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' }
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-8">
      <div className={`${sizes[size]} border-2 border-theater-border border-t-theater-accent-light rounded-full animate-spin`} />
      {label && <p className="text-theater-gray text-sm font-mono tracking-wider">{label}</p>}
    </div>
  )
}

export function AIThinking({ label = 'Theater is analyzing...' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 p-12">
      <div className="relative">
        <div className="w-16 h-16 border-2 border-theater-accent/30 rounded-full" />
        <div className="absolute inset-0 border-2 border-transparent border-t-theater-accent-light rounded-full animate-spin" />
        <div className="absolute inset-3 border border-theater-accent/20 rounded-full animate-ping" />
      </div>
      <div className="text-center">
        <p className="text-theater-accent-light font-mono font-semibold tracking-wider">{label}</p>
        <p className="text-theater-muted text-xs font-mono mt-1">This may take a few moments...</p>
      </div>
      <div className="flex gap-1">
        {[0,1,2].map(i => (
          <div key={i} className="w-2 h-2 bg-theater-accent-light rounded-full animate-bounce"
            style={{ animationDelay: `${i * 0.15}s` }} />
        ))}
      </div>
    </div>
  )
}
