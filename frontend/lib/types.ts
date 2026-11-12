/* What FastAPI's render() sends in JSON mode: the template's own context. Loose by design; the backend owns its shape. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Ctx = Record<string, any>;
export type Role = "A" | "B";
export type Viewer = { fid: string; role: Role; names: Record<Role, string>; me: string | null } | null;
export type Envelope = {
  template: string;
  demo_mode: boolean;
  viewer: Viewer;
  words: { categories: Record<string, string>; status: Record<string, string>; reason: Record<string, string> };
  ctx: Ctx;
};
