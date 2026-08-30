import type { Proposal } from "../api/proposals";

export function ProposalCard({ proposal }: { proposal: Proposal }) {
  return (
    <div className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
      <p className="text-xs text-stone-500">
        {proposal.source === "ai" ? "Testi arricchiti con AI" : "Testo deterministico"} · {proposal.prompt_version}
      </p>
      <p className="text-sm text-stone-700">{proposal.summary}</p>
      <p className="text-sm font-medium">Servizio: {proposal.recommended_service}</p>
      <p className="text-2xl font-semibold">
        {proposal.range_min.toLocaleString("it-IT")}–{proposal.range_max.toLocaleString("it-IT")} {proposal.currency}
      </p>
      <p className="text-xs text-stone-500">{proposal.range_note}</p>
      <div>
        <h3 className="text-xs tracking-wide text-stone-500 uppercase">Problemi prioritari</h3>
        <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-stone-700">
          {proposal.priority_problems.length === 0 ? (
            <li>Nessun finding ad alta gravità.</li>
          ) : (
            proposal.priority_problems.map((item) => (
              <li key={item.code}>
                {item.title} — {item.recommendation}
              </li>
            ))
          )}
        </ul>
      </div>
      <div>
        <h3 className="text-xs tracking-wide text-stone-500 uppercase">Strategia</h3>
        <p className="mt-2 text-sm text-stone-700">{proposal.strategy}</p>
      </div>
      <div>
        <h3 className="text-xs tracking-wide text-stone-500 uppercase">Email</h3>
        <p className="mt-2 text-sm font-medium">{proposal.email_subject}</p>
        <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-stone-700">{proposal.email_body}</pre>
        <button
          type="button"
          className="mt-2 text-xs underline"
          onClick={() =>
            void navigator.clipboard.writeText(`${proposal.email_subject}\n\n${proposal.email_body}`)
          }
        >
          Copia email
        </button>
      </div>
      <div>
        <h3 className="text-xs tracking-wide text-stone-500 uppercase">Brief</h3>
        <pre className="mt-2 whitespace-pre-wrap font-sans text-sm text-stone-700">{proposal.brief}</pre>
      </div>
    </div>
  );
}
