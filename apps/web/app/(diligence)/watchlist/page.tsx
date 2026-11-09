import ResearchShell from "@/components/shell/ResearchShell";
import { apiJson } from "@/lib/api";
import { sessionCookie } from "@/lib/session";
import WatchlistClient from "./WatchlistClient";

export default async function WatchlistPage() {
  const cookie = await sessionCookie();
  const list = cookie
    ? await apiJson<{
        items: Array<{
          id: string;
          company_name: string;
          primary_domain?: string;
          cadence: string;
          paused: boolean;
        }>;
      }>("/api/v1/watchlist", cookie)
    : null;

  return (
    <ResearchShell title="Watchlist" demo>
      <WatchlistClient initial={list?.items || []} />
    </ResearchShell>
  );
}
