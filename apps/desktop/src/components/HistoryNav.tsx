import { useEffect, useState } from "react";
import { useLocation, useNavigate, useNavigationType } from "react-router-dom";

const scrollByKey = new Map<string, number>();
let farthestIdx = 0;

function historyIdx(): number {
  return typeof window.history.state?.idx === "number" ? window.history.state.idx : 0;
}

export function HistoryNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const navType = useNavigationType();
  const [canBack, setCanBack] = useState(false);
  const [canForward, setCanForward] = useState(false);

  useEffect(() => {
    const idx = historyIdx();
    if (navType === "PUSH" || navType === "REPLACE") {
      farthestIdx = idx;
    } else if (idx > farthestIdx) {
      farthestIdx = idx;
    }
    setCanBack(idx > 0);
    setCanForward(idx < farthestIdx);

    const previousKey = location.key;
    if (navType === "POP") {
      const y = scrollByKey.get(previousKey);
      requestAnimationFrame(() => {
        window.scrollTo(0, y ?? 0);
      });
    } else {
      window.scrollTo(0, 0);
    }

    return () => {
      scrollByKey.set(previousKey, window.scrollY);
    };
  }, [location.key, navType]);

  return (
    <div className="flex items-center gap-1">
      <HistoryButton
        label="Pagina precedente"
        disabled={!canBack}
        onClick={() => navigate(-1)}
      >
        ←
      </HistoryButton>
      <HistoryButton
        label="Pagina successiva"
        disabled={!canForward}
        onClick={() => navigate(1)}
      >
        →
      </HistoryButton>
    </div>
  );
}

function HistoryButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="flex h-8 w-8 items-center justify-center rounded-lg text-lg leading-none text-stone-700 hover:bg-stone-100 disabled:cursor-not-allowed disabled:text-stone-300 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}

export function PageBackLink({ fallback, label }: { fallback: string; label: string }) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => {
        if (historyIdx() > 0) {
          navigate(-1);
          return;
        }
        navigate(fallback);
      }}
      className="w-fit text-left text-sm text-stone-500 hover:text-stone-900"
    >
      ← {label}
    </button>
  );
}
