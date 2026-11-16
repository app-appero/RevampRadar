import { MANUAL_COMPANY_METHOD, MANUAL_COMPANY_PATH, buildManualCompanyBody, emptyManualCompanyForm } from "./addCompanyForm.ts";

function assert(condition: unknown, message: string) {
  if (!condition) throw new Error(message);
}

const empty = emptyManualCompanyForm();
empty.name = "  Bar Rossi  ";
empty.city = "Palermo";
empty.notes = "\nPrima nota\n";
empty.tags = " lotto2 , ";
empty.socialLinks = [{ label: "Instagram", url: "" }];
const withoutSite = buildManualCompanyBody(empty);
assert(withoutSite.name === "Bar Rossi", "il nome viene ripulito");
assert(withoutSite.website_url === undefined, "il sito vuoto non viene inviato");
assert(withoutSite.email === undefined && withoutSite.phone === undefined, "i contatti vuoti non vengono inventati");
assert(withoutSite.social_links === undefined, "uno social senza url non viene inviato");
assert(withoutSite.city === "Palermo", "la città resta");
assert(JSON.stringify(withoutSite.notes) === JSON.stringify(["Prima nota"]), "le note vuote si scartano");
assert(JSON.stringify(withoutSite.tags) === JSON.stringify(["lotto2"]), "i tag vuoti si scartano");

const withSite = buildManualCompanyBody({
  ...emptyManualCompanyForm(),
  name: "Studio Neri",
  websiteUrl: " https://studio.test ",
  email: "info@studio.test",
  status: "to_contact",
  socialLinks: [{ label: "Instagram", url: "instagram.com/studio" }],
});
assert(withSite.website_url === "https://studio.test", "il sito valorizzato resta nel corpo");
assert(withSite.social_links?.[0]?.url === "instagram.com/studio", "il social valorizzato resta");
assert(!("audit" in withSite) && !("analyze" in withSite), "salvare non richiede un'analisi");

const request = { path: MANUAL_COMPANY_PATH, method: MANUAL_COMPANY_METHOD };
assert(request.path === "/companies" && request.method === "POST", "il salvataggio usa POST /companies");
assert(!request.path.includes("audit"), "il salvataggio non passa dagli audit");

let missingName = false;
try {
  buildManualCompanyBody(emptyManualCompanyForm());
} catch {
  missingName = true;
}
assert(missingName, "senza nome il modulo non parte");

console.log("addCompanyForm ok");
