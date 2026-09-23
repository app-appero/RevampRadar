from __future__ import annotations

REFACTOR_TOKENS = ("nome_mittente", "nome_attivita", "luogo", "dominio", "firma", "osservazione")
GREENFIELD_TOKENS = ("nome_mittente", "nome_attivita", "luogo", "firma")

DEFAULT_REFACTOR_EMAIL_TEMPLATE = """Buongiorno,

mi chiamo {{nome_mittente}} e sono uno sviluppatore web freelance. Aiuto le attività a migliorare la propria presenza online, rendendo i loro siti web più moderni, funzionali e semplici da utilizzare per i clienti.

Ho avuto modo di visitare il sito di {{nome_attivita}}{{luogo}} ({{dominio}}) e credo ci siano delle interessanti opportunità per valorizzare ulteriormente la vostra attività online.{{osservazione}}

Mi piacerebbe proporvi alcune soluzioni per migliorare l'esperienza di chi visita il vostro sito, facilitare il contatto con i potenziali clienti e rendere la vostra presenza digitale ancora più efficace.

Se vi fa piacere, possiamo approfondire insieme le possibilità di miglioramento e capire quali interventi potrebbero essere più utili per la vostra struttura.

Resto a disposizione per qualsiasi informazione.

Un saluto,
{{firma}}"""

DEFAULT_GREENFIELD_EMAIL_TEMPLATE = """Buongiorno,

mi chiamo {{nome_mittente}} e sono uno sviluppatore web freelance. Aiuto le attività a migliorare la propria presenza online, rendendo più semplice per i clienti scoprirle, conoscerle e mettersi in contatto con loro.

Ho avuto modo di conoscere la vostra attività e credo ci siano delle interessanti opportunità per valorizzarla ulteriormente attraverso una presenza online dedicata.

Mi piacerebbe proporvi la realizzazione di un sito web moderno, professionale e semplice da utilizzare, che permetta di presentare al meglio la vostra attività, valorizzare i vostri servizi e facilitare il contatto con i potenziali clienti.

Avere un sito web dedicato può aiutarvi a raggiungere nuove persone, migliorare la vostra visibilità online e offrire un punto di riferimento a chi desidera conoscere meglio ciò che proponete.

Se vi fa piacere, possiamo approfondire insieme questa possibilità e valutare una soluzione adatta alle vostre esigenze.

Resto a disposizione per qualsiasi informazione.

Un saluto,
{{firma}}"""


def render_email_template(template: str, context: dict[str, str]) -> str:
    """Sostituzione semplice di token {{nome}}: nessuna eccezione su token mancanti o testo libero."""
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered
