export const MANUAL_COMPANY_PATH = "/companies";
export const MANUAL_COMPANY_METHOD = "POST" as const;

export type SocialDraft = { label: string; url: string };

export type ManualCompanyForm = {
  name: string;
  websiteUrl: string;
  email: string;
  phone: string;
  socialLinks: SocialDraft[];
  category: string;
  city: string;
  province: string;
  region: string;
  source: string;
  status: string;
  notes: string;
  tags: string;
};

export type ManualCompanyBody = {
  name: string;
  website_url?: string;
  email?: string;
  phone?: string;
  social_links?: { label: string; url: string }[];
  category?: string;
  city?: string;
  province?: string;
  region?: string;
  source?: string;
  status?: string;
  notes?: string[];
  tags?: string[];
};

export function emptyManualCompanyForm(): ManualCompanyForm {
  return {
    name: "",
    websiteUrl: "",
    email: "",
    phone: "",
    socialLinks: [{ label: "Instagram", url: "" }],
    category: "",
    city: "",
    province: "",
    region: "",
    source: "",
    status: "discovered",
    notes: "",
    tags: "",
  };
}

/** Corpo di POST /companies. I campi vuoti non partono: il backend non deve inventarli. */
export function buildManualCompanyBody(form: ManualCompanyForm): ManualCompanyBody {
  const name = form.name.trim();
  if (!name) {
    throw new Error("Il nome è obbligatorio.");
  }
  const body: ManualCompanyBody = { name };
  assign(body, "website_url", form.websiteUrl);
  assign(body, "email", form.email);
  assign(body, "phone", form.phone);
  assign(body, "category", form.category);
  assign(body, "city", form.city);
  assign(body, "province", form.province);
  assign(body, "region", form.region);
  assign(body, "source", form.source);
  const status = form.status.trim();
  if (status) body.status = status;
  const social = form.socialLinks
    .map((item) => ({ label: item.label.trim(), url: item.url.trim() }))
    .filter((item) => item.url);
  if (social.length) body.social_links = social;
  const notes = form.notes
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (notes.length) body.notes = notes;
  const tags = form.tags
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (tags.length) body.tags = tags;
  return body;
}

function assign(
  body: ManualCompanyBody,
  key: "website_url" | "email" | "phone" | "category" | "city" | "province" | "region" | "source",
  value: string,
) {
  const trimmed = value.trim();
  if (trimmed) body[key] = trimmed;
}
